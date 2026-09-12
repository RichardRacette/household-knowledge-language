"""Inspectable experiment probes; expected behaviors are authored, not generated."""
import copy
import json
import subprocess
import sys
import tempfile
import shutil
import zipfile
from pathlib import Path

from .answers import build_plan, public_view, render
from .common import FIXTURES, ROOT, digest, json_bytes, read_json, write_json
from .model import resolve, schema_errors, semantic_errors, simulated_accept, tables, validate
from .preservation import export_packet, unpack_packet, zip_packet
from .packet_reader import verify
from .temporal import available_as_of, historical_location


def check(rows, name, observed, expected=True, layer="answer-eligibility"):
    rows.append({"case": name, "layer": layer, "observed": observed, "expected": expected, "passed": observed == expected})


def e1(corpus, profile):
    rows = []
    check(rows, "normal corpus", validate(corpus, profile), [], "schema-and-semantic")
    view = public_view(corpus, profile)
    all_refs = [s["ref"] for s in view["profile"]["sources"]]
    plan = lambda subject, predicate: build_plan(view, all_refs, {"subjects": [subject], "predicate": predicate})
    quote = plan("bird", "gift_quote")
    raw_source = (FIXTURES / "sources/OBJ-0004--EVID-001.txt").read_text(encoding="utf-8")
    check(rows, "quotation recovered exactly from source bytes", quote["claims"][0]["value"] in raw_source, layer="exact-source")
    check(rows, "precise quotation remains Reported", quote["claims"][0]["epistemic_state"], "Reported")
    check(rows, "paraphrase remains qualified at confidence .99", plan("bird", "gift_paraphrase")["mode"], "Qualified")
    repeated = plan("bird", "gift_repeat")
    check(rows, "newer repeated paraphrase retains three-source lineage", len(repeated["claims"][0]["evidence"]), 3)
    check(rows, "conflicting givers remain separately attributed", {x["attributed_to"] for x in plan("bird", "giver")["claims"]} == {"Elena Marlow", "Leo Marlow"})
    check(rows, "pending record remains pending", corpus["records"][0]["approval"]["state"], "Pending", "decision-contract")
    for name, mutation in [
        ("missing evidence", lambda c, p: c["records"][0]["claims"][0]["evidence_ids"].append("EVID-999")),
        ("duplicate local claim", lambda c, p: c["records"][0]["claims"].append(copy.deepcopy(c["records"][0]["claims"][0]))),
        ("duplicate local evidence", lambda c, p: c["records"][0]["evidence"].append(copy.deepcopy(c["records"][0]["evidence"][0]))),
        ("missing decision reference", lambda c, p: p["assertions"][0].update(decision_ref="SIM-MISSING")),
        ("QA decision cannot approve claim", lambda c, p: p["assertions"][0].update(decision_ref="SIM-QA-BIRD")),
        ("record status cannot substitute for decision", lambda c, p: c["records"][0]["approval"].update(state="Approved")),
        ("derived source cannot become primary", lambda c, p: next(e for e in c["records"][0]["evidence"] if e["evidence_id"] == "EVID-003").update(reliability="Primary")),
        ("quotation cannot become Known", lambda c, p: next(r for r in c["records"] if r["record_id"] == "OBJ-0004")["claims"][0].update(epistemic_state="Known")),
    ]:
        c, p = copy.deepcopy(corpus), copy.deepcopy(profile)
        mutation(c, p)
        check(rows, name + " passes legacy/envelope structure", schema_errors(c, p), [], "schema")
        errors = semantic_errors(c, p)
        check(rows, name + " rejected semantically", bool(errors), layer="semantic-reference")
        rows[-1]["diagnostics"] = errors
    evidence = tables(corpus, profile)[2]
    try:
        resolve("EVID-001", evidence)
        ambiguous = False
    except ValueError:
        ambiguous = True
    check(rows, "unqualified cross-record ID collision rejected", ambiguous, layer="semantic-reference")
    check(rows, "qualified collisions remain distinct", evidence["OBJ-0001/EVID-001"] != evidence["OBJ-0004/EVID-001"], layer="semantic-reference")
    check(rows, "restricted and derived content absent before context", b"ORCHID-482" not in json_bytes(view), layer="privacy-projection")
    check(rows, "restricted existence acknowledged without contents", plan("letter", "contents")["mode"], "Private")
    before = copy.deepcopy(profile)
    target = next(a for a in before["assertions"] if a["basis"] == "quotation")
    old_id = target["decision_ref"]
    target["decision_ref"] = None
    before["decisions"] = [d for d in before["decisions"] if d["id"] != old_id]
    before_bytes = json_bytes(before)
    before_plan = build_plan(public_view(corpus, before), all_refs, {"subjects": ["bird"], "predicate": "gift_quote"})
    after = simulated_accept(before, target["ref"], old_id, target["recorded_at"])
    after_plan = build_plan(public_view(corpus, after), all_refs, {"subjects": ["bird"], "predicate": "gift_quote"})
    check(rows, "no decision requires review", before_plan["mode"], "Needs Human", "decision-contract")
    check(rows, "simulated acceptance preserves uncertainty", after_plan["mode"], "Qualified", "decision-contract")
    check(rows, "transition leaves earlier snapshot unchanged", json_bytes(before) == before_bytes, layer="decision-contract")
    check(rows, "transition preserves assertion content", after["assertions"] == profile["assertions"], layer="decision-contract")
    check(rows, "transition preserves all decision identities and contents", {d["id"]: d for d in after["decisions"]} == {d["id"]: d for d in profile["decisions"]}, layer="decision-contract")
    return {"checks": rows, "before": before_plan, "after": after_plan, "rendered_before": render(before_plan), "rendered_after": render(after_plan), "conflict_plan": plan("bird", "giver"), "repeated_paraphrase": repeated}


