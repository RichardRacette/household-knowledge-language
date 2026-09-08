"""Small file/provenance helpers shared by the experiments."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "research/fixtures/v1"


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def json_bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json_bytes(value))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_path(root, name):
    """Conservative portable packet paths; reject aliases, drives and symlinks."""
    if not isinstance(name, str) or not name or not re.fullmatch(r"[A-Za-z0-9_./-]+", name):
        raise ValueError("unsafe path")
    parts = name.split("/")
    if any(p in ("", ".", "..") or p.endswith(".") for p in parts):
        raise ValueError("unsafe path")
    if any(p.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(10)], *[f"LPT{i}" for i in range(10)]} for p in parts):
        raise ValueError("unsafe reserved path")
    if PurePosixPath(name).is_absolute():
        raise ValueError("unsafe absolute path")
    root = Path(root).resolve()
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise ValueError("unsafe linked path")
    if not current.resolve().is_relative_to(root):
        raise ValueError("path escapes packet")
    return current


def verify_fixtures(directory=FIXTURES):
    manifest = read_json(directory / "manifest.json")
    if manifest.get("version") != "1" or manifest.get("fictional") is not True:
        raise ValueError("unsupported fixture version")
    for name, expected in manifest["files"].items():
        path = safe_path(directory, name)
        if not path.is_file() or digest(path.read_bytes()) != expected:
            raise ValueError(f"fixture hash mismatch: {name}")
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()}
    if actual != set(manifest["files"]) | {"manifest.json"}:
        raise ValueError("unlisted fixture files")
    return digest((directory / "manifest.json").read_bytes())


def load_inputs(directory=FIXTURES):
    verify_fixtures(directory)
    return read_json(directory / "corpus.json"), read_json(directory / "profile.json")


def provenance(command, directory=FIXTURES):
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()
    code = sorted((ROOT / "hkl_workbench").glob("*.py")) + sorted(ROOT.glob("test*.py"))
    code += [ROOT / "validate_record.py", ROOT / "household_record.schema.json", ROOT / "hkl_workbench/profile.schema.json"]
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "code_revision": git("rev-parse", "HEAD"),
        "dirty_worktree": bool(git("status", "--porcelain")),
        "dirty_paths": git("status", "--porcelain").splitlines(),
        "command": command,
        "python": platform.python_version(),
        "platform": platform.system(),
        "dependencies": {x: importlib.metadata.version(x) for x in ("jsonschema", "attrs", "jsonschema-specifications", "referencing", "rpds-py")},
        "code_hashes": {p.relative_to(ROOT).as_posix(): digest(p.read_bytes()) for p in code if p.exists()},
        "schema_sha256": digest((ROOT / "household_record.schema.json").read_bytes()),
        "profile_version": "1.0",
        "profile_sha256": digest((directory / "profile.json").read_bytes()),
        "fixture_manifest_sha256": verify_fixtures(directory),
        "contract_sha256": digest((ROOT / "docs/research/contract.md").read_bytes()),
    }
