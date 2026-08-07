#!/usr/bin/env python3
"""Regression tests for the Household Knowledge Language validator."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from validate_record import load_json, validate_record


HERE = Path(__file__).resolve().parent
SCHEMA_PATH = HERE / "household_record.schema.json"
EXAMPLE_PATH = HERE / "ceramic_bird.json"


class HouseholdRecordValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.valid_record = load_json(EXAMPLE_PATH)

    def validate_modified_record(self, record: dict) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            record_path = Path(directory) / "record.json"
            record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
            return validate_record(record_path, SCHEMA_PATH)

    def test_fictional_ceramic_bird_is_valid(self) -> None:
        self.assertEqual(validate_record(EXAMPLE_PATH, SCHEMA_PATH), [])

    def test_unknown_is_a_valid_epistemic_state(self) -> None:
        record = copy.deepcopy(self.valid_record)
        record["claims"][0]["epistemic_state"] = "Unknown"
        self.assertEqual(self.validate_modified_record(record), [])

    def test_unsupported_epistemic_state_is_rejected(self) -> None:
        record = copy.deepcopy(self.valid_record)
        record["claims"][0]["epistemic_state"] = "Definitely True"
        errors = self.validate_modified_record(record)
        self.assertTrue(any("epistemic_state" in error for error in errors), errors)

    def test_invalid_record_id_is_rejected(self) -> None:
        record = copy.deepcopy(self.valid_record)
        record["record_id"] = "my private object"
        errors = self.validate_modified_record(record)
        self.assertTrue(any("record_id" in error for error in errors), errors)

    def test_missing_family_meaning_is_rejected(self) -> None:
        record = copy.deepcopy(self.valid_record)
        del record["meaning"]["why_kept"]
        errors = self.validate_modified_record(record)
        self.assertTrue(any("meaning" in error and "why_kept" in error for error in errors), errors)

    def test_invalid_privacy_class_is_rejected(self) -> None:
        record = copy.deepcopy(self.valid_record)
        record["privacy"]["privacy_class"] = "Anyone on the internet"
        errors = self.validate_modified_record(record)
        self.assertTrue(any("privacy_class" in error for error in errors), errors)

    def test_confidence_above_one_is_rejected(self) -> None:
        record = copy.deepcopy(self.valid_record)
        record["claims"][0]["confidence"] = 1.5
        errors = self.validate_modified_record(record)
        self.assertTrue(any("confidence" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main(verbosity=2)
