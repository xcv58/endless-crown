"""Synthetic contract checks; these fixtures are never Watch battery measurements."""
import copy
import importlib.util
import json
import argparse
from pathlib import Path
import plistlib
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from test_energy_tests import fixture

spec = importlib.util.spec_from_file_location("pilot", Path(__file__).parents[1] / "energy-compare.py")
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


class PilotTests(unittest.TestCase):
    def normal_build(self, session):
        app = session / "Normal.app"
        app.mkdir()
        (app / "Info.plist").write_bytes(plistlib.dumps({"EnergySourceFingerprint": "synthetic-source",
            "CFBundleIdentifier": pilot.energy.BUNDLE_ID, "CFBundleExecutable": "CrownSpin"}))
        (app / "CrownSpin").write_bytes(b"synthetic ordinary executable")
        normal = session / "normal.json"
        normal.write_text(json.dumps({"app": str(app), "sourceFingerprint": "synthetic-source",
                                     "diagnosticMarkersAbsent": True}))
        pilot.record_normal(normal)
        manifest = {"restoreNormalBuildManifest": str(normal), "sourceFingerprint": "synthetic-source",
                    "developerDir": "/synthetic-Xcode", "device": "synthetic-watch"}
        return app, normal, manifest

    def test_restore_rejects_changed_product_and_legacy_diagnostic_identity(self):
        for replacement in (b"different normal executable", b"synthetic EnergyTestController CROWN_START_DIAGNOSTICS"):
            with self.subTest(replacement=replacement), tempfile.TemporaryDirectory() as directory:
                session = Path(directory)
                app, normal, manifest = self.normal_build(session)
                with patch.object(pilot.energy, "source_fingerprint", return_value="synthetic-source"):
                    self.assertEqual(pilot.energy.build_fingerprint("legacy-unqualified"), manifest["sourceFingerprint"])
                (app / "CrownSpin").write_bytes(replacement)
                with patch.object(pilot.subprocess, "run") as device:
                    with self.assertRaisesRegex(ValueError, "restore product changed|exclude diagnostic"):
                        pilot.restore_normal(session, manifest)
                    device.assert_not_called()
                with self.assertRaises(ValueError):
                    pilot.record_normal(normal)

    def test_restore_rejects_unrecorded_product_before_device_actions(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Path(directory)
            _, normal, manifest = self.normal_build(session)
            value = json.loads(normal.read_text())
            del value["restoreProductFingerprint"]
            normal.write_text(json.dumps(value))
            with patch.object(pilot.subprocess, "run") as device:
                with self.assertRaisesRegex(ValueError, "unrecorded"):
                    pilot.restore_normal(session, manifest)
                device.assert_not_called()

    def test_failed_cleanup_is_durable_and_retried_without_captures(self):
        for capture_status in ("completed", "stopped"):
            with tempfile.TemporaryDirectory() as directory:
                session = Path(directory); manifest = {"status": capture_status, "attempts": [{"fixture": True}], "error": "capture error"}
                (session / "restore-launch.log").write_text("first failure")
                with patch.object(pilot, "restore_normal", side_effect=ValueError("synthetic restore failure")):
                    with self.assertRaisesRegex(ValueError, "synthetic restore failure"):
                        pilot.restore_after_capture(session, manifest)
                persisted = json.loads((session / "comparison.json").read_text())
                self.assertEqual(persisted["status"], "restoration-failed")
                self.assertEqual(persisted["captureStatus"], capture_status)
                self.assertIn("synthetic restore failure", persisted["restoreError"])
                self.assertEqual(persisted["error"], "capture error")
                with patch.object(pilot, "restore_normal"), patch.object(pilot, "run_attempt") as captures:
                    pilot.run(argparse.Namespace(session=session, restore_only=True))
                    captures.assert_not_called()
                after = json.loads((session / "comparison.json").read_text())
                self.assertEqual(after["status"], capture_status)
                self.assertNotIn("restoreError", after)
                self.assertEqual(after["attempts"], [{"fixture": True}])
                self.assertEqual(next(session.glob("restore-prior-*/restore-launch.log")).read_text(), "first failure")
                # A later resumed capture must replace the previous stopped result.
                after["status"] = "completed"
                with patch.object(pilot, "restore_normal"):
                    pilot.restore_after_capture(session, after)
                self.assertEqual(after["status"], "completed")

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

    def test_battery_runner_rejects_profile_session_before_build_or_device_work(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Path(directory)
            (session / "comparison.json").write_text(json.dumps({"status": "ready", "attempts": [], "runtimeProfile": True}))
            with patch.object(pilot, "verify_builds") as verify, patch.object(pilot, "run_attempt") as run:
                with self.assertRaisesRegex(ValueError, "runtime-compare.py"):
                    pilot.run(argparse.Namespace(session=session))
                verify.assert_not_called(); run.assert_not_called()

    def test_battery_summary_rejects_valid_profiling_and_timing_reports(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = self.manifest(directory)
            with self.assertRaisesRegex(ValueError, "Runtime profiles"):
                pilot.summarize(dict(manifest, runtimeProfile=True))
            for purpose in ("runtime-profile-v1", "haptic-timing-only"):
                manifest = self.manifest(directory)
                path = Path(manifest["attempts"][0]["report"])
                report = json.loads(path.read_text())
                report["metadata"]["diagnosticPurpose"] = purpose
                if purpose == "runtime-profile-v1":
                    report["configuration"]["captureRuntimeProfile"] = True
                    report["runtimeProfile"] = {"samples": [
                        {"elapsedSeconds": sample["elapsedSeconds"],
                         "userCPUSeconds": sample["elapsedSeconds"] * .1,
                         "systemCPUSeconds": sample["elapsedSeconds"] * .01,
                         "contentViewBodyUpdates": sample["scrollEvents"], "work": {}}
                        for sample in report["samples"]]}
                else:
                    report["configuration"]["captureHapticTiming"] = True
                self.assertEqual(pilot.energy.validate(report), [])
                path.write_text(json.dumps(report))
                with self.assertRaisesRegex(ValueError, "not battery observations"):
                    pilot.summarize(manifest)

    def test_restore_launch_failure_is_saved_and_propagated(self):
        for launch_code in (0, 9):
            with tempfile.TemporaryDirectory(prefix="crown-restore-launch-") as directory:
                session = Path(directory)
                _, normal, manifest = self.normal_build(session)
                with patch.object(pilot.subprocess, "run", side_effect=[SimpleNamespace(returncode=0), SimpleNamespace(returncode=launch_code)]) as command:
                    if launch_code:
                        with self.assertRaisesRegex(ValueError, "could not be opened"):
                            pilot.restore_normal(session, manifest)
                    else:
                        pilot.restore_normal(session, manifest)
                    self.assertEqual(command.call_count, 2)
                self.assertEqual(json.loads((session / "comparison.json").read_text())["normalRestore"]["launchExitCode"], launch_code)
                self.assertEqual(json.loads(normal.read_text())["lastRestoreLaunchExit"], launch_code)


if __name__ == "__main__":
    unittest.main()
