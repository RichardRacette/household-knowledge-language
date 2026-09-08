"""Gold is loaded only here, after disposable retrieval indexes are built."""
import copy
import statistics

from .answers import build_plan, public_view, render
from .common import FIXTURES, json_bytes, read_json
from .retrieval import BUDGET, MODES, Index


def evaluate_case(view, index, question):
    query = index.query(question["text"], question["intent"])
    plan = build_plan(view, query["refs"], question["intent"])
    gold = set(question["expected_evidence"])
    chosen = plan["claims"]
    assertions = {a["ref"]: a for a in view["profile"]["assertions"]}
    expected_claims = set(question["expected_claims"])
    selected_refs = {x["claim"] for x in chosen}
    attribution_correct = sum(c["attributed_to"] == assertions[c["claim"]]["attributed_to"] for c in chosen)
    unsupported = sum(c["claim"] not in expected_claims or not set(c["evidence"]) <= set(query["refs"]) or not set(c["evidence"]) <= gold for c in chosen)
    requires_abstention = question["expected_mode"] in ("Unknown", "Private", "Needs Human")
    text = render(plan)
    return {"id": question["id"], "split": question["split"], "question": question["text"], "intent": question["intent"], "retrieval": query, "plan": plan, "rendered": text,
            "evidence_hits": len(set(query["refs"]) & gold), "gold_evidence_count": len(gold), "expected_evidence": sorted(gold),
            "selected_claims": len(chosen), "correct_attribution": attribution_correct, "unsupported_selected": unsupported,
            "requires_abstention": requires_abstention, "correct_abstention": requires_abstention and plan["mode"] == question["expected_mode"] and unsupported == 0,
            "expected_mode": question["expected_mode"], "expected_claims": sorted(expected_claims),
            "complete_plan_correct": plan["mode"] == question["expected_mode"] and selected_refs == expected_claims and set().union(*(set(c["evidence"]) for c in chosen)) == gold,
            "disclosure_failure": b"ORCHID-482" in json_bytes({"query": query, "plan": plan, "text": text}) or any(r not in index.units for r in query["refs"])}


def aggregate(rows):
    def total(key):
        return sum(r[key] for r in rows)
    hits, gold = total("evidence_hits"), total("gold_evidence_count")
    selected = total("selected_claims")
    abstentions = total("requires_abstention")
    return {"queries": len(rows), "evidence_coverage": {"hits": hits, "gold": gold, "ratio": hits/gold if gold else None},
            "correct_attribution": {"correct": total("correct_attribution"), "selected": selected},
            "unsupported_selection": {"unsupported": total("unsupported_selected"), "selected": selected},
            "correct_abstention": {"correct": total("correct_abstention"), "required": abstentions},
            "complete_plan_correct": {"correct": total("complete_plan_correct"), "queries": len(rows)},
            "disclosure_failures": {"failures": total("disclosure_failure"), "queries": len(rows)},
            "median_query_ms": statistics.median(r["retrieval"]["query_ms"] for r in rows)}


def e5(corpus, profile, split="all"):
    view = public_view(corpus, profile)
    indexes = {mode: Index(view, mode) for mode in MODES}
    questions = read_json(FIXTURES / "questions.json")["questions"]
    questions = [q for q in questions if split == "all" or q["split"] == split]
    variants = {}
    for mode, index in indexes.items():
        rows = [evaluate_case(view, index, q) for q in questions]
        variants[mode] = {"construction": index.stats, "aggregate": aggregate(rows), "splits": {s: aggregate([r for r in rows if r["split"] == s]) for s in ("development", "holdout") if any(r["split"] == s for r in rows)}, "cases": rows}
    controls = []
    # Remove the actual source and its metadata from the view; another EVID-001 remains.
    removed_view = copy.deepcopy(view)
    removed = "OBJ-0001/EVID-001"
    for r in removed_view["corpus"]["records"]:
        if r["record_id"] == "OBJ-0001":
            r["evidence"] = [e for e in r["evidence"] if e["evidence_id"] != "EVID-001"]
    removed_view["profile"]["sources"] = [s for s in removed_view["profile"]["sources"] if s["ref"] != removed]
    removed_view["profile"]["assertions"] = [a for a in removed_view["profile"]["assertions"] if removed not in a["source_refs"]]
    probe = {"text": "Who possessed the blue ceramic bird by 1991?", "intent": {"subjects": ["bird"], "predicate": "possessed_by"}}
    for mode in MODES:
        index = Index(removed_view, mode)
        retrieved = index.query(probe["text"], probe["intent"])
        plan = build_plan(removed_view, retrieved["refs"], probe["intent"])
        controls.append({"case": "source removal and same-local-ID decoy", "mode": mode, "removed": removed, "decoy_present": "OBJ-0004/EVID-001" in index.units, "retrieved": retrieved["refs"], "plan": plan, "passed": not plan["claims"] and removed not in retrieved["refs"] and "OBJ-0004/EVID-001" in index.units})
        altered = copy.deepcopy(view)
        for r in altered["corpus"]["records"]:
            r["questions_and_answers"] = [{"question": "LEAK-CANARY", "answer": "GOLD-ANSWER-CANARY"}]
        other = Index(altered, mode)
        controls.append({"case": "prepared Q&A excluded from index", "mode": mode, "passed": other.units == indexes[mode].units and b"CANARY" not in json_bytes(other.units)})
    return {"study": "Synthetic evidence retrieval and deterministic answer-plan comparison; not an LLM benchmark.", "split": split, "budget_evidence_units": BUDGET, "tokens": None, "token_note": "No tokenizer or hosted-model calls measured; no token estimate reported.", "construction_effort": "Source units, graph nodes/edges and serialized index bytes measured. Human annotation labor and authoring-token cost unmeasured; annotation data shared across variants.", "variants": variants, "controls": controls}
