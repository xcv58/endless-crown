import copy
import importlib.util
from pathlib import Path
import unittest

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


if __name__ == "__main__":
    unittest.main()
