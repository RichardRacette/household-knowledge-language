"""Export the fixed public packet profile; no private-view fallback."""
import copy
import stat
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .answers import public_view
from .common import FIXTURES, ROOT, digest, read_json, safe_path, write_json
from .packet_reader import verify

PACKET_README = """# Fictional HKL public evidence packet

Every household, source file and review decision in this packet is fictional.
Sources are authored UTF-8 descriptions, not actual photographs or historical documents.
This public view omits restricted source bytes and every derivative depending on them.
There is no fallback source location. policy.json carries permitted evidence-existence
stubs only. Evidence omission does not retract independently Public Demo object metadata;
record privacy must be Restricted to withhold that record's identity. An independently
public source can still describe the same object. Unreachable profile entities are removed.

Run `python -I -S read_packet.py . --isolated` from this directory. No installation,
network, original repository or account is required. The standalone reader checks the
enumerated HKL packet 1.0 subset: complete file inventory and hashes, safe paths,
supported versions, qualified/local references, acyclic derivations, simulated decision
actions/times/links and the retained earlier snapshot, RO-Crate 1.2 root/descriptor
fields, local graph links, curation inputs and software receipt/version consistency.
The three baseline record snapshots are required while their record remains public;
an omitted record's baseline snapshot must also be absent. Fixture-origin receipts agree.
It does not run JSON-LD expansion, full JSON Schema validation, ontology reasoning,
signature authentication, or full RO-Crate compliance testing.

Preservation objectives: recover source bytes; follow source/derivation/decision
links; interpret recorded uncertainty without hidden context. Hashes detect changes
against this manifest, not an attacker who replaces both files and manifest.

corpus.json contains public records; profile.json connects assertions to typed subjects,
source references and decisions. IDs before `/` qualify the record; local IDs must not
be merged. Known is a recorded state, not a proof of truth. Reported remains attributed;
Unknown records a gap. A precisely copied quotation can still be Reported. Simulated
acceptance permits a demonstration plan; it authenticates nobody and approves no family
record. Numeric confidence, repetition and timestamps do not upgrade authority.

Intervals retain expression and precision. Start is inclusive and end exclusive except
an exact date, whose equal bounds indicate a point. Year bounds are search bounds only.
Approximate bounds give possibilities, not probabilities. Open/by bounds do not invent
missing dates. recorded_at dates an assertion; supersedes changes an assertion view,
not the physical event. Earlier assertions and the earlier simulated decision snapshot
remain in history/. Original record snapshots there are explicitly public projections:
their bytes are not claimed to be the original unfiltered repository files.

Reader exercise: inspect the quotation assertion, find its qualified source file, identify
its speaker and epistemic state, and follow its simulated decision. The automated reader
demonstrates these lookups. No human reader study or preservation certification occurred.
LICENSE retains the repository's MIT license. software.json identifies producing code.
"""


