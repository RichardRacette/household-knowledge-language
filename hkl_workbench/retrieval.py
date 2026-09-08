"""Three disposable local indexes over exactly the same public evidence units.

No prepared Q&A, question set, expected answer or gold evidence is accepted by the
constructor. Manual entity/time annotations incur real construction complexity;
these experiments do not measure the labor of acquiring those annotations.
"""
from collections import Counter, defaultdict
import math
import re
from time import perf_counter_ns

from .common import json_bytes
from .model import tables
from .temporal import active_assertions, source_recording_times, time_match, timestamp

MODES = ("direct", "entity", "event")
BUDGET = 4
STOP = set("a an the of for to from in on by as is was were are it its did does do what which who when where how and or with at after during be have has had that this about can we".split())


def tokens(text):
    return [x for x in re.findall(r"[a-z0-9]+", text.casefold()) if x not in STOP]


class Index:
    def __init__(self, view, mode):
        if mode not in MODES:
            raise ValueError("unknown retrieval mode")
        start = perf_counter_ns()
        self.mode = mode
        records, _, evidence, sources = tables(view["corpus"], view["profile"])
        recorded = source_recording_times(view["profile"])
        self.units = {}
        for ref, e in evidence.items():
            r = records[ref.split("/")[0]]
            text = " ".join([r["title"], *r["identity"].get("aliases", []), e["source_name"], e.get("excerpt_or_observation") or ""])
            self.units[ref] = {"ref": ref, "text": text, "recorded_at": recorded.get(ref)}
        self.term_counts = {ref: Counter(tokens(u["text"])) for ref, u in self.units.items()}
        self.df = Counter(t for count in self.term_counts.values() for t in count)
        self.avg_len = sum(sum(c.values()) for c in self.term_counts.values()) / max(len(self.units), 1)
        # Identical query vocabulary expansion is available to every variant.
        self.labels = {e["id"]: " ".join([e["label"], *e["aliases"]]) for e in view["profile"]["entities"]}
        self.entity_sources = defaultdict(set)
        self.neighbors = defaultdict(set)
        self.temporal = []
        self.events = []
        if mode in ("entity", "event"):
            for ref, s in sources.items():
                for entity in s["entities"]:
                    self.entity_sources[entity].add(ref)
            for relation in view["profile"]["relations"]:
                self.neighbors[relation["subject"]].add(relation["object"])
                self.neighbors[relation["object"]].add(relation["subject"])
        if mode == "event":
            # Event-aware indexing includes assertion valid time and recording time.
            for a in view["profile"]["assertions"]:
                if a["time"] is not None:
                    self.temporal.append({k: a[k] for k in ("ref", "subject", "predicate", "source_refs", "time", "recorded_at", "supersedes", "event")})
            self.events = view["profile"]["events"]
        self.stats = {
            "source_units": len(self.units),
            "nodes": len(self.units) + len(self.entity_sources) + len(self.temporal) + len(self.events),
            "edges": sum(map(len, self.entity_sources.values())) + sum(map(len, self.neighbors.values())) + sum(len(a["source_refs"]) + 1 + bool(a["event"]) for a in self.temporal) + sum(len(e["source_refs"]) + 1 for e in self.events),
        }
        serializable = {"units": self.units, "labels": self.labels, "terms": {k: dict(v) for k, v in self.term_counts.items()}, "entity_sources": {k: sorted(v) for k, v in self.entity_sources.items()}, "neighbors": {k: sorted(v) for k, v in self.neighbors.items()}, "temporal": self.temporal, "events": self.events}
        self.stats["serialized_index_bytes"] = len(json_bytes(serializable))
        self.stats["construction_ms"] = (perf_counter_ns() - start) / 1e6

    def query(self, text, intent, budget=BUDGET):
        start = perf_counter_ns()
        terms = set(tokens(text + " " + " ".join(self.labels.get(s, "") for s in intent["subjects"])))
        scores = {}
        n = len(self.units)
        for ref, counts in self.term_counts.items():
            unit = self.units[ref]
            if intent.get("as_of") and (unit["recorded_at"] is None or timestamp(unit["recorded_at"]) > timestamp(intent["as_of"])):
                continue
            length = sum(counts.values())
            scores[ref] = sum(math.log(1 + (n - self.df[t] + .5) / (self.df[t] + .5)) * (counts[t] * 2.2) / (counts[t] + 1.2 * (.25 + .75 * length / max(self.avg_len, 1))) for t in terms if counts[t])
        if self.mode in ("entity", "event"):
            # Fixed weights and one-hop traversal, frozen before the first comparison.
            for subject in intent["subjects"]:
                for ref in self.entity_sources.get(subject, []):
                    if ref in scores:
                        scores[ref] += 2.0
                for neighbor in self.neighbors.get(subject, []):
                    for ref in self.entity_sources.get(neighbor, []):
                        if ref in scores:
                            scores[ref] += 1.0
        if self.mode == "event" and (intent.get("valid_at") or intent.get("as_of")):
            for a in active_assertions(self.temporal, intent.get("as_of")):
                if a["subject"] in intent["subjects"] and a["predicate"] == intent["predicate"] and (not intent.get("valid_at") or time_match(a["time"], intent["valid_at"])):
                    for ref in a["source_refs"]:
                        if ref in scores:
                            scores[ref] += 4.0
            # Explicit event adjacency adds a smaller boost to associated sources.
            for event in self.events:
                if event["subject"] in intent["subjects"] and intent.get("valid_at") and time_match(event["when"], intent["valid_at"]):
                    for ref in event["source_refs"]:
                        if ref in scores:
                            scores[ref] += .5
        refs = sorted((r for r in scores if scores[r] > 0), key=lambda r: (-scores[r], r))[:budget]
        return {"refs": refs, "scores": [round(scores[r], 6) for r in refs], "query_ms": (perf_counter_ns() - start) / 1e6}
