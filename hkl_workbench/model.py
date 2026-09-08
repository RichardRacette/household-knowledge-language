"""Schema, reference, source-authority and simulated decision contracts.

These checks do not determine natural-language entailment or authenticate people.
"""
from __future__ import annotations

import copy
from collections import Counter
from datetime import date, datetime

from jsonschema import Draft202012Validator, FormatChecker

from .common import ROOT, read_json


def tables(corpus, profile):
    records = {r["record_id"]: r for r in corpus["records"]}
    claims = {r["record_id"] + "/" + c["claim_id"]: c for r in records.values() for c in r["claims"]}
    evidence = {r["record_id"] + "/" + e["evidence_id"]: e for r in records.values() for e in r["evidence"]}
    return records, claims, evidence, {s["ref"]: s for s in profile["sources"]}


def resolve(ref, mapping):
    if "/" not in ref:
        matches = [k for k in mapping if k.endswith("/" + ref)]
        raise ValueError("ambiguous local identity" if len(matches) > 1 else "record-qualified identity required")
    if ref not in mapping:
        raise ValueError("missing reference: " + ref)
    return mapping[ref]


def schema_errors(corpus, profile):
    errors = []
    validator = Draft202012Validator(read_json(ROOT / "household_record.schema.json"), format_checker=FormatChecker())
    for r in corpus.get("records", []):
        errors.extend("record-schema: " + e.message for e in validator.iter_errors(r))
    validator = Draft202012Validator(read_json(ROOT / "hkl_workbench/profile.schema.json"), format_checker=FormatChecker())
    errors.extend("profile-schema: " + e.message for e in validator.iter_errors(profile))
    if corpus.get("version") != "1" or corpus.get("fictional") is not True:
        errors.append("record-schema: unsupported fictional corpus envelope")
    return errors


def time_errors(t):
    if t is None:
        return []
    try:
        start = date.fromisoformat(t["start"]) if t["start"] else None
        end = date.fromisoformat(t["end"]) if t["end"] else None
        precision = t["precision"]
        if start and end and (start > end or (start == end and precision != "exact")):
            return ["invalid interval order"]
        if precision == "exact" and (not start or start != end or t["expression"] != t["start"]):
            return ["invalid exact date"]
        if precision == "year":
            year = int(t["expression"])
            if t["start"] != f"{year:04}-01-01" or t["end"] != f"{year+1:04}-01-01":
                return ["invalid year bounds"]
        if precision in ("interval", "approximate") and (not start or not end):
            return ["missing finite interval bounds"]
        if precision == "by" and (start is not None or end is None):
            return ["invalid by bound"]
        if precision == "open" and ((start is None) == (end is None)):
            return ["invalid open interval"]
    except (ValueError, TypeError, KeyError):
        return ["invalid temporal expression"]
    return []


def dependency_closure(ref, sources, trail=()):
    if ref in trail:
        raise ValueError("cyclic evidence derivation")
    source = resolve(ref, sources)
    found = {ref}
    for parent in source["derived_from"]:
        found |= dependency_closure(parent, sources, trail + (ref,))
    return found