def e3(corpus, profile, output, receipt):
    packet = output / "packet"
    exported = export_packet(corpus, profile, packet, receipt)
    archive = output / "fictional-public-packet.zip"
    zip_packet(packet, archive)
    with tempfile.TemporaryDirectory(prefix="hkl-detached-") as directory:
        detached = Path(directory) / "packet"
        unpack_packet(archive, detached)
        command = [sys.executable, "-I", "-S", "read_packet.py", ".", "--isolated", "--probe-path", str(ROOT / "household_record.schema.json")]
        process = subprocess.run(command, cwd=detached, capture_output=True, text=True, timeout=30)
        if process.returncode:
            raise RuntimeError("detached verification failed: " + process.stdout + process.stderr)
        recovered = json.loads(process.stdout)
        old = read_json(packet / "packet-manifest.json")["files"]
        new = read_json(detached / "packet-manifest.json")["files"]
        roundtrip = old == new
    rows = []
    check(rows, "original bytes and identities round-trip", roundtrip, layer="preservation")
    check(rows, "original project access denied", recovered["isolation"]["original_path_denied"], layer="preservation")
    check(rows, "network access denied", recovered["isolation"]["network_denied"], layer="preservation")
    check(rows, "packet-only reader recovers Reported quotation", recovered["reader_exercise"]["state"], "Reported", "preservation")
    check(rows, "restricted byte markers absent from all packet files", all(b"ORCHID-482" not in p.read_bytes() for p in packet.rglob("*") if p.is_file()), layer="privacy-projection")
    corruptions = corrupt_packet_probes(packet)
    for c in corruptions:
        check(rows, c["case"], c["detected"], layer="packet-verification")
    return {"checks": rows, "export": exported, "detached_reader": recovered, "corruptions": corruptions, "archive_sha256": digest(archive.read_bytes()), "archive_bytes": archive.stat().st_size, "detached_command": "python -I -S read_packet.py . --isolated --probe-path <original-project-schema>", "limits": "Automated reconstruction only; no human usability study, full RO-Crate validation or OAIS certification."}


