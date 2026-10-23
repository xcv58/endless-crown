"""Synthetic contract checks; these fixtures are never Watch battery measurements."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from test_energy_tests import fixture

spec = importlib.util.spec_from_file_location("pilot", Path(__file__).parents[1] / "energy-compare.py")
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


class PilotTests(unittest.TestCase):
    def manifest(self, directory):
        manifest = {"schedule": ["original", "optimized", "optimized", "original"],
                    "durationSeconds": 600, "stepsPerSecond": 2, "scenario": "replay",
                    "pattern": "clicks", "conditions": "fixture only",
                    "variants": {v: {"fingerprint": "fixture-" + v} for v in ("original", "optimized")},
                    "attempts": []}
        for slot, variant in enumerate(manifest["schedule"], 1):
            report = fixture(variant, activity=2)
            report["runID"] += str(slot)
            report["configuration"]["stepsPerSecond"] = 2
            report["metadata"]["inputDriver"] = "app-scroll-replay-v1"
            path = Path(directory) / (str(slot) + ".json")
            path.write_text(json.dumps(report))
            manifest["attempts"].append({"slot": slot, "variant": variant, "phase": "battery",
                                         "status": "completed", "report": str(path)})
        return manifest

    def test_complete_pilot_remains_descriptive_and_excludes_smoke_and_interruption(self):
        with tempfile.TemporaryDirectory() as directory:
            m = self.manifest(directory)
            m["attempts"].insert(0, {"phase": "smoke", "status": "completed"})
            m["attempts"].insert(2, {"phase": "battery", "status": "failed"})
            summary = pilot.summarize(m)
            self.assertEqual(len(summary["rows"]), 4)
            self.assertTrue(summary["recordedConditionsMatched"])
            self.assertFalse(summary["batterySavingEstablished"])
            self.assertIn("below the three-run analysis threshold", summary["limitations"][0])

    def test_incomplete_duplicate_or_reordered_schedule_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            m = self.manifest(directory)
            for change in (lambda a: a.pop(), lambda a: a.append(copy.deepcopy(a[0])), lambda a: a.reverse()):
                changed = copy.deepcopy(m)
                change(changed["attempts"])
                with self.assertRaises(ValueError):
                    pilot.summarize(changed)

    def test_wrong_build_identity_or_requested_workload_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            m = self.manifest(directory)
            path = Path(m["attempts"][0]["report"])
            original = json.loads(path.read_text())
            for mutate in (lambda r: r["metadata"].update(sourceFingerprint="wrong"),
                           lambda r: r["configuration"].update(label="optimized"),
                           lambda r: r["configuration"].update(conditions="different")):
                changed = copy.deepcopy(original)
                mutate(changed)
                path.write_text(json.dumps(changed))
                with self.assertRaises(ValueError):
                    pilot.summarize(m)

    def test_different_settings_do_not_produce_combined_medians(self):
        with tempfile.TemporaryDirectory() as directory:
            m = self.manifest(directory)
            path = Path(m["attempts"][1]["report"])
            report = json.loads(path.read_text())
            report["metadata"]["menuHidden"] = "true"
            path.write_text(json.dumps(report))
            result = pilot.summarize(m)
            self.assertFalse(result["recordedConditionsMatched"])
            self.assertIsNone(result["descriptiveMediansPercentagePointsPerHour"])


if __name__ == "__main__":
    unittest.main()