def semantic_errors(corpus, profile):
    """Call schema_errors first on untrusted structures."""
    errors = []
    records, claims, evidence, sources = tables(corpus, profile)
    entities = {e["id"]: e for e in profile["entities"]}
    assertions = {a["ref"]: a for a in profile["assertions"]}
    decisions = {d["id"]: d for d in profile["decisions"]}
    events = {e["id"]: e for e in profile["events"]}

    def unique(values, label):
        for value, count in Counter(values).items():
            if count > 1:
                errors.append(f"duplicate {label}: {value}")

    def links(values, mapping, label):
        for ref in values:
            if ref not in mapping:
                errors.append(f"missing {label}: {ref}")

    unique([r["record_id"] for r in corpus["records"]], "record")
    for group, key in (("entities", "id"), ("sources", "ref"), ("assertions", "ref"), ("decisions", "id"), ("events", "id")):
        unique([x[key] for x in profile[group]], group)
    for r in corpus["records"]:
        for group, key in (("claims", "claim_id"), ("evidence", "evidence_id"), ("events", "event_id"), ("relationships", "relationship_id"), ("questions_and_answers", "qa_id")):
            unique([x[key] for x in r[group]], r["record_id"] + "/" + group)
            for item in r[group]:
                links([r["record_id"] + "/" + x for x in item.get("evidence_ids", [])], evidence, "evidence")
                links([r["record_id"] + "/" + x for x in item.get("claim_ids", [])], claims, "claim")
        if r["approval"]["state"].startswith("Approved"):
            d = decisions.get(r["approval"].get("decision_id"), {})
            if d.get("scope") != "record" or d.get("target") != r["record_id"]:
                errors.append("inconsistent record decision")
    if set(sources) != set(evidence):
        errors.append("source/evidence identity mismatch")
    for ref, s in sources.items():
        links(s["entities"], entities, "source entity")
        try:
            dependency_closure(ref, sources)
        except ValueError as exc:
            errors.append(str(exc))
        if s["derived_from"] and evidence.get(ref, {}).get("reliability") != "Derived":
            errors.append("derived source cannot claim primary authority")
        if s["disclosure"] == "public" and evidence.get(ref, {}).get("privacy_class") != "Public Demo":
            errors.append("inconsistent source disclosure")

    for a in profile["assertions"]:
        links([a["ref"]], claims, "claim")
        links([a["subject"]], entities, "subject")
        links(a["source_refs"], evidence, "support")
        links(a["derived_from"] + a["conflicts_with"], assertions, "assertion")
        errors.extend(time_errors(a["time"]))
        if a["event"]:
            links([a["event"]], events, "event")
            if a["event"] in events and events[a["event"]]["subject"] != a["subject"]:
                errors.append("event subject mismatch")
        if a["supersedes"]:
            old = assertions.get(a["supersedes"])
            if not old or old["subject"] != a["subject"] or old["predicate"] != a["predicate"] or old["event"] != a["event"] or old["recorded_at"] >= a["recorded_at"]:
                errors.append("inconsistent assertion correction")
        if a["decision_ref"]:
            d = decisions.get(a["decision_ref"], {})
            if d.get("scope") != "claim" or d.get("target") != a["ref"] or d.get("action") != "accept_for_demo" or d.get("recorded_at", "") < a["recorded_at"]:
                errors.append("inconsistent claim decision")
        c = claims.get(a["ref"], {})
        if not a["source_refs"] and c.get("epistemic_state") not in ("Unknown", "Not Applicable"):
            errors.append("non-unknown assertion lacks evidence")
        if a["basis"] in ("account", "quotation", "paraphrase") and c.get("epistemic_state") == "Known":
            errors.append("unsupported epistemic promotion")
        if a["basis"] == "paraphrase" and not a["derived_from"]:
            errors.append("paraphrase lacks derivation")
        if a["basis"] == "quotation" and len(a["source_refs"]) != 1:
            errors.append("quotation requires one exact source")
        kind = entities.get(a["subject"], {}).get("kind")
        if a["predicate"] in ("photograph_date", "digitization_date") and kind != "document":
            errors.append("date assigned to wrong entity role")
        if a["predicate"] == "manufacturing_label" and kind != "observation":
            errors.append("label assigned to wrong entity role")
    # Detect assertion derivation cycles independently of evidence cycles.
    def visit(ref, trail=()):
        if ref in trail:
            return True
        return any(visit(x, trail + (ref,)) for x in assertions.get(ref, {}).get("derived_from", []) if x in assertions)
    if any(visit(ref) for ref in assertions):
        errors.append("cyclic assertion derivation")
    qa = {r["record_id"] + "/" + q["qa_id"]: q for r in records.values() for q in r["questions_and_answers"]}
    for d in profile["decisions"]:
        links([d["target"]], {"claim": claims, "record": records, "qa": qa}[d["scope"]], "decision target")
        if d["simulated"] is not True:
            errors.append("only simulated decisions supported")
    for event in profile["events"]:
        links([event["subject"]], entities, "event subject")
        links(event["source_refs"], evidence, "event evidence")
        errors.extend(time_errors(event["when"]))
    for relation in profile["relations"]:
        links([relation["subject"], relation["object"]], entities, "relation entity")
        links(relation["source_refs"], evidence, "relation support")
    return sorted(set(errors))


def validate(corpus, profile):
    errors = schema_errors(corpus, profile)
    return errors if errors else semantic_errors(corpus, profile)


def simulated_accept(profile, ref, decision_id, recorded_at):
    """Return a new snapshot; no epistemic state, source or record approval changes."""
    if any(d["id"] == decision_id for d in profile["decisions"]):
        raise ValueError("decision ID already exists")
    updated = copy.deepcopy(profile)
    a = next((x for x in updated["assertions"] if x["ref"] == ref), None)
    if a is None or recorded_at < a["recorded_at"]:
        raise ValueError("invalid simulated transition")
    datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
    updated["decisions"].append(dict(id=decision_id, scope="claim", target=ref, action="accept_for_demo", simulated=True, actor="Simulated reviewer", recorded_at=recorded_at))
    a["decision_ref"] = decision_id
    return updated