def corrupt_packet_probes(packet):
    """Rehash structural mutations so the tests challenge links, not only fixity."""
    results = []
    def edit(p, name, mutate):
        value = read_json(p / name)
        mutate(value)
        write_json(p / name, value)
        if name != "packet-manifest.json":
            manifest = read_json(p / "packet-manifest.json")
            manifest["files"][name] = digest((p / name).read_bytes())
            write_json(p / "packet-manifest.json", manifest)
    def edit_profiles(p, mutate):
        # Preserve the valid before/after relationship to isolate link validation.
        for name in ("profile.json", "history/profile-before-simulated-decision.json"):
            edit(p, name, mutate)
    def unreferenced_decision(p, **changes):
        def mutate(value):
            decision = copy.deepcopy(value["decisions"][0])
            decision.update(id="SIM-UNREFERENCED", **changes)
            value["decisions"].append(decision)
        edit_profiles(p, mutate)
    def remove_baseline_history(p):
        name = "history/ceramic_bird.json"
        (p / name).unlink()
        edit(p, "packet-manifest.json", lambda x: x["files"].pop(name))
        def mutate(crate):
            crate["@graph"] = [x for x in crate["@graph"] if x["@id"] != name]
            root = next(x for x in crate["@graph"] if x["@id"] == "./")
            root["hasPart"] = [x for x in root["hasPart"] if x["@id"] != name]
        edit(p, "ro-crate-metadata.json", mutate)
    cases = [
        ("missing source file", lambda p: (p / "sources/OBJ-0004--EVID-001.txt").unlink()),
        ("modified source bytes", lambda p: (p / "sources/OBJ-0004--EVID-001.txt").write_bytes(b"corrupt")),
        ("broken source derivation link", lambda p: edit(p, "profile.json", lambda x: x["sources"][0]["derived_from"].append("OBJ-9999/EVID-001"))),
        ("broken assertion link", lambda p: edit(p, "profile.json", lambda x: x["assertions"][0].update(subject="missing-entity"))),
        ("cyclic source lineage", lambda p: edit(p, "profile.json", lambda x: (x["sources"][0].update(derived_from=[x["sources"][1]["ref"]]), x["sources"][1].update(derived_from=[x["sources"][0]["ref"]])))),
        ("broken record-local claim link", lambda p: edit(p, "corpus.json", lambda x: x["records"][0]["claims"][0].update(evidence_ids=["EVID-999"]))),
        ("current profile substituted for earlier history", lambda p: edit(p, "history/profile-before-simulated-decision.json", lambda x: (x.clear(), x.update(read_json(p / "profile.json"))))),
        ("non-acceptance decision", lambda p: edit(p, "profile.json", lambda x: x["decisions"][0].update(action="reject"))),
        ("decision predates assertion", lambda p: edit(p, "profile.json", lambda x: x["decisions"][0].update(recorded_at="1900-01-01T00:00:00Z"))),
        ("unreferenced non-acceptance decision", lambda p: unreferenced_decision(p, action="reject")),
        ("unreferenced decision predates assertion", lambda p: unreferenced_decision(p, recorded_at="1900-01-01T00:00:00Z")),
        ("unreferenced invalid decision timestamp", lambda p: unreferenced_decision(p, recorded_at="not-a-time")),
        ("broken assertion event reference", lambda p: edit_profiles(p, lambda x: x["assertions"][0].update(event="MISSING-EVENT"))),
        ("broken source entity reference", lambda p: edit_profiles(p, lambda x: x["sources"][0].update(entities=["MISSING-ENTITY"]))),
        ("duplicate entity identity", lambda p: edit_profiles(p, lambda x: x["entities"].append(copy.deepcopy(x["entities"][0])))),
        ("duplicate event identity", lambda p: edit_profiles(p, lambda x: x["events"].append(copy.deepcopy(x["events"][0])))),
        ("broken event source reference", lambda p: edit_profiles(p, lambda x: x["events"][0].update(source_refs=["OBJ-9999/EVID-001"]))),
        ("broken relation entity reference", lambda p: edit_profiles(p, lambda x: x["relations"][0].update(object="MISSING-ENTITY"))),
        ("broken record-local event evidence", lambda p: edit(p, "corpus.json", lambda x: x["records"][0]["events"][0].update(evidence_ids=["EVID-999"]))),
        ("missing baseline history with inventory repaired", remove_baseline_history),
        ("empty software receipt", lambda p: edit(p, "software.json", lambda x: x.clear())),
        ("software revision mismatch", lambda p: edit(p, "software.json", lambda x: x.update(code_revision="different"))),
        ("fixture provenance receipt mismatch", lambda p: edit(p, "packet-manifest.json", lambda x: x.update(source_fixture_manifest_sha256="0"*64))),
        ("unsupported profile version", lambda p: edit(p, "profile.json", lambda x: x.update(version="99.0"))),
        ("unsupported packet version", lambda p: edit(p, "packet-manifest.json", lambda x: x.update(version="99.0"))),
        ("unsafe manifest path", lambda p: edit(p, "packet-manifest.json", lambda x: x["files"].update({"../escape.txt": "0"*64}))),
        ("broken crate link", lambda p: edit(p, "ro-crate-metadata.json", lambda x: next(n for n in x["@graph"] if n["@id"] == "#export").update(instrument={"@id": "#missing"}))),
        ("restricted evidence annotation in public packet", lambda p: edit(p, "corpus.json", lambda x: x["records"][0]["evidence"][0].update(privacy_class="Restricted"))),
        ("unlisted extra file", lambda p: (p / "extra.txt").write_text("extra", encoding="utf-8")),
    ]
    for name, mutate in cases:
        with tempfile.TemporaryDirectory(prefix="hkl-corruption-") as tmp:
            target = Path(tmp) / "packet"
            shutil.copytree(packet, target)
            verify(target)  # positive control for the same checker
            mutate(target)
            try:
                verify(target)
                detected, diagnostic = False, "accepted unexpectedly"
            except (ValueError, OSError) as exc:
                detected, diagnostic = True, str(exc)
            results.append({"case": name, "detected": detected, "diagnostic": diagnostic})
    for name in ("../escape.txt", "/absolute.txt", "C:/drive.txt", "sources/../alias.txt", "CON.txt", "sources/file.txt:stream"):
        with tempfile.TemporaryDirectory(prefix="hkl-unsafe-zip-") as tmp:
            archive = Path(tmp) / "unsafe.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr(name, "unsafe synthetic entry")
            try:
                unpack_packet(archive, Path(tmp) / "unpacked")
                detected, diagnostic = False, "accepted unexpectedly"
            except ValueError as exc:
                detected, diagnostic = True, str(exc)
            results.append({"case": "unsafe zip path: " + name, "detected": detected, "diagnostic": diagnostic})
    return results


