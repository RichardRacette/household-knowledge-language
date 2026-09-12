"""Privacy projection and a deterministic structured reader, not an LLM."""
from __future__ import annotations

import copy

from .model import dependency_closure, tables
from .temporal import active_assertions, source_recording_times, time_match, timestamp


def public_view(corpus, profile):
    """Remove restricted dependency closures before index/context construction.

    Disclosure annotations are supplied policy, not inferred from prose. Acknowledgment
    exposes only an explicitly permitted subject/predicate stub, never its value.
    """
    records, claims, evidence, sources = tables(corpus, profile)
    closures = {ref: dependency_closure(ref, sources) for ref in sources}
    blocked = {ref for ref, e in evidence.items() if e["privacy_class"] != "Public Demo" or records[ref.split('/')[0]]["privacy"]["privacy_class"] != "Public Demo" or sources[ref]["disclosure"] != "public"}
    visible = {ref for ref in sources if not (closures[ref] & blocked)}
    kept = {a["ref"] for a in profile["assertions"] if set(a["source_refs"]) <= visible and records[a["ref"].split('/')[0]]["privacy"]["privacy_class"] == "Public Demo"}
    # Assertion ancestry is also a privacy boundary, independently of source links.
    while True:
        next_kept = {a["ref"] for a in profile["assertions"] if a["ref"] in kept and set(a["derived_from"]) <= kept}
        if next_kept == kept:
            break
        kept = next_kept
    acknowledgments = []
    for a in profile["assertions"]:
        if a["ref"] not in kept:
            blockers = set().union(*(closures[x] & blocked for x in a["source_refs"]))
            if blockers and all(sources[x]["disclosure"] == "acknowledge" and records[x.split('/')[0]]["privacy"]["privacy_class"] == "Public Demo" for x in blockers):
                acknowledgments.append({"subject": a["subject"], "predicate": a["predicate"], "mode": "Private"})
    out_corpus = copy.deepcopy(corpus)
    out_corpus["records"] = [r for r in out_corpus["records"] if r["privacy"]["privacy_class"] == "Public Demo"]
    for r in out_corpus["records"]:
        rid = r["record_id"]
        r["evidence"] = [e for e in r["evidence"] if rid + "/" + e["evidence_id"] in visible]
        r["claims"] = [c for c in r["claims"] if rid + "/" + c["claim_id"] in kept]
        r["questions_and_answers"] = []
        for group in ("events", "relationships"):
            r[group] = [x for x in r[group] if all(rid + "/" + e in visible for e in x.get("evidence_ids", []))]
    out_profile = copy.deepcopy(profile)
    out_profile["sources"] = [s for s in out_profile["sources"] if s["ref"] in visible]
    out_profile["assertions"] = [a for a in out_profile["assertions"] if a["ref"] in kept]
    for a in out_profile["assertions"]:
        a["conflicts_with"] = [x for x in a["conflicts_with"] if x in kept]
        if a["supersedes"] not in kept:
            a["supersedes"] = None
    out_profile["decisions"] = [d for d in out_profile["decisions"] if d["scope"] == "claim" and d["target"] in kept]
    out_profile["relations"] = [r for r in out_profile["relations"] if set(r["source_refs"]) <= visible]
    out_profile["events"] = [e for e in out_profile["events"] if set(e["source_refs"]) <= visible]
    event_ids = {e["id"] for e in out_profile["events"]}
    for a in out_profile["assertions"]:
        if a["event"] not in event_ids:
            a["event"] = None
    reached = {a["subject"] for a in out_profile["assertions"]}
    reached |= {x for s in out_profile["sources"] for x in s["entities"]}
    reached |= {x for r in out_profile["relations"] for x in (r["subject"], r["object"])}
    reached |= {e["subject"] for e in out_profile["events"]}
    reached |= {a["subject"] for a in acknowledgments}
    out_profile["entities"] = [e for e in out_profile["entities"] if e["id"] in reached]
    return {"corpus": out_corpus, "profile": out_profile, "acknowledgments": acknowledgments}


def build_plan(view, retrieved_refs, intent):
    """All selected claims require their entire public source closure in context."""
    corpus, profile = view["corpus"], view["profile"]
    _, claims, evidence, sources = tables(corpus, profile)
    available = set(retrieved_refs) & set(evidence)
    as_of = intent.get("as_of")
    if as_of:
        recorded = source_recording_times(profile)
        available = {r for r in available if r in recorded and timestamp(recorded[r]) <= timestamp(as_of)}
    active = active_assertions(profile["assertions"], as_of)
    active_ids = {a["ref"] for a in active}
    candidates = [a for a in active if a["subject"] in intent["subjects"] and a["predicate"] == intent["predicate"]]
    if intent.get("valid_at"):
        candidates = [a for a in candidates if time_match(a["time"], intent["valid_at"])]
    selected = []
    needs_review = False
    decisions = {d["id"]: d for d in profile["decisions"]}
    for a in candidates:
        needed = set().union(*(dependency_closure(r, sources) for r in a["source_refs"]))
        if not needed <= available:
            continue
        decision = decisions.get(a["decision_ref"], {})
        if decision.get("scope") != "claim" or decision.get("target") != a["ref"] or decision.get("simulated") is not True or decision.get("action") != "accept_for_demo" or (as_of and timestamp(decision["recorded_at"]) > timestamp(as_of)):
            needs_review = True
            continue
        c = claims[a["ref"]]
        selected.append({"claim": a["ref"], "subject": a["subject"], "predicate": a["predicate"], "value": a["object"], "attributed_to": a["attributed_to"], "epistemic_state": c["epistemic_state"], "evidence": sorted(needed), "derivation": a["derived_from"], "source_authority": {r: evidence[r]["reliability"] for r in sorted(needed)}, "decision": a["decision_ref"], "decision_simulated": True, "time": a["time"], "conflicts_with": [r for r in a["conflicts_with"] if r in active_ids]})
    withheld = any(x["subject"] in intent["subjects"] and x["predicate"] == intent["predicate"] for x in view["acknowledgments"])
    if needs_review:
        mode = "Needs Human"
    elif not selected:
        mode = "Private" if withheld else "Unknown"
    elif any(x["epistemic_state"] == "Unknown" for x in selected):
        mode = "Unknown"
    elif any(x["epistemic_state"] != "Known" or x["conflicts_with"] for x in selected) or len({x["value"] for x in selected}) > 1:
        mode = "Qualified"
    else:
        mode = "Direct"
    return {"mode": mode, "claims": selected, "withheld": withheld, "reader": "deterministic structured reader; simulated decisions"}


def render(plan):
    lines = [plan["mode"] + "."]
    for c in plan["claims"]:
        period = "" if c["time"] is None else f"; source time: {c['time']['expression']} ({c['time']['precision']})"
        lines.append(f"According to {c['attributed_to']} [{c['epistemic_state']}], {c['predicate']}: {c['value']}{period}. Evidence: {', '.join(c['evidence']) or 'explicit knowledge gap'}. Decision: {c['decision']} (simulated).")
    if plan["withheld"]:
        lines.append("Supporting information is restricted; contents withheld.")
    if not plan["claims"] and plan["mode"] == "Unknown":
        lines.append("Available public evidence does not support an answer to this structured request.")
    return "\n".join(lines)
