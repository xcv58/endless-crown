import copy
import argparse
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("system_scroll", Path(__file__).parents[1] / "system-scroll-compare.py")
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


class ReportValidationTests(unittest.TestCase):
    def setUp(self):
        self.request = {"runID": "sample", "condition": "app-list", "mode": "automated",
                        "seconds": 16, "delta": .5, "velocity": .5, "period": 8}
        self.report = {**self.request, "durationSeconds": 16, "elapsedSeconds": 16.2,
                       "batteryReader": "WKInterfaceDevice-in-UI-test-runner",
                       "issues": [], "samples": [self.sample(0), self.sample(16)],
                       "gestures": [{"plannedSeconds": 0, "startedSeconds": .1, "endedSeconds": 6.4, "delta": .5},
                                    {"plannedSeconds": 8, "startedSeconds": 8.1, "endedSeconds": 14.4, "delta": -.5}]}

    def sample(self, seconds):
        return {"elapsedSeconds": seconds, "batteryLevel": .4, "batteryState": 1,
                "thermalState": 0, "foreground": True}

    def test_accepts_matched_crown_workload(self):
        self.assertEqual(comparison.validate(self.report, self.request), [])

    def test_accepts_long_phases_with_full_battery_coverage(self):
        self.request.update(seconds=120, delta=2, velocity=.1, period=30)
        self.report.update(self.request, durationSeconds=120, elapsedSeconds=120.1,
                           samples=[self.sample(t) for t in (0, 25.3, 55.3, 85.3, 115.3, 120.1)],
                           gestures=[{"plannedSeconds": t, "startedSeconds": t + .1,
                                      "endedSeconds": t + 25.3, "delta": 2 if i % 2 == 0 else -2}
                                     for i, t in enumerate((0, 30, 60, 90))])
        self.assertEqual(comparison.validate(self.report, self.request), [])
        self.report["samples"] = [self.sample(t) for t in (0, 55.3, 115.3, 120.1)]
        self.assertTrue(comparison.validate(self.report, self.request))

    def test_rejects_extra_or_missing_commands(self):
        for gestures in (self.report["gestures"][:1], self.report["gestures"] + self.report["gestures"]):
            value = copy.deepcopy(self.report)
            value["gestures"] = gestures
            self.assertIn("Crown command count differs.", comparison.validate(value, self.request))

    def test_rejects_gesture_overrun(self):
        self.report["gestures"][0]["endedSeconds"] = 9
        self.assertIn("Crown command cadence or direction differs.", comparison.validate(self.report, self.request))

    def test_rejects_wrong_mode_or_condition(self):
        for key, value in (("mode", "manual"), ("condition", "app")):
            report = copy.deepcopy(self.report)
            report[key] = value
            self.assertTrue(comparison.validate(report, self.request))

    def test_rejects_a_different_battery_reader(self):
        self.report["batteryReader"] = "foreground-app-only"
        self.assertTrue(comparison.validate(self.report, self.request))

    def test_rejects_launcher_screen_switches(self):
        self.request["screenValidation"] = "list-row-width-or-clicks-label-v1"
        self.report["screenValidation"] = self.request["screenValidation"]
        for sample in self.report["samples"]:
            sample["screenVerified"] = True
        self.assertEqual(comparison.validate(self.report, self.request), [])
        self.report["samples"][1]["screenVerified"] = False
        self.assertTrue(comparison.validate(self.report, self.request))

    def test_rejects_invalid_health_and_foreground(self):
        for key, value in (("batteryLevel", -1), ("batteryLevel", float("nan")),
                           ("batteryState", 2), ("thermalState", 1), ("foreground", False)):
            report = copy.deepcopy(self.report)
            report["samples"][1][key] = value
            self.assertTrue(comparison.validate(report, self.request))

    def test_rejects_truncated_measurement(self):
        self.report["elapsedSeconds"] = 12
        self.report["samples"][-1]["elapsedSeconds"] = 12
        self.assertTrue(comparison.validate(self.report, self.request))

    def test_manual_input_has_no_synthetic_commands(self):
        self.request["mode"] = self.report["mode"] = "manual"
        self.report["gestures"] = []
        self.assertEqual(comparison.validate(self.report, self.request), [])
        self.report["gestures"] = [{"plannedSeconds": 0, "startedSeconds": 0, "endedSeconds": 6, "delta": .5}]
        self.assertTrue(comparison.validate(self.report, self.request))


