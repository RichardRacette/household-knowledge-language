"""Adversarial checks of the experimental contracts, separate from schema tests."""
import copy
import tempfile
import unittest
from pathlib import Path

from hkl_workbench.answers import build_plan, public_view
from hkl_workbench.common import FIXTURES, digest, load_inputs, read_json, verify_fixtures, write_json
from hkl_workbench.experiments import e1
from hkl_workbench.model import semantic_errors, validate
from hkl_workbench.packet_reader import verify
from hkl_workbench.preservation import export_packet


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.corpus, self.profile = load_inputs()

    def test_frozen_contract_and_normal_inputs(self):
        self.assertEqual(validate(self.corpus, self.profile), [])

    def test_provenance_and_decision_probes(self):
        result = e1(self.corpus, self.profile)
        for row in result["checks"]:
            with self.subTest(case=row["case"]):
                self.assertTrue(row["passed"], row)

    def test_source_removal_cannot_use_another_records_local_id(self):
        view = public_view(self.corpus, self.profile)
        plan = build_plan(view, ["OBJ-0004/EVID-001"], {"subjects": ["bird"], "predicate": "possessed_by"})
        self.assertEqual(plan["claims"], [])
        self.assertEqual(plan["mode"], "Unknown")

    def test_omit_policy_does_not_acknowledge_existence(self):
        next(s for s in self.profile["sources"] if s["ref"] == "OBJ-0008/EVID-001")["disclosure"] = "omit"
        view = public_view(self.corpus, self.profile)
        plan = build_plan(view, [], {"subjects": ["letter"], "predicate": "contents"})
        self.assertFalse(plan["withheld"])
        self.assertEqual(plan["mode"], "Unknown")

    def test_derived_evidence_cycle_is_rejected(self):
        next(s for s in self.profile["sources"] if s["ref"] == "OBJ-0001/EVID-003")["derived_from"] = ["OBJ-0001/EVID-004"]
        self.assertIn("cyclic evidence derivation", semantic_errors(self.corpus, self.profile))

    def test_packet_modified_bytes_and_broken_links_are_distinct_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            packet = Path(tmp) / "packet"
            export_packet(self.corpus, self.profile, packet, {"code_revision": "test", "timestamp_utc": "2026-09-08T00:00:00Z", "fixture_manifest_sha256": verify_fixtures()})
            source = packet / "sources/OBJ-0004--EVID-001.txt"
            source.write_bytes(source.read_bytes() + b"modified")
            with self.assertRaisesRegex(ValueError, "modified packet bytes"):
                verify(packet)
            # Recompute the outer manifest to independently challenge semantic links.
            manifest = read_json(packet / "packet-manifest.json")
            manifest["files"][source.relative_to(packet).as_posix()] = digest(source.read_bytes())
            write_json(packet / "packet-manifest.json", manifest)
            with self.assertRaisesRegex(ValueError, "source hash differs"):
                verify(packet)


if __name__ == "__main__":
    unittest.main()
