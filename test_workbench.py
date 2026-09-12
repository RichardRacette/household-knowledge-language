"""Adversarial checks of the experimental contracts, separate from schema tests."""
import tempfile
import shutil
import unittest
import zipfile
from pathlib import Path

from hkl_workbench.answers import build_plan, public_view
from hkl_workbench.common import FIXTURES, digest, json_bytes, load_inputs, provenance, read_json, write_json
from hkl_workbench.experiments import e1, e2, e4, corrupt_packet_probes
from hkl_workbench.model import semantic_errors, validate
from hkl_workbench.packet_reader import verify
from hkl_workbench.preservation import export_packet, unpack_packet
from hkl_workbench.retrieval import Index, MODES
from hkl_workbench.temporal import available_as_of, time_match


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

    def test_temporal_and_entity_regression_probes(self):
        for experiment in (e2, e4):
            for row in experiment(self.corpus, self.profile)["checks"]:
                with self.subTest(case=row["case"]):
                    self.assertTrue(row["passed"], row)

    def test_interval_boundaries_and_source_precision(self):
        a = next(a for a in self.profile["assertions"] if a["ref"] == "OBJ-0001/CLM-006")
        self.assertTrue(time_match(a["time"], "2020-01-01"))
        self.assertFalse(time_match(a["time"], "2024-05-01"))
        year = next(a for a in self.profile["assertions"] if a["ref"] == "DISPLAY-0001/CLM-001")["time"]
        self.assertTrue(time_match(year, "1998-12-31"))
        self.assertFalse(time_match(year, "1999-01-01"))
        self.assertEqual(year["expression"], "1998")

    def test_photo_capture_date_is_not_source_recording_time(self):
        snapshot = available_as_of(self.profile, "2024-06-01T00:00:00Z")
        self.assertNotIn("OBJ-0001/EVID-001", snapshot["evidence"])
        self.assertIn("OBJ-0001/EVID-007", snapshot["evidence"])
        view = public_view(self.corpus, self.profile)
        for mode in MODES:
            result = Index(view, mode).query("bird photograph 1991", {"subjects": ["bird"], "predicate": "possessed_by", "as_of": "2024-06-01T00:00:00Z"})
            self.assertNotIn("OBJ-0001/EVID-001", result["refs"])

    def test_as_of_plan_does_not_reference_future_conflict(self):
        view = public_view(self.corpus, self.profile)
        plan = build_plan(view, ["OBJ-0001/EVID-002"], {"subjects": ["bird"], "predicate": "giver", "as_of": "2026-07-31T00:00:00Z"})
        self.assertEqual(plan["claims"][0]["conflicts_with"], [])

    def test_same_source_units_and_bounded_context_across_indexes(self):
        view = public_view(self.corpus, self.profile)
        indexes = [Index(view, mode) for mode in MODES]
        self.assertEqual(indexes[0].units, indexes[1].units)
        self.assertEqual(indexes[1].units, indexes[2].units)
        for index in indexes:
            result = index.query("bird and key", {"subjects": ["bird"], "predicate": "location"})
            self.assertLessEqual(len(result["refs"]), 4)
            self.assertEqual(len(result["refs"]), len(set(result["refs"])))
            self.assertNotIn("OBJ-0008/EVID-001", index.units)
            self.assertNotIn("DISPLAY-0001/EVID-005", index.units)

    def test_source_content_change_changes_ranking(self):
        view = public_view(self.corpus, self.profile)
        before = Index(view, "direct").query("distinctivequartz", {"subjects": [], "predicate": "description"})
        self.assertEqual(before["refs"], [])
        view["corpus"]["records"][0]["evidence"][0]["excerpt_or_observation"] += " distinctivequartz"
        after = Index(view, "direct").query("distinctivequartz", {"subjects": [], "predicate": "description"})
        self.assertEqual(after["refs"], ["OBJ-0001/EVID-001"])

    def test_omitted_source_is_absent_but_public_object_is_independent(self):
        next(s for s in self.profile["sources"] if s["ref"] == "OBJ-0008/EVID-001")["disclosure"] = "omit"
        view = public_view(self.corpus, self.profile)
        plan = build_plan(view, [], {"subjects": ["letter"], "predicate": "contents"})
        self.assertFalse(plan["withheld"])
        self.assertEqual(plan["mode"], "Unknown")
        # Object identity remains independently declared Public Demo by its record.
        self.assertTrue(any(r["record_id"] == "OBJ-0008" for r in view["corpus"]["records"]))
        self.assertNotIn(b"ORCHID-482", json_bytes(view))
        source_name = next(r for r in self.corpus["records"] if r["record_id"] == "OBJ-0008")["evidence"][0]["source_name"]
        self.assertNotIn(source_name.encode(), json_bytes(view))

    def test_restricted_record_identity_and_orphan_entity_are_removed(self):
        record = next(r for r in self.corpus["records"] if r["record_id"] == "OBJ-0003")
        record["privacy"]["privacy_class"] = "Restricted"
        record["title"] = "RESTRICTED-RECORD-CANARY"
        view = public_view(self.corpus, self.profile)
        self.assertNotIn(b"RESTRICTED-RECORD-CANARY", json_bytes(view))
        self.assertFalse(any(r["record_id"] == "OBJ-0003" for r in view["corpus"]["records"]))
        self.assertFalse(any(e["id"] == "label-observation" for e in view["profile"]["entities"]))

    def test_derived_evidence_cycle_is_rejected(self):
        next(s for s in self.profile["sources"] if s["ref"] == "OBJ-0001/EVID-003")["derived_from"] = ["OBJ-0001/EVID-004"]
        self.assertIn("cyclic evidence derivation", semantic_errors(self.corpus, self.profile))

    def test_restricted_original_record_is_omitted_from_packet_history(self):
        self.corpus["records"][0]["privacy"]["privacy_class"] = "Restricted"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures = root / "fixtures"
            shutil.copytree(FIXTURES, fixtures)
            original = read_json(fixtures / "originals/ceramic_bird.json")
            original["title"] = "RESTRICTED-HISTORY-IDENTITY-CANARY"
            write_json(fixtures / "originals/ceramic_bird.json", original)
            packet = root / "packet"
            result = export_packet(self.corpus, self.profile, packet, provenance("python -m unittest discover -v"), fixtures)
            self.assertTrue(result["verified"])
            self.assertFalse((packet / "history/ceramic_bird.json").exists())
            for path in packet.rglob("*"):
                if path.is_file():
                    self.assertNotIn(b"RESTRICTED-HISTORY-IDENTITY-CANARY", path.read_bytes())

    def test_profile_cannot_rebind_a_local_claim_to_unrelated_evidence(self):
        self.profile["assertions"][0]["source_refs"] = ["OBJ-0001/EVID-002"]
        self.assertIn("assertion differs from record-local evidence links", semantic_errors(self.corpus, self.profile))

    def test_profile_cannot_append_unrecorded_cross_record_support(self):
        self.profile["assertions"][1]["source_refs"].append("OBJ-0004/EVID-001")
        self.assertIn("assertion differs from record-local evidence links", semantic_errors(self.corpus, self.profile))

    def test_assertion_derivation_requires_matching_source_ancestry(self):
        next(s for s in self.profile["sources"] if s["ref"] == "OBJ-0001/EVID-003")["derived_from"] = []
        self.assertIn("assertion derivation lacks source lineage", semantic_errors(self.corpus, self.profile))

    def test_reported_source_cannot_gain_known_status_by_changing_basis(self):
        self.corpus["records"][0]["claims"][1]["epistemic_state"] = "Known"
        self.profile["assertions"][1]["basis"] = "observation"
        self.assertIn("Known assertion lacks primary-only support", semantic_errors(self.corpus, self.profile))

    def test_packet_modified_bytes_and_broken_links_are_distinct_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            packet = Path(tmp) / "packet"
            export_packet(self.corpus, self.profile, packet, provenance("python -m unittest discover -v"))
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

    def test_packet_corruption_matrix(self):
        with tempfile.TemporaryDirectory() as tmp:
            packet = Path(tmp) / "packet"
            export_packet(self.corpus, self.profile, packet, provenance("python -m unittest discover -v"))
            for row in corrupt_packet_probes(packet):
                with self.subTest(case=row["case"]):
                    self.assertTrue(row["detected"], row)

    def test_zip_case_aliases_and_symlinks_rejected_before_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with zipfile.ZipFile(root / "aliases.zip", "w") as z:
                z.writestr("sources/A.txt", "one")
                z.writestr("sources/a.txt", "two")
            with self.assertRaisesRegex(ValueError, "duplicate packet paths"):
                unpack_packet(root / "aliases.zip", root / "aliases")
            self.assertFalse((root / "aliases").exists())
            with zipfile.ZipFile(root / "link.zip", "w") as z:
                info = zipfile.ZipInfo("source-link")
                info.create_system = 3
                info.external_attr = (0o120777 << 16)
                z.writestr(info, "../outside")
            with self.assertRaisesRegex(ValueError, "unsupported packet entry"):
                unpack_packet(root / "link.zip", root / "linked")
            self.assertFalse((root / "linked").exists())


if __name__ == "__main__":
    unittest.main()