def e2(corpus, profile):
    rows, queries = [], []
    for label, day, as_of, expected in [
        ("historical hallway", "2022-06-01", None, ("supported", ["Hallway"])),
        ("initial move assertion", "2024-05-02", "2024-06-01T00:00:00Z", ("supported", ["Study"])),
        ("gap exposed by correction", "2024-05-02", "2026-09-01T00:00:00Z", ("gap", [])),
        ("conflicting late recollection", "2023-06-01", None, ("overlap", ["Attic", "Hallway"])),
        ("late recollection unavailable earlier", "2023-06-01", "2024-06-01T00:00:00Z", ("supported", ["Hallway"])),
        ("corrected open interval", "2025-01-01", None, ("supported", ["Study"])),
    ]:
        result = historical_location(profile, "bird", day, as_of)
        queries.append({"case": label, "projection": result, "legacy": {"status": "not structurally answerable", "current_area_only": corpus["records"][0]["location_and_state"]["current_area"], "reason": "Legacy event strings have no recording-time/correction links or queryable location intervals."}})
        check(rows, label, (result["status"], result["locations"]) == expected, layer="temporal-query")
    time_by_ref = {a["ref"]: a["time"] for a in profile["assertions"]}
    check(rows, "year expression preserved without asserted January 1", time_by_ref["DISPLAY-0001/CLM-001"]["expression"], "1998", "temporal-query")
    check(rows, "approximate key date retained", time_by_ref["OBJ-0010/CLM-001"]["precision"], "approximate", "temporal-query")
    check(rows, "exact photo date retained", time_by_ref["OBJ-0002/CLM-001"]["start"], "1991-06-15", "temporal-query")
    check(rows, "possession by date is not acquisition", next(a for a in profile["assertions"] if a["ref"] == "OBJ-0001/CLM-001")["predicate"], "possessed_by", "temporal-query")
    check(rows, "one move event survives correction", len([e for e in profile["events"] if e["kind"] == "Moved"]), 1, "temporal-query")
    check(rows, "earlier assertion is retained", any(a["ref"] == "OBJ-0001/CLM-007" for a in profile["assertions"]), layer="temporal-query")
    for label, mutation in [
        ("inverted interval", lambda p: next(a for a in p["assertions"] if a["ref"] == "OBJ-0001/CLM-006")["time"].update(start="2025-01-01")),
        ("invented year precision", lambda p: next(a for a in p["assertions"] if a["ref"] == "DISPLAY-0001/CLM-001")["time"].update(start="1998-06-01")),
        ("correction as a new physical event", lambda p: next(a for a in p["assertions"] if a["ref"] == "OBJ-0001/CLM-008").update(event=None)),
        ("correction before original assertion", lambda p: next(a for a in p["assertions"] if a["ref"] == "OBJ-0001/CLM-008").update(recorded_at="2020-01-01T00:00:00Z")),
    ]:
        p = copy.deepcopy(profile)
        mutation(p)
        diagnostics = semantic_errors(corpus, p)
        check(rows, label + " rejected", bool(diagnostics), layer="semantic-reference")
        rows[-1]["diagnostics"] = diagnostics
    original_bird = read_json(FIXTURES / "originals/ceramic_bird.json")
    original_collection = read_json(FIXTURES / "originals/annual_ornament_collection.json")
    return {"checks": rows, "queries": queries,
            "available_as_of": [available_as_of(profile, "2024-06-01T00:00:00Z"), available_as_of(profile, "2026-09-01T00:00:00Z")],
            "existing_representation_successes": [{"question": "What source date expression describes the bird photograph?", "output": original_bird["events"][0]["date_or_range"], "faithful_scope": "Source expression; does not answer an exact acquisition date."}, {"question": "What recurring display interval is recorded?", "output": original_collection["events"][-1]["date_or_range"], "faithful_scope": "Textual recurrence; explicit recurrence rules are deferred."}], "decision": "ADOPT IN PUBLIC WORKBENCH: explicit assertion valid-time and recorded-time projection; defer temporal NLP, recurrence expansion and RDF reasoning."}


