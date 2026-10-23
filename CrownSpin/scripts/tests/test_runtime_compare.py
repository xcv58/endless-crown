"""Fabricated protocol data only; never Watch measurements."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_energy_tests import fixture

spec = importlib.util.spec_from_file_location("runtime", Path(__file__).parents[1] / "runtime-compare.py")
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


class RuntimeComparisonTests(unittest.TestCase):
    def test_cleanup_retry_does_not_repeat_runtime_slots(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Path(directory)
            manifest = {"status": "restoration-failed", "captureStatus": "completed", "attempts": [], "restoreError": "first failure"}
            (session / "comparison.json").write_text(json.dumps(manifest))
            with patch.object(runtime.comparison, "restore_normal"), patch.object(runtime.comparison, "run_attempt") as capture:
                runtime.run(session, restore_only=True)
                capture.assert_not_called()
            self.assertEqual(json.loads((session / "comparison.json").read_text())["status"], "completed")

    def prepare(self, directory):
        manifest = {"schedule": runtime.SCHEDULE, "attempts": [], "scenario": "replay", "pattern": "clicks",
                    "durationSeconds": 600, "stepsPerSecond": 2, "conditions": "fixture only",
                    "runtimeProfile": True, "variants": {v: {"fingerprint": "fixture-" + v} for v in runtime.VARIANTS}}
        for slot, variant in enumerate(runtime.SCHEDULE, 1):
            report = fixture(label=variant, activity=2)
            report["runID"] = "fixture-runtime-" + str(slot)
            report["configuration"].update(stepsPerSecond=2, captureRuntimeProfile=True)
            report["metadata"].update(inputDriver="app-scroll-replay-v1", diagnosticPurpose="runtime-profile-v1")
            report["runtimeProfile"] = {"samples": [
                {"elapsedSeconds": s["elapsedSeconds"], "userCPUSeconds": s["elapsedSeconds"] * .1,
                 "systemCPUSeconds": s["elapsedSeconds"] * .01, "contentViewBodyUpdates": s["scrollEvents"],
                 "work": {}} for s in report["samples"]]}
            path = Path(directory) / (str(slot) + ".json")
            path.write_text(json.dumps(report))
            manifest["attempts"].append({"phase": "runtime", "slot": slot, "variant": variant,
                                         "status": "completed", "report": str(path)})
        return manifest

    def test_complete_balanced_cpu_comparison_never_claims_battery_savings(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = self.prepare(directory)
            result = runtime.summarize(manifest)
            self.assertEqual(len(result["rows"]), 8)
            self.assertTrue(result["recordedConditionsMatched"])
            self.assertFalse(result["batterySavingEstablished"])
            self.assertAlmostEqual(result["descriptiveCPUSecondsPerMinute"]["original"]["median"], 6.6)
            incomplete = copy.deepcopy(manifest)
            incomplete["attempts"].pop()
            with self.assertRaises(ValueError):
                runtime.summarize(incomplete)

    def test_bad_identity_duplicate_cpu_or_mismatched_conditions_prevent_summary(self):
        for mutation in ("identity", "duplicate", "cpu", "conditions"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                manifest = self.prepare(directory)
                path = Path(manifest["attempts"][-1]["report"])
                report = json.loads(path.read_text())
                if mutation == "identity": report["metadata"]["sourceFingerprint"] = "other"
                elif mutation == "duplicate": report["runID"] = "fixture-runtime-1"
                elif mutation == "cpu": report["runtimeProfile"]["samples"][-1]["userCPUSeconds"] = -1
                else: report["metadata"]["numberSystem"] = "roman"
                path.write_text(json.dumps(report))
                with self.assertRaises(ValueError):
                    runtime.summarize(manifest)

    def test_resume_accepts_only_a_valid_unique_schedule_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = self.prepare(directory)
            manifest["attempts"] = manifest["attempts"][:2]
            self.assertEqual(runtime.completed_prefix(manifest), 2)
            manifest["attempts"].append(copy.deepcopy(manifest["attempts"][0]))
            with self.assertRaises(ValueError):
                runtime.completed_prefix(manifest)
