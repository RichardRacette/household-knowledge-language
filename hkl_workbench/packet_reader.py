"""Standalone stdlib reader/verifier for the bounded HKL packet profile.

Copy this file with a packet. It imports no HKL code and never fetches JSON-LD
contexts. Its documented subset checks are not full RO-Crate conformance.
"""
import argparse
import hashlib
import json
import re
import socket
import sys
from datetime import date, datetime
from pathlib import Path


def safe(root, name):
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_./-]+", name):
        raise ValueError("unsafe packet path")
    parts = name.split("/")
    reserved = {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(10)], *[f"LPT{i}" for i in range(10)]}
    if any(x in ("", ".", "..") or x.endswith(".") or x.split(".")[0].upper() in reserved for x in parts):
        raise ValueError("unsafe packet path")
    p = root
    for part in parts:
        p = p / part
        if p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction()):
            raise ValueError("linked packet path")
    if not p.resolve().is_relative_to(root):
        raise ValueError("packet path escape")
    return p


def load(root, name):
    return json.loads(safe(root, name).read_text(encoding="utf-8"))


def verify(root):
    root = Path(root).resolve()
    manifest = load(root, "packet-manifest.json")
    if manifest.get("version") != "1.0" or manifest.get("view") != "public":
        raise ValueError("unsupported packet version/view")
    names = manifest["files"]
    if len({x.casefold() for x in names}) != len(names):
        raise ValueError("case-colliding packet paths")
    for name, expected in names.items():
        p = safe(root, name)
        if not p.is_file():
            raise ValueError("missing packet file")
        if hashlib.sha256(p.read_bytes()).hexdigest() != expected:
            raise ValueError("modified packet bytes")
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() or p.is_symlink()}
    if actual != set(names) | {"packet-manifest.json"}:
        raise ValueError("unlisted packet file")
    required = {"corpus.json", "profile.json", "policy.json", "software.json", "household_record.schema.json", "profile.schema.json", "README.md", "LICENSE", "read_packet.py", "ro-crate-metadata.json", "history/profile-before-simulated-decision.json"}
    if not required <= set(names):
        raise ValueError("missing profile payload")
    corpus, profile = load(root, "corpus.json"), load(root, "profile.json")
    software = load(root, "software.json")
    if not all(software.get(x) for x in ("code_revision", "python", "dependencies", "timestamp_utc", "fixture_manifest_sha256")):
        raise ValueError("software receipt lacks versions/provenance")
    if not re.fullmatch(r"[0-9a-f]{64}", software["fixture_manifest_sha256"]) or manifest.get("source_fixture_manifest_sha256") != software["fixture_manifest_sha256"]:
        raise ValueError("fixture provenance receipts differ")
    if not all(isinstance(k, str) and isinstance(v, str) and v for k, v in software["dependencies"].items()):
        raise ValueError("invalid dependency versions")
    if corpus.get("version") != "1" or profile.get("version") != "1.0" or corpus.get("fictional") is not True or profile.get("fictional") is not True:
        raise ValueError("unsupported payload version")
    evidence = {}
    claims = {}
    records = {r["record_id"]: r for r in corpus["records"]}
    if len(records) != len(corpus["records"]):
        raise ValueError("duplicate record identity")
    for r in corpus["records"]:
        if r["privacy"]["privacy_class"] != "Public Demo":
            raise ValueError("nonpublic record")
        for e in r["evidence"]:
            ref = r["record_id"] + "/" + e["evidence_id"]
            if ref in evidence or e["privacy_class"] != "Public Demo":
                raise ValueError("evidence collision or disclosure")
            evidence[ref] = e
        for c in r["claims"]:
            ref = r["record_id"] + "/" + c["claim_id"]
            if ref in claims:
                raise ValueError("claim collision")
            claims[ref] = c
    sources = {s["ref"]: s for s in profile["sources"]}
    if len(sources) != len(profile["sources"]) or set(sources) != set(evidence):
        raise ValueError("source identities differ")
    for ref, s in sources.items():
        if s["disclosure"] != "public" or s["path"] not in names or not set(s["derived_from"]) <= set(sources):
            raise ValueError("broken source link")
        if evidence[ref]["sha256"] != names[s["path"]]:
            raise ValueError("source hash differs")
    for ref, c in claims.items():
        if not {ref.split("/")[0] + "/" + x for x in c["evidence_ids"]} <= set(evidence):
            raise ValueError("broken record-local claim link")
    for r in corpus["records"]:
        for group, key in (("events", "event_id"), ("relationships", "relationship_id"), ("questions_and_answers", "qa_id")):
            if len({x[key] for x in r[group]}) != len(r[group]):
                raise ValueError("duplicate record-local identity")
            for item in r[group]:
                for field, targets in (("evidence_ids", evidence), ("claim_ids", claims)):
                    if not {r["record_id"] + "/" + x for x in item.get(field, [])} <= set(targets):
                        raise ValueError("broken record-local " + group + " link")
    assertions = {a["ref"]: a for a in profile["assertions"]}
    entities = {e["id"] for e in profile["entities"]}
    decisions = {d["id"]: d for d in profile["decisions"]}
    events = {e["id"]: e for e in profile["events"]}
    if len(assertions) != len(profile["assertions"]) or len(decisions) != len(profile["decisions"]) or len(entities) != len(profile["entities"]) or len(events) != len(profile["events"]):
        raise ValueError("duplicate profile identity")
    for s in sources.values():
        if not set(s["entities"]) <= entities:
            raise ValueError("broken source entity link")
    for event in events.values():
        if event["subject"] not in entities or not set(event["source_refs"]) <= set(sources):
            raise ValueError("broken event link")
    for relation in profile["relations"]:
        if not {relation["subject"], relation["object"]} <= entities or not set(relation["source_refs"]) <= set(sources):
            raise ValueError("broken relation link")
    for a in assertions.values():
        if a["subject"] not in entities or a["ref"] not in claims or not set(a["source_refs"]) <= set(sources) or not set(a["derived_from"] + a["conflicts_with"]) <= set(assertions) or (a["supersedes"] and a["supersedes"] not in assertions):
            raise ValueError("broken assertion link")
        local = {a["ref"].split("/")[0] + "/" + x for x in claims[a["ref"]]["evidence_ids"]}
        if set(a["source_refs"]) != local:
            raise ValueError("assertion support differs from record")
        if a["event"] and events.get(a["event"], {}).get("subject") != a["subject"]:
            raise ValueError("broken assertion event link")
        if a["decision_ref"]:
            d = decisions.get(a["decision_ref"], {})
            if d.get("target") != a["ref"] or d.get("scope") != "claim" or d.get("simulated") is not True or d.get("action") != "accept_for_demo" or datetime.fromisoformat(d["recorded_at"].replace("Z", "+00:00")) < datetime.fromisoformat(a["recorded_at"].replace("Z", "+00:00")):
                raise ValueError("broken simulated decision link")
    for d in decisions.values():
        if d.get("simulated") is not True or d.get("scope") != "claim" or d.get("target") not in assertions or d.get("action") != "accept_for_demo":
            raise ValueError("invalid simulated decision")
        recorded = datetime.fromisoformat(d["recorded_at"].replace("Z", "+00:00"))
        asserted = datetime.fromisoformat(assertions[d["target"]]["recorded_at"].replace("Z", "+00:00"))
        if recorded.tzinfo is None or asserted.tzinfo is None or recorded < asserted:
            raise ValueError("invalid simulated decision time")
    def acyclic(mapping, key):
        done = set()
        def visit(ref, trail):
            if ref in trail:
                raise ValueError("cyclic packet derivation")
            if ref in done:
                return
            for parent in mapping[ref][key]:
                visit(parent, trail | {ref})
            done.add(ref)
        for ref in mapping:
            visit(ref, set())
    acyclic(sources, "derived_from")
    acyclic(assertions, "derived_from")
    crate = load(root, "ro-crate-metadata.json")
    if crate.get("@context") != "https://w3id.org/ro/crate/1.2/context":
        raise ValueError("unsupported RO-Crate context")
    graph = {x["@id"]: x for x in crate["@graph"]}
    if graph.get("#software", {}).get("version") != software["code_revision"]:
        raise ValueError("crate software version differs from receipt")
    if len(graph) != len(crate["@graph"]):
        raise ValueError("duplicate crate identity")
    descriptor, dataset = graph.get("ro-crate-metadata.json", {}), graph.get("./", {})
    if descriptor.get("@type") != "CreativeWork" or descriptor.get("about") != {"@id": "./"} or descriptor.get("conformsTo") != {"@id": "https://w3id.org/ro/crate/1.2"}:
        raise ValueError("invalid crate descriptor")
    if dataset.get("@type") != "Dataset" or not all(dataset.get(x) for x in ("name", "description", "datePublished", "license")):
        raise ValueError("invalid crate root")
    date.fromisoformat(dataset["datePublished"])
    if {x["@id"] for x in dataset["hasPart"]} != set(names) - {"ro-crate-metadata.json"}:
        raise ValueError("crate inventory differs")
    def links(value):
        if isinstance(value, list):
            for child in value:
                links(child)
        elif isinstance(value, dict):
            if set(value) == {"@id"} and not value["@id"].startswith("https://") and value["@id"] not in graph:
                raise ValueError("broken crate link")
            for key, child in value.items():
                if key != "@id":
                    links(child)
    links(crate["@graph"])
    for item in graph.values():
        if item["@type"] in ("CreateAction", "UpdateAction") and not item.get("object"):
            raise ValueError("curation action lacks input")
        if item["@type"] == "SoftwareApplication" and not item.get("version"):
            raise ValueError("software lacks version")
    baseline_history = {"OBJ-0001": "ceramic_bird.json", "DISPLAY-0001": "composite_memory_shelf.json", "COLLECTION-0001": "annual_ornament_collection.json"}
    for rid, filename in baseline_history.items():
        name = "history/" + filename
        if rid in records:
            if name not in names:
                raise ValueError("missing public baseline history")
            snapshot = load(root, name)
            if snapshot["record_id"] != rid or snapshot["privacy"]["privacy_class"] != "Public Demo":
                raise ValueError("invalid public baseline history")
        elif name in names:
            raise ValueError("history reveals omitted record")
    before = load(root, "history/profile-before-simulated-decision.json")
    if {a['ref'] for a in before['assertions']} != set(assertions):
        raise ValueError("history identities differ")
    # A packet-only exercise: reconstruct a quotation's support and recorded uncertainty.
    quote = next(a for a in assertions.values() if a["basis"] == "quotation")
    expected_before = json.loads(json.dumps(profile))
    next(a for a in expected_before["assertions"] if a["ref"] == quote["ref"])["decision_ref"] = None
    expected_before["decisions"] = [d for d in expected_before["decisions"] if d["id"] != quote["decision_ref"]]
    if before != expected_before:
        raise ValueError("history does not preserve the simulated transition")
    answer = {"claim": quote["ref"], "attributed_to": quote["attributed_to"], "state": claims[quote["ref"]]["epistemic_state"], "source_files": [sources[x]["path"] for x in quote["source_refs"]], "decision_simulated": decisions[quote["decision_ref"]]["simulated"]}
    return {"verified": True, "files_checked": len(names), "source_files_recovered": len(sources), "source_identities": sorted(sources), "reader_exercise": answer, "history_retained": True, "objectives": {"bytes": True, "lineage_links": True, "uncertainty_fields": True}, "human_usability_study": False, "full_ro_crate_validation": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("--isolated", action="store_true")
    parser.add_argument("--probe-path", type=Path)
    args = parser.parse_args()
    root = args.packet.resolve()
    isolation = {}
    if args.isolated:
        # All modules above are loaded before imposing packet-only file access.
        def audit(event, values):
            if event == "open" and not isinstance(values[0], int):
                if not Path(values[0]).resolve().is_relative_to(root):
                    raise PermissionError("outside packet access denied")
            if event.startswith("socket."):
                raise PermissionError("network disabled")
        sys.addaudithook(audit)
        try:
            with open(args.probe_path or root.parent / "unavailable-source", "rb"):
                pass
        except PermissionError:
            isolation["original_path_denied"] = True
        try:
            socket.socket()
        except PermissionError:
            isolation["network_denied"] = True
        if len(isolation) != 2:
            raise ValueError("isolation probe failed")
    result = verify(root)
    result["isolation"] = isolation
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"verified": False, "error": str(exc)}))
        raise SystemExit(1)