def e4(corpus, profile):
    rows = []
    view = public_view(corpus, profile)
    refs = [s["ref"] for s in view["profile"]["sources"]]
    demonstrations = []
    for label, subject, predicate, mode in [
        ("manufacturing label is an observation", "label-observation", "manufacturing_label", "Direct"),
        ("manufacturing place does not establish clay origin", "bird", "geological_origin", "Unknown"),
        ("photograph date does not establish bird creation", "bird", "photograph_date", "Unknown"),
        ("digitization does not establish object creation", "bird", "digitization_date", "Unknown"),
        ("proximity does not establish shared provenance", "stone", "shared_provenance", "Unknown"),
        ("missing ornament does not prove never existed", "collection", "2017_never_existed", "Unknown"),
        ("different people's meanings coexist", "ticket", "meaning", "Qualified"),
        ("composite cannot expose restricted derivative", "letter", "summary", "Private"),
    ]:
        plan = build_plan(view, refs, {"subjects": [subject], "predicate": predicate})
        check(rows, label, plan["mode"], mode, "answer-eligibility")
        demonstrations.append({"case": label, "plan": plan, "rendered": render(plan)})
    for label, mutation in [
        ("observation retargeted to physical object", lambda p: next(a for a in p["assertions"] if a["predicate"] == "manufacturing_label").update(subject="bird")),
        ("photo date retargeted to physical object", lambda p: next(a for a in p["assertions"] if a["predicate"] == "photograph_date").update(subject="bird")),
        ("unresolved relationship entity", lambda p: p["relations"][0].update(object="missing")),
    ]:
        p = copy.deepcopy(profile)
        mutation(p)
        errors = semantic_errors(corpus, p)
        check(rows, label + " rejected", bool(errors), layer="semantic-reference")
        rows[-1]["diagnostics"] = errors
    return {"checks": rows, "entities": profile["entities"][:12], "relations": view["profile"]["relations"], "demonstrations": demonstrations, "decision": "ADOPT IN PUBLIC WORKBENCH: typed roles and exact subject/predicate answer eligibility; defer arbitrary prose entailment and full heritage ontology."}