class RestorationTests(unittest.TestCase):
    def run_with_restoration(self, *, grid_code=0, grid_error=None, normal_error=None, trial_error=None):
        with tempfile.TemporaryDirectory(prefix="crown-restore-tests-") as directory:
            session = Path(directory)
            manifest = {"status": "ready", "attempts": [], "sourceFingerprint": "synthetic-source",
                        "fixtureFingerprint": hashlib.sha256(comparison.FIXTURE.read_bytes()).hexdigest()}
            path = session / "system-comparison.json"; path.write_text(json.dumps(manifest))
            def execute(session, manifest, request, name, test=None):
                if name == "restore-grid":
                    if grid_error:
                        raise grid_error
                    return grid_code, None
                self.assertTrue(name.startswith("trial-"))
                if trial_error:
                    raise trial_error
                return 0, {"samples": [{"batteryLevel": .6}, {"batteryLevel": .6}], "gestures": []}
            failure = None
            with patch.object(comparison.energy, "source_fingerprint", return_value="synthetic-source"), \
                    patch.object(comparison, "execute", side_effect=execute), \
                    patch.object(comparison, "validate", return_value=[]), \
                    patch.object(comparison.time, "sleep"), \
                    patch.object(comparison.comparison, "restore_normal", side_effect=normal_error) as normal, \
                    redirect_stdout(io.StringIO()):
                try:
                    comparison.run(argparse.Namespace(session=session, mode="manual", seconds=30,
                                                     delta=.5, velocity=.5, period=8))
                except BaseException as error:
                    failure = error
                self.assertEqual(normal.call_count, 1)
            return json.loads(path.read_text()), failure

    def test_grid_failure_attempts_app_restore_and_cannot_complete(self):
        manifest, error = self.run_with_restoration(grid_code=7)
        self.assertIsInstance(error, ValueError)
        self.assertEqual(manifest["status"], "restoration-failed")
        self.assertEqual(manifest["gridRestoreTestExitCode"], 7)
        self.assertEqual(len(manifest["attempts"]), 4)

    def test_grid_exception_still_attempts_app_restore(self):
        manifest, error = self.run_with_restoration(grid_error=TimeoutError("synthetic timeout"))
        self.assertIsInstance(error, ValueError)
        self.assertIn("TimeoutError", manifest["gridRestoreError"])
        self.assertEqual(manifest["status"], "restoration-failed")

    def test_grid_interrupt_attempts_app_restore_then_propagates(self):
        manifest, error = self.run_with_restoration(grid_error=KeyboardInterrupt())
        self.assertIsInstance(error, KeyboardInterrupt)
        self.assertEqual(manifest["status"], "restoration-failed")

    def test_app_restore_failure_cannot_complete(self):
        manifest, error = self.run_with_restoration(normal_error=ValueError("synthetic restore refused"))
        self.assertIsInstance(error, ValueError)
        self.assertEqual(manifest["gridRestoreTestExitCode"], 0)
        self.assertEqual(manifest["status"], "restoration-failed")
        self.assertIn("restore refused", manifest["normalRestoreError"])

    def test_trial_failure_restores_both_and_retains_original_failure(self):
        manifest, error = self.run_with_restoration(trial_error=ValueError("synthetic trial failed"))
        self.assertEqual(str(error), "synthetic trial failed")
        self.assertEqual(manifest["gridRestoreTestExitCode"], 0)
        self.assertEqual(manifest["status"], "stopped")

    def test_success_requires_both_restorations(self):
        manifest, error = self.run_with_restoration()
        self.assertIsNone(error)
        self.assertEqual(manifest["gridRestoreTestExitCode"], 0)
        self.assertEqual(manifest["status"], "complete-needs-screenshot-review")


if __name__ == "__main__":
    unittest.main()
