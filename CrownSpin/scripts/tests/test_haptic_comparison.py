"""Synthetic fixtures for contract checks; never physical Watch measurements."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("comparison", Path(__file__).parents[1] / "haptic-comparison.py")
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


def fixture():
    timings = [{"callbackElapsedSeconds": t - .001, "requestElapsedSeconds": t,
                "oldPosition": 500 + i, "newPosition": 501 + i,
                "pattern": "clicks", "requestsHaptic": True} for i, t in enumerate((1, 2, 2.05, 2.25))]
    return {"schemaVersion": 1, "runID": "fixture", "status": "completed", "issues": [],
            "configuration": {"scenario": "manual", "label": "fixture", "durationSeconds": 30,
                              "stepsPerSecond": 2, "pattern": "clicks", "conditions": "fixture only",
                              "captureHapticTiming": True},
            "metadata": {"simulator": "false"}, "hapticTimings": timings,
            "samples": [{"elapsedSeconds": t, "batteryLevel": .5, "powerState": "unplugged",
                         "scenePhase": "active", "luminanceReduced": False, "thermalState": 0,
                         "scrollEvents": count, "hapticRequests": count, "replaySteps": 0}
                        for t, count in ((0, 0), (30, 4))]}


class HapticComparisonTests(unittest.TestCase):
    def test_intervals_exclude_startup_and_do_not_claim_motor_delivery(self):
        result = comparison.timing_metrics(fixture())
        self.assertEqual(result["hapticRequests"], 4)
        self.assertEqual(result["steadyRequests"], 3)
        self.assertAlmostEqual(result["requestIntervalMs"]["p50"], 125)
        self.assertEqual(result["requestIntervalsUnder100msPercent"], 50)
        self.assertAlmostEqual(result["callbackToRequestMs"]["p50"], 1)
        self.assertFalse(result["motorDeliveryMeasured"])

    def test_missing_reordered_and_nonfinite_timestamps_are_rejected(self):
        for mutate in (lambda r: r["hapticTimings"].pop(),
                       lambda r: r["hapticTimings"].reverse(),
                       lambda r: r["hapticTimings"][0].update(requestElapsedSeconds=float("nan")),
                       lambda r: r["hapticTimings"][0].update(requestElapsedSeconds=0),
                       lambda r: r["hapticTimings"][0].update(pattern="buzz")):
            r = copy.deepcopy(fixture())
            mutate(r)
            with self.assertRaises(ValueError):
                comparison.timing_metrics(r)

    def test_interrupted_capture_and_mismatched_requests_are_rejected(self):
        r = fixture()
        r["status"] = "interrupted"
        with self.assertRaises(ValueError):
            comparison.timing_metrics(r)
        r = fixture()
        r["hapticTimings"][0]["requestsHaptic"] = False
        with self.assertRaises(ValueError):
            comparison.timing_metrics(r)


if __name__ == "__main__":
    unittest.main()
