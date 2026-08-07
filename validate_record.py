#!/usr/bin/env python3
"""Validate a Household Knowledge Language JSON record."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object from disk with a useful error if it is malformed."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"File not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"Invalid JSON in {path} at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc

    if not isinstance(value, dict):
        raise SystemExit(f"Expected a JSON object in {path}.")
    return value


def validate_record(record_path: Path, schema_path: Path) -> list[str]:
    """Return human-readable validation errors, or an empty list when valid."""
    record = load_json(record_path)
    schema = load_json(schema_path)

    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    errors: list[str] = []
    for error in sorted(
        validator.iter_errors(record),
        key=lambda item: [str(part) for part in item.absolute_path],
    ):
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append(f"{location}: {error.message}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a household record against the HKL JSON Schema."
    )
    parser.add_argument("record", type=Path, help="Path to the household record JSON file")
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path(__file__).with_name("household_record.schema.json"),
        help="Path to the schema file (default: household_record.schema.json)",
    )
    args = parser.parse_args()

    errors = validate_record(args.record, args.schema)

    if errors:
        print(f"INVALID: {args.record}")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"VALID: {args.record}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
