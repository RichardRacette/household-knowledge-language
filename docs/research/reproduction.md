# Reproduce the offline research workbench

Use Python 3.12 or later. GitHub Actions tests Python 3.12; local execution receipts
identify the actual interpreter and dependency versions. No service, credential,
hosted model, cloud database or real household input is needed.

From a fresh checkout of the PR branch:

```bash
git clone --branch research/offline-workbench https://github.com/RichardRacette/household-knowledge-language.git
cd household-knowledge-language
python -m pip install -r requirements-research.txt
python -m unittest discover -v
python validate_record.py ceramic_bird.json
python validate_record.py composite_memory_shelf.json
python validate_record.py annual_ornament_collection.json
python -m hkl_workbench run --output work/reproduction
python -m hkl_workbench verify-packet --packet work/reproduction/packet
```

Installation can use an existing virtual environment. To prepare an offline machine,
download the pinned wheels on a compatible Python/platform first:

```bash
python -m pip download -r requirements-research.txt --dest work/wheels
python -m pip install --no-index --find-links work/wheels -r requirements-research.txt
```

Everything after dependency installation runs offline. Outputs must be new directories
to prevent overwriting run evidence. `slice` runs E1/E3; `run --split development` leaves
out the six holdout questions. `run` executes all five tracks and both retrieval splits.

## Inspect the published packet

```bash
python -m hkl_workbench unpack --archive research/artifacts/fictional-public-packet.zip --output work/published-packet
python -I -S work/published-packet/read_packet.py work/published-packet --isolated
```

The second command requires only the standard library, not this repository's imports.
Copy the extracted packet elsewhere and run its `read_packet.py` there. The `--isolated`
mode denies network access and file access outside the packet, probes those restrictions,
then reconstructs source identities, byte integrity, lineage and a quotation's uncertainty.
Packet documentation enumerates the implemented RO-Crate 1.2 subset and its limitations.
Never execute an untrusted reader script merely because its own manifest validates it.

## What to inspect

- `research/fixtures/v1/manifest.json`: frozen inputs and SHA-256 hashes.
- `research/fixtures/v1/questions.json`: 18 development and six holdout questions, gold evidence, claim IDs and outcome modes; never indexed.
- `research/results/final.json`: per-track checks, corruption results, bounded retrieval rows, all denominators and the producing revision/dirty state/hashes.
- `research/artifacts/fictional-public-packet.zip`: synthetic bytes, records, earlier public snapshots, versioned schemas, simulated decisions, software information and standalone reader.
- `docs/research/sources.md`, `contract.md`, `retrieval-method.md`, `decisions.md`, and `findings.md`: scope, hypotheses, methods, observations and recommendations.

Timings, timestamps, platform strings, Git revision and packet metadata naturally differ
between runs. Fixture hashes, identifiers and behavioral outcomes should agree. A report-only
commit publishes results of the named implementation revision; it does not relabel those
results as execution of later code. Dirty runs identify exact file hashes as well as Git HEAD.

Schema conformance, semantic reference checks, exact-source recovery, answer eligibility,
retrieval performance, recorded simulated decisions and actual human validation are separate.
Only the first six have automated demonstrations here; no actual human validation is claimed.
