# Findings: fictional offline workbench v1

The additional retrieval graphs did not improve evidence coverage or complete answer
plans on this corpus. Explicit provenance, temporal assertions, typed roles and public
packet checks did provide inspectable behavior absent from the original schema validator.
These conclusions apply to the public experimental profile; they change no private archive.

## Evidence and execution

The baseline was `e5391af4905f1c615e1b34c51692b02fd817cb21`: seven schema tests and all
three original example validations passed. The original validator enforced structure and
formats, with no executable reference, disclosure, decision or temporal semantics.
[Baseline receipt](baseline.json) and [source traceability](sources.md) separate this
observation from the papers' findings and our implementation hypotheses.

The final run executed clean implementation commit
[`aefc9cab5cabc808af21ec70193b9497baa3b490`](https://github.com/RichardRacette/household-knowledge-language/commit/aefc9cab5cabc808af21ec70193b9497baa3b490)
at `2026-09-08T05:35:09.671103+00:00`, in a fresh local Git clone and fresh Python 3.14.7
environment on Windows. Pinned dependencies installed from previously downloaded wheels
with `--no-index`. All 27 discovered tests, three unchanged example validations, the full
runner and packet verification passed. A Windows sandbox account required trust scoped
to this newly created checkout; no global Git settings changed.
The implementation's [Python 3.12 GitHub Actions run also passed](https://github.com/RichardRacette/household-knowledge-language/actions/runs/34191223243).

[Raw results](../../research/results/final.json) contain actual code-file hashes,
schema/profile and frozen-fixture hashes, dependency versions, exact command and dirty
status (`false`). [Fresh-checkout receipt](../../research/results/fresh-checkout.json)
records the other commands. The results and packet are published by a later report-only
commit and are evidence for the named implementation revision, not a relabeled later run.
The [reproduction guide](reproduction.md) gives the complete command path.

Fixtures remained unchanged after their freeze in `1a6a1ce`: 12 records, 32 authored
source files and 24 questions (18 development, six holdout). The final all-question run
followed defect review. Holdout questions were visible to the author but never evaluated
in development; this was not a blinded experiment. Neither weights nor gold changed
after seeing the final results.

## Results and recommendations

| Track | Observed result | Recommendation and scope |
|---|---|---|
| E1: provenance and acceptance | 32/32 experiment checks. Exact quotation remains Reported; confidence .99, repetition and recency retain derivation. Eight structurally valid invalid cases fail semantic checks. Scoped simulated acceptance changes Needs Human to Qualified while preserving attribution/history. Restricted dependency content is removed before context. | **ADOPT IN PUBLIC WORKBENCH**: qualified IDs, explicit derivation, decision scope and public projection. These check supplied metadata, not factual truth or reviewer identity. |
| E2: temporal assertions | 16/16 checks, including six historical queries. The corrected May 2024 move exposes a gap; a late attic recollection preserves overlap. Recording-time queries retain the earlier view. Year/approximate/exact/open expressions survive; four invalid temporal/correction cases fail. | **ADOPT IN PUBLIC WORKBENCH**: minimal valid-time/recorded-time assertions linked to a single physical event. Defer temporal NLP, recurrence expansion and RDF reasoning. |
| E3: portable preservation | 40/40 checks: five recovery/privacy checks and 35 rejected corruptions. The 46,404-byte sample ZIP recovers 29 public synthetic sources in 43 manifest-listed payload files. A fresh process denies original-path and network access, verifies hashes/links/history, and recovers the quotation's speaker and Reported state. | **ADOPT IN PUBLIC WORKBENCH**: bounded packet 1.0 and documented RO-Crate 1.2 subset. No OAIS certification, full RO-Crate conformance, authenticated origin or human usability result. |
| E4: entity distinctions | 11/11 checks: eight answer-plan demonstrations and three rejected role/reference mutations. Object, photograph, inscription observation and account stay distinct. Manufacturing label, image dates, proximity and missing inventory do not establish the requested unsupported facts; conflicting meanings remain attributed. | **ADOPT IN PUBLIC WORKBENCH**: typed roles and exact subject/predicate eligibility. Arbitrary natural-language entailment and a full heritage ontology remain deferred. |
| E5: retrieval cost/benefit | All three variants tie: 20/23 required evidence occurrences recovered, 21/24 complete plans, 20/20 selected attributions preserved, 9/9 required abstentions, 0/20 unsupported selections and 0/24 disclosure failures. Six source-removal/collision/Q&A-exclusion controls pass. | **ADOPT IN PUBLIC WORKBENCH** the direct baseline and comparative harness; **DEFER** making a graph variant the default. Retain graphs as experimental comparators because their added structure earned no quality gain here. |

Check counts include related positive and negative probes; they are not independent
observations or statistical confidence estimates. A passing safety gate does not make
a missed supported answer successful.

The existing schema can retain source date expressions and textual recurrence, both
demonstrated in E2. Its current-area field and free-text events cannot structurally answer
the six interval/as-of/correction queries without additional interpretation. The sidecar
supplies that machinery while preserving the original records and schema. Source
availability currently uses the earliest recorded assertion that references a source;
capture date is not ingestion time. Independent source-ingestion timestamps remain absent.

The [packet](../../research/artifacts/fictional-public-packet.zip) includes real synthetic
text bytes, versioned schemas, qualified lineage, simulated decisions, public baseline
snapshots, software receipts, RO-Crate input/result actions and a standard-library reader.
Corruptions cover absent/changed files, rehashed broken links, cycles, duplicate identities,
decision action/time, fixture/software inconsistencies, missing earlier history, unsupported
versions and unsafe paths. Separate regression tests reject ZIP case aliases/symlinks and
show a restricted original record cannot leak through a history snapshot. The reader's
README enumerates its subset; it does not run full JSON Schema or JSON-LD validation.

## Retrieval comparison

All variants use the same 29 public source units, caller-supplied structured intent,
maximum four evidence units, visibility rules and deterministic reader/renderer.
The [fixed protocol](retrieval-method.md) describes BM25, entity adjacency and event boosts.
Question/gold data and prepared Q&A are excluded from every index. Construction annotations
are manually authored and shared; the canonical corpus does not depend on an index.

| Mode | Development evidence / complete plans | Holdout evidence / complete plans | Index nodes / edges | Serialized bytes | Construction ms | Median query ms |
|---|---|---|---|---:|---:|---:|
| Direct | 15/18; 15/18 | 5/5; 6/6 | 29 / 0 | 19,161 | 0.8423 | 0.1023 |
| Entity | 15/18; 15/18 | 5/5; 6/6 | 40 / 47 | 20,835 | 3.2565 | 0.0997 |
| Event-aware | 15/18; 15/18 | 5/5; 6/6 | 51 / 72 | 25,309 | 1.1440 | 0.1108 |

Evidence denominators count required source occurrences across questions; questions with
no gold evidence have null case coverage. Serialized entity/event indexes are about 8.7%
and 32.1% larger than direct. Timings are single-run descriptive measurements, too small
and noisy to establish a reliable speed ranking. No annotation labor, tokens, model usage,
cost in dollars or general scalability was measured. This is not an LLM benchmark and
does not reproduce or compare scores with the [VLDB workshop study](sources.md).

All modes retain the same three failures:

| Case | Missing support and consequence |
|---|---|
| Q03: exact Elena quotation | `OBJ-0004/EVID-001` is absent from the top four; plan is Unknown instead of Qualified. |
| Q05: paraphrase of Elena's account | The derivative is retrieved, but its original `OBJ-0004/EVID-001` is absent; the closure requirement prevents selection. |
| Q14: missing annual ornament year | `COLLECTION-0001/EVID-001` is absent from the top four; plan is Unknown instead of Direct. |

These failures remain in the raw per-case results. E1 can construct the quoted/paraphrased
plans when complete source context is supplied; E5 shows that this does not ensure the
retriever supplies that context. No budget or expected answer was changed to hide the misses.

## Limits and next milestone

The strongest finding is a useful distinction: explicit provenance and temporal contracts
support auditable behavior, while extra retrieval graph structure produced no measured
quality benefit here. A temporal projection can justify itself for historical queries
without justifying an event-aware retrieval default.

The most important unresolved limitation is the tiny, manually annotated, author-visible
corpus and supplied structured intent. It cannot establish household usability, production
readiness, general privacy protection, prose truth, genuine human approval, preservation
usability or superiority over published systems. Disclosure follows supplied record/source
policy, with no automatic classification of prose; omitting a source does not retract an
independently public object's identity. All review decisions are explicitly simulated.

The next single milestone is an independently authored, frozen fictional replication set
focused on quotation lineage and missing-inventory retrieval, evaluated with the same
four-source budget before changing retrieval defaults. That would test whether the three
misses and lack of graph benefit persist outside the author's original examples.
