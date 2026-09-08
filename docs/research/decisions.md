# Architecture decisions for the public workbench

These decisions apply only to the public research workbench. They adopt no private
archive policy or canonical household conclusion.

## Keep the public record schema stable

The legacy schema can hold claim states, confidence, evidence IDs, free-text events,
privacy labels and approval metadata. It cannot enforce cross-field references, distinguish
recording time from event time, or authenticate approval. A separate profile 1.0 supplies
explicit structured assertions, typed entity IDs, qualified references, simulated decisions,
derivation and temporal scopes. The original three files and their validator stay supported.
Only mapped assertions enter the deterministic reader; unmapped legacy prose is not silently
converted into executable truth. Existing tests remain schema tests.

## Distinguish acceptance, attribution and source authority

ADOPT IN PUBLIC WORKBENCH: use immutable decision records and new snapshots for simulated
acceptance. Decisions have a target and scope. A QA decision does not approve a claim or
parent record. Acceptance does not change epistemic state, confidence, original source,
privacy or the legacy approval block. A decision ID is a reference, not a signature or
proof that its named actor is a human. No real household transition API is implemented.

## Represent source time and assertion time separately

ADOPT IN PUBLIC WORKBENCH: preserve source expression/precision alongside query bounds and
recorded_at. Later assertions can explicitly supersede earlier ones for an as-of view;
earlier claims and physical event IDs remain. Intervals are half-open except exact point
dates. Approximate and year bounds are possible ranges, not exact January 1 events or
probability distributions. Conflicting location intervals return an overlap, empty spans a
gap. A location log correction does not synthesize another move. DEFER recurring calendar
rules, free-text temporal parsing and RDF/ontology reasoning.

## Use a conceptual heritage crosswalk, with no ontology conformance claim

| Workbench role | Paper's heritage concept family | Boundary exercised |
|---|---|---|
| physical_object (bird, stone, key, ornament) | Material heritage entity in the CIDOC CRM ecosystem | The object is distinct from representations of it. |
| document (photograph, letter) | Documentary dimension of a heritage digital twin; digital provenance context | Photo and digitization dates date documentation, not the physical object. |
| observation (manufacturing label inspection) | Scientific/inspection observation; CRMsci concept family | A manufacturing inscription is not geological material analysis. |
| account and attributed Meaning assertions | Interpretive knowledge with source/actor context | Two people can assign different meanings without automatic settlement. |
| event and temporal assertion | Event-based biography and change of descriptions | Correction and physical change are separate. |
| composite and collection | Part/whole and contextual relationships | Proximity does not imply shared origin; absent inventory does not prove nonexistence. |

This is a small conceptual mapping to the [accessible manuscript, sections 4.1–4.2](https://www.preprints.org/manuscript/202507.1673),
not a formal mapping to exact CIDOC classes. Expert interpretive alignment remains outside
automated validation. ADOPT IN PUBLIC WORKBENCH: the typed roles and exact structured
subject/predicate answer boundary. DEFER full digital twins and arbitrary prose entailment.

## Preserve a bounded public packet

ADOPT IN PUBLIC WORKBENCH: explicit recovery objectives, qualified link graphs, source-byte
hashes, versioned profiles, retained earlier snapshots and a standalone reader. Public
projection happens before indexing and export, including transitive source and assertion
derivation restrictions. A policy-approved stub may acknowledge restricted support; no
restricted source name, value or bytes enters its stub. No private-view fallback exists.
Original snapshots in a public packet are labeled public projections; full unfiltered original
bytes remain only in the fictional fixture corpus. This preserves disclosure scope honestly.

The standalone verifier implements only the enumerated packet/RO-Crate subset in its README.
Checksums provide fixity against a manifest, not authenticated origins or resistance to an
attacker replacing the manifest. No full JSON-LD reasoning, OAIS certification, long-term
storage service, authenticated reviewer, or human reader study is claimed.

## Keep retrieval disposable

The canonical corpus/profile is independent of all three indexes. Every variant uses the
same public sources, budget and deterministic reader. Node/edge counts and index bytes make
construction complexity visible; measured wall times do not estimate annotation labor.
Development results show equal evidence coverage and complete-plan counts for all modes.
DEFER adopting the additional entity/event indexes as the default until a broader corpus
demonstrates a benefit. Retain them as experimental comparators. The explicit temporal
projection remains useful for semantic queries even when an event retrieval index adds no
measured retrieval benefit. Final recommendations and their denominators appear in findings.md.

## Scope refinements from adversarial review

Direct assertion source_refs must match the record’s qualified local evidence_ids. Cross-record lineage is expressed through explicit assertion/source derivation, whose support must resolve; appending an unrelated cross-record source is rejected. Known assertions in this experimental profile require Primary-only support; this structural policy does not prove source content true.

Source disclosure=omit removes that evidence’s names, contents and acknowledgment stub. Object identity can remain independently Public Demo in its record or another public source. To withhold the record identity, restrict the record itself; unreachable profile entity metadata is removed. This is an explicit policy boundary, not automatic privacy classification of prose.

As-of evidence availability uses the earliest recorded supporting assertion. Capture dates do not establish ingestion time; standalone ingest timestamps and availability of otherwise unreferenced sources remain unresolved.

The detached verifier independently checks qualified/local links across claims, sources, entities, events and relations; duplicate identities; acyclic lineage; every decision's action/time; and the earlier simulated-decision snapshot. Public baseline history is required for retained baseline records and omitted for restricted ones. Software and fixture-origin receipts must agree with packet metadata. Rehashed corruption probes isolate these checks from byte integrity. The complete-plan retrieval metric requires the expected support set as well as mode and claim IDs. These fixes changed implementation checks, not the frozen corpus or gold questions.
