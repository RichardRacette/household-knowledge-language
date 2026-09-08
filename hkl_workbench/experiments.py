"""Inspectable experiment probes; expected behaviors are authored, not generated."""
import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from .answers import build_plan, public_view, render
from .common import FIXTURES, ROOT, digest, json_bytes, read_json, write_json
from .model import resolve, schema_errors, semantic_errors, simulated_accept, tables, validate
from .preservation import export_packet, unpack_packet, zip_packet


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
    return {"checks": rows, "export": exported, "detached_reader": recovered, "archive_sha256": digest(archive.read_bytes()), "archive_bytes": archive.stat().st_size, "detached_command": "python -I -S read_packet.py . --isolated --probe-path <original-project-schema>", "limits": "Automated reconstruction only; no human usability study, full RO-Crate validation or OAIS certification."}
