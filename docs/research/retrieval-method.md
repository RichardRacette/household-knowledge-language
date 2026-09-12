# Retrieval protocol v1

Fixed before the first development comparison; question/expectation freeze is commit
`1a6a1ce`. The six holdout questions remain visible to the author but are excluded
from development runs. There is no claim of blinding or statistical independence.

Every index contains the same public source units: record title/aliases plus evidence
name and observation. It omits claims' prose, prepared Q&A, questions, gold answers
and expected support. All variants expand query vocabulary with the same caller-supplied
subject labels. The structured intent (subjects, predicate, optional valid_at/as_of)
is caller supplied; natural-language intent parsing is outside the study.

Direct retrieval uses BM25 (k1=1.2, b=0.75), fixed stopwords and record-qualified
lexical tie-breaking. Entity retrieval adds source/entity adjacency (+2) and one
entity-relation hop (+1). Event-aware retrieval additionally indexes temporal
assertions and physical events. Active matching temporal assertions add +4 to their
sources; a matching physical event adds +0.5. A later recording-time correction
changes the active temporal index view without deleting earlier assertions.
No weight is fitted to the questions. At most four unique evidence units enter the
shared reader, including derivation ancestors; a missing ancestor prevents selection.

The reader checks exact structured subject/predicate eligibility, source closure,
recording time, source availability, valid time and scoped simulated acceptance. Source
availability uses the earliest recorded assertion referencing that source; capture date
is not ingestion time. Sources without a recorded assertion have unknown availability
and are omitted for as-of retrieval in every variant. Explicit source-ingest timestamps
are a future profile extension. It never
reads gold. Rendering simply exposes the plan. The evaluator then compares it with
frozen evidence, claim IDs and modes. Attribution measures preservation of supplied
attribution metadata, not verification of the speaker or source's truth. Unsupported
selection means a selected claim outside the expected set, lacking retrieved support,
or citing evidence outside the expected supporting set. A complete plan must match mode,
claim IDs and the entire expected supporting-evidence set;
this is not a natural-language entailment metric. Missing supported claims remain failures
of complete-plan recovery even when abstention is safe.

Raw rows include question/split, retrieved IDs/scores, bounded plan, rendered text,
support hits/gold, attribution correct/selected, unsupported/selected, correct/required
abstentions, complete plans/queries and disclosure-failure counts. Empty-gold coverage
is null, never an invented perfect score. Report micro coverage and split denominators.
Single-run construction time, per-query time, nodes, edges and serialized index bytes
are measured; tiny timings are descriptive and machine-dependent. No tokens, model
costs, human annotation labor or general scalability are measured.

Controls remove the bird's actual possession source while retaining another record's
EVID-001, and inject prepared-Q&A canaries to check index exclusion. Regression tests
also change source text and require retrieval to respond. Safety gates fail on disclosure,
unsupported selected claims or failed controls; retrieval misses and weak graph gains
remain reportable research outcomes. Development commands explicitly specify
`--split development`; the documented reproduction/CI default `run` executes the final
comparison over all questions. The first all-question run happens only after defect review.