def export_packet(corpus, profile, destination, receipt, fixture_dir=FIXTURES):
    destination = Path(destination)
    if destination.exists():
        raise ValueError("packet destination must be new")
    view = public_view(corpus, profile)
    destination.mkdir(parents=True)
    write_json(destination / "corpus.json", view["corpus"])
    write_json(destination / "profile.json", view["profile"])
    write_json(destination / "policy.json", {"view": "public", "restricted_content": "omitted including transitive derivatives", "acknowledgments": view["acknowledgments"]})
    for s in view["profile"]["sources"]:
        src, dest = safe_path(fixture_dir, s["path"]), safe_path(destination, s["path"])
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
    write_json(destination / "software.json", receipt)
    for src, name in ((ROOT / "household_record.schema.json", "household_record.schema.json"), (ROOT / "hkl_workbench/profile.schema.json", "profile.schema.json"), (ROOT / "LICENSE", "LICENSE"), (ROOT / "hkl_workbench/packet_reader.py", "read_packet.py")):
        (destination / name).write_bytes(src.read_bytes())
    (destination / "README.md").write_text(PACKET_README, encoding="utf-8", newline="\n")
    # A real simulated transition used in E1 is retained as two snapshots, never overwritten.
    before = copy.deepcopy(view["profile"])
    quote = next(a for a in before["assertions"] if a["basis"] == "quotation")
    removed = quote["decision_ref"]
    quote["decision_ref"] = None
    before["decisions"] = [d for d in before["decisions"] if d["id"] != removed]
    write_json(destination / "history/profile-before-simulated-decision.json", before)
    for path in sorted((fixture_dir / "originals").glob("*.json")):
        original = read_json(path)
        rid = original["record_id"]
        if rid not in {r["record_id"] for r in view["corpus"]["records"]}:
            continue
        permitted = {s["ref"] for s in view["profile"]["sources"]}
        original["evidence"] = [e for e in original["evidence"] if rid + "/" + e["evidence_id"] in permitted]
        original["questions_and_answers"] = []
        for group in ("claims", "events", "relationships"):
            original[group] = [x for x in original[group] if all(rid + "/" + e in permitted for e in x.get("evidence_ids", []))]
        write_json(destination / "history" / path.name, original)
    payload = sorted(p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file())
    ident = lambda name: {"@id": name}
    graph = [
        {"@id": "ro-crate-metadata.json", "@type": "CreativeWork", "about": ident("./"), "conformsTo": ident("https://w3id.org/ro/crate/1.2")},
        {"@id": "./", "@type": "Dataset", "name": "Fictional HKL public evidence packet", "description": "Bounded recovery of bytes, lineage and uncertainty; all decisions simulated.", "datePublished": datetime.now(timezone.utc).date().isoformat(), "license": ident("LICENSE"), "hasPart": [ident(x) for x in payload]},
        {"@id": "#software", "@type": "SoftwareApplication", "name": "HKL offline workbench", "version": receipt["code_revision"]},
        {"@id": "#curator", "@type": "Person", "name": "Simulated fictional curator"},
        {"@id": "#export", "@type": "CreateAction", "name": "Export fictional public projection", "instrument": ident("#software"), "object": [ident(s["path"]) for s in view["profile"]["sources"]], "result": [ident("corpus.json"), ident("profile.json")]},
        {"@id": "#simulated-decision", "@type": "UpdateAction", "name": "Simulated acceptance of the reported quotation", "agent": ident("#curator"), "object": ident("history/profile-before-simulated-decision.json"), "result": ident("profile.json"), "instrument": ident("#software"), "endTime": receipt["timestamp_utc"]},
    ]
    for name in payload:
        graph.append({"@id": name, "@type": "File", "name": name, "description": "MIT-licensed fictional packet component", "contentSize": str((destination / name).stat().st_size)})
    for s in view["profile"]["sources"]:
        if s["derived_from"]:
            sources = {x["ref"]: x for x in view["profile"]["sources"]}
            graph.append({"@id": "#derive-" + s["ref"].replace("/", "-"), "@type": "CreateAction", "name": "Fictional source derivation", "object": [ident(sources[x]["path"]) for x in s["derived_from"]], "result": ident(s["path"]), "instrument": ident("#software")})
    write_json(destination / "ro-crate-metadata.json", {"@context": "https://w3id.org/ro/crate/1.2/context", "@graph": graph})
    write_json(destination / "packet-manifest.json", {"version": "1.0", "view": "public", "source_fixture_manifest_sha256": receipt["fixture_manifest_sha256"], "files": {p.relative_to(destination).as_posix(): digest(p.read_bytes()) for p in sorted(destination.rglob("*")) if p.is_file()}})
    return verify(destination)


def zip_packet(directory, target):
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for p in sorted(Path(directory).rglob("*")):
            if p.is_file():
                archive.write(p, p.relative_to(directory).as_posix())


def unpack_packet(archive_path, destination):
    destination = Path(destination)
    if destination.exists():
        raise ValueError("unpack destination must be new")
    with zipfile.ZipFile(archive_path) as archive:
        infos = archive.infolist()
        if len(infos) > 2048 or sum(x.file_size for x in infos) > 64 * 1024 * 1024:
            raise ValueError("packet exceeds bounded size")
        if len({x.filename.casefold() for x in infos}) != len(infos):
            raise ValueError("duplicate packet paths")
        for info in infos:
            safe_path(destination, info.filename)
            if info.is_dir() or stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError("unsupported packet entry")
        destination.mkdir(parents=True)
        for info in infos:
            path = safe_path(destination, info.filename)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.read(info))
    return verify(destination)
