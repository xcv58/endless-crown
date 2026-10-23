import argparse
from contextlib import redirect_stdout
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("energy_tests", Path(__file__).parents[1] / "energy-tests.py")
energy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(energy)


def fixture(label="baseline", scenario="replay", drop=.03, activity=5):
    """Fabricated data solely for validator tests; never device measurements."""
    return {
        "schemaVersion": 1, "runID": f"fixture-{label}", "status": "completed", "issues": [],
        "configuration": {"label": label, "scenario": scenario, "pattern": "clicks",
                          "durationSeconds": 600, "stepsPerSecond": 5, "conditions": "fixture only"},
        "metadata": {"simulator": "false", "hardwareModel": "fixture-Watch", "watchOS": "fixture-OS",
                     "sourceFingerprint": f"fixture-{label}", "diagnosticVersion": "1",
                     "ambientMode": "true", "numberSystem": "decimal", "menuHidden": "false"},
        "samples": [{"elapsedSeconds": t, "batteryLevel": .8 - drop * t / 600,
                     "powerState": "unplugged", "scenePhase": "active", "luminanceReduced": False,
                     "thermalState": 0, "scrollEvents": int(t * activity),
                     "hapticRequests": 0 if scenario == "replay-no-haptics" else int(t * activity),
                     "replaySteps": int(t * activity) if scenario.startswith("replay") else 0}
                    for t in range(0, 601, 30)]
    }


class EnergyTests(unittest.TestCase):
    def test_runtime_profile_captures_are_excluded_from_battery_comparisons(self):
        data = fixture()
        data["configuration"]["captureRuntimeProfile"] = True
        data["metadata"]["diagnosticPurpose"] = "runtime-profile-v1"
        data["runtimeProfile"] = {"samples": [
            {"elapsedSeconds": s["elapsedSeconds"], "userCPUSeconds": s["elapsedSeconds"] * .1,
             "systemCPUSeconds": s["elapsedSeconds"] * .01, "contentViewBodyUpdates": s["scrollEvents"],
             "work": {}} for s in data["samples"]]}
        self.assertEqual(energy.validate(data), [])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            path.write_text(json.dumps(data))
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(energy.analyse(argparse.Namespace(reports=[path], before="baseline", after="optimized")), 0)
            self.assertIn("excluded from battery comparison", output.getvalue())
            self.assertNotIn("median=", output.getvalue())

    def test_runtime_capture_rejects_missing_decreasing_and_mismatched_cpu_data(self):
        data = fixture()
        data["configuration"]["captureRuntimeProfile"] = True
        self.assertTrue(energy.validate(data))
        data["metadata"]["diagnosticPurpose"] = "runtime-profile-v1"
        data["runtimeProfile"] = {"samples": [
            {"elapsedSeconds": s["elapsedSeconds"], "userCPUSeconds": s["elapsedSeconds"] * .1,
             "systemCPUSeconds": s["elapsedSeconds"] * .01, "contentViewBodyUpdates": 0,
             "work": {}} for s in data["samples"]]}
        self.assertEqual(energy.validate(data), [])
        for key, value in (("userCPUSeconds", -1), ("elapsedSeconds", 599), ("systemCPUSeconds", 0)):
            changed = copy.deepcopy(data)
            changed["runtimeProfile"]["samples"][-1][key] = value
            self.assertTrue(energy.validate(changed))

    def test_variant_identities_separate_compile_flags_and_preserve_legacy_builds(self):
        with patch.object(energy, "source_fingerprint", return_value="frozen-source"):
            self.assertEqual(energy.build_fingerprint("legacy-unqualified"), "frozen-source")
            self.assertEqual(energy.build_fingerprint(), energy.build_fingerprint("optimized"))
            self.assertNotEqual(energy.build_fingerprint(), "frozen-source")
            self.assertNotEqual(energy.build_fingerprint("original"), energy.build_fingerprint("optimized"))
            self.assertEqual(energy.build_fingerprint("optimized"), energy.build_fingerprint("optimized"))
            with self.assertRaises(ValueError):
                energy.build_fingerprint("unknown")
        self.assertEqual(energy.compilation_flags("optimized"), ["ENERGY_TESTING", "HAPTIC_LEGACY_STATS"])
        self.assertEqual(energy.compilation_flags("legacy-unqualified"), ["ENERGY_TESTING"])
        self.assertIn("HAPTIC_LEGACY_PERSISTENCE", energy.compilation_flags("original"))
        self.assertIn("HAPTIC_LEGACY_MENU_TIMER", energy.compilation_flags("original"))

    def test_isolated_variants_change_only_the_requested_overhead_path(self):
        original = set(energy.compilation_flags("original"))
        timer = set(energy.compilation_flags("timer-only"))
        persistence = set(energy.compilation_flags("persistence-only"))
        self.assertEqual(original - timer, {"HAPTIC_LEGACY_TIMER", "HAPTIC_LEGACY_MENU_TIMER"})
        self.assertEqual(original - persistence, {"HAPTIC_LEGACY_PERSISTENCE"})
        self.assertFalse(timer - original)
        self.assertFalse(persistence - original)
        with patch.object(energy, "source_fingerprint", return_value="frozen-source"):
            identities = {energy.build_fingerprint(variant) for variant in energy.AUTOMATION_VARIANTS}
            self.assertEqual(len(identities), len(energy.AUTOMATION_VARIANTS))

    def test_new_cli_builds_select_normal_observation_and_legacy_is_explicit(self):
        for command, arguments, function in (("build", [], "build"),
                ("build-automation", ["--device", "synthetic-watch"], "build"),
                ("automate", ["--device", "synthetic-watch"], "automate")):
            for extra, expected in (([], "optimized"), (["--variant", "legacy-unqualified"], "legacy-unqualified")):
                selected = []
                with patch.object(energy, function, side_effect=lambda args: selected.append(args.variant)), \
                        patch.object(energy.sys, "argv", ["energy-tests.py", command, *arguments, *extra]):
                    self.assertEqual(energy.main(), 0)
                self.assertEqual(selected, [expected])
        self.assertIn("HAPTIC_LEGACY_STATS", energy.compilation_flags())

    def test_full_display_modes_and_historical_unknown_mode_do_not_pool(self):
        ambient = fixture()
        ambient["metadata"]["displayMode"] = "ambient"
        haptics_only = copy.deepcopy(ambient)
        haptics_only["metadata"]["displayMode"] = "hapticsOnly"
        historical = copy.deepcopy(ambient)
        del historical["metadata"]["displayMode"]
        self.assertNotEqual(energy.comparison_key(ambient), energy.comparison_key(haptics_only))
        self.assertNotEqual(energy.comparison_key(ambient), energy.comparison_key(historical))

    def test_haptic_timing_captures_never_enter_battery_metrics(self):
        for configuration, purpose in ((True, "haptic-timing-only"), (True, None), (False, "haptic-timing-only")):
            data = fixture(scenario="manual")
            data["configuration"]["captureHapticTiming"] = configuration
            if purpose:
                data["metadata"]["diagnosticPurpose"] = purpose
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "timing.json"; path.write_text(json.dumps(data))
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(energy.analyse(argparse.Namespace(reports=[path], before="baseline", after="optimized")), 0)
                self.assertIn("TIMING timing.json: excluded from battery comparison", output.getvalue())
                self.assertNotIn("median=", output.getvalue())
                self.assertNotIn("pp/hour", output.getvalue())

    def test_device_environment_removes_prior_automation_without_losing_xcode(self):
        with patch.dict(energy.os.environ, {"CROWN_ENERGY_REQUEST": "stale", "CROWN_HAPTIC_COMPARISON": "stale",
                                         "CROWN_START_DIAGNOSTICS": "stale", "DEVICECTL_CHILD_TEST": "stale",
                                         "DEVELOPER_DIR": "/chosen/Xcode"}, clear=True):
            self.assertEqual(energy.clean_device_environment(), {"DEVELOPER_DIR": "/chosen/Xcode"})

    def test_automated_crown_control_requires_actual_input_and_driver(self):
        data = fixture(scenario="crown-no-haptics")
        for sample in data["samples"]:
            sample["hapticRequests"] = 0
        data["metadata"]["inputDriver"] = "xcuitest-crown-v1"
        self.assertEqual(energy.validate(data), [])
        data["samples"][-1]["hapticRequests"] = 1
        self.assertIn("Haptics occurred in the haptics-disabled control.", energy.validate(data))
        data["metadata"].pop("inputDriver")
        self.assertIn("Automated Crown run has an invalid input driver.", energy.validate(data))

    def test_input_driver_and_crown_profile_are_separate_comparison_conditions(self):
        baseline = fixture()
        for key, value in (("inputDriver", "xcuitest-crown-v1"), ("crownInputProfile", "different-speed"),
                           ("displayPolicy", "different-display-policy"), ("builtSDK", "different-SDK"),
                           ("xcodeBuild", "different-Xcode"), ("wakeTapIntervalSeconds", "different-interval"),
                           ("statusPollIntervalSeconds", "different-interval")):
            changed = copy.deepcopy(baseline)
            changed["metadata"][key] = value
            self.assertNotEqual(energy.comparison_key(baseline), energy.comparison_key(changed))

    def test_fixed_replay_rejects_wrong_cadence_and_extra_scrolls(self):
        valid = fixture(activity=2)
        valid["configuration"]["stepsPerSecond"] = 2
        valid["metadata"]["inputDriver"] = "app-scroll-replay-v1"
        self.assertEqual(energy.validate(valid), [])
        for rate in (1.9, 2.1):
            data = fixture(activity=rate)
            data["configuration"]["stepsPerSecond"] = 2
            data["metadata"]["inputDriver"] = "app-scroll-replay-v1"
            self.assertIn("Automated replay did not maintain the fixed scroll rate.", energy.validate(data))
        extra = copy.deepcopy(valid)
        extra["samples"][-1]["scrollEvents"] += 3
        extra["samples"][-1]["hapticRequests"] += 3
        self.assertIn("Automated replay did not maintain the fixed scroll rate.", energy.validate(extra))

    def test_fixed_replay_allows_one_pending_endpoint_tick(self):
        data = fixture(scenario="replay-no-haptics", activity=2)
        data["configuration"]["stepsPerSecond"] = 2
        data["metadata"]["inputDriver"] = "app-scroll-replay-v1"
        data["samples"][-1]["scrollEvents"] -= 1
        data["samples"][-1]["replaySteps"] -= 1
        self.assertEqual(energy.validate(data), [])

    def test_automated_idle_requires_active_display_and_regular_samples(self):
        data = fixture(scenario="idle", activity=0)
        data["metadata"]["inputDriver"] = "app-idle-v1"
        self.assertEqual(energy.validate(data), [])
        inactive = copy.deepcopy(data)
        inactive["samples"][5].update(scenePhase="inactive", luminanceReduced=True)
        self.assertIn("Active-use run lost the foreground or entered Always On.", energy.validate(inactive))
        inactive["metadata"].pop("inputDriver")
        self.assertEqual(energy.validate(inactive), [])
        del data["samples"][1:5]
        self.assertIn("Sampling was interrupted.", energy.validate(data))

    def test_idle_rejects_unexpected_work_even_without_haptic_calls(self):
        for counter in ("scrollEvents", "hapticRequests", "replaySteps"):
            data = fixture(scenario="idle", activity=0)
            data["metadata"]["inputDriver"] = "app-idle-v1"
            data["samples"][-1][counter] = 1
            self.assertIn("Input or haptics occurred during the idle control.", energy.validate(data))

    def test_ui_test_target_discovery_supports_both_xctestrun_formats(self):
        target = {"BlueprintName": "CrownSpinEnergyUITests", "IsUITestBundle": True,
                  "EnvironmentVariables": {"EXISTING": "preserve"}}
        for structure in ({"CrownSpinEnergyUITests": target},
                          {"TestConfigurations": [{"TestTargets": [target]}]}):
            found = energy.automation_test_targets(structure)
            self.assertEqual(found, [target])
            self.assertEqual(found[0]["EnvironmentVariables"]["EXISTING"], "preserve")

    def test_fixture_metrics_use_percentage_points_per_hour(self):
        data = fixture()
        self.assertEqual(energy.validate(data), [])
        rate, activity, drop = energy.metrics(data)
        self.assertAlmostEqual(rate, 18)
        self.assertEqual(activity, 5)
        self.assertAlmostEqual(drop, 3)

    def test_simulator_charging_unknown_and_interruption_are_rejected(self):
        for mutate in (
            lambda r: r["metadata"].update(simulator="true"),
            lambda r: r["samples"][10].update(powerState="charging"),
            lambda r: r["samples"][0].update(batteryLevel=None),
            lambda r: r.update(status="interrupted"),
            lambda r: r["samples"][10].update(luminanceReduced=True),
        ):
            with self.subTest(mutation=mutate):
                data = fixture()
                mutate(data)
                self.assertTrue(energy.validate(data))

    def test_no_haptics_replay_is_valid_but_motor_calls_are_rejected(self):
        data = fixture(scenario="replay-no-haptics")
        self.assertEqual(energy.validate(data), [])
        data["samples"][-1]["hapticRequests"] = 1
        self.assertIn("Haptics occurred in the haptics-disabled control.", energy.validate(data))

    def test_replay_rate_and_sampling_gaps_are_checked(self):
        data = fixture(activity=1)
        self.assertIn("Replay did not maintain the requested rate.", energy.validate(data))
        data = fixture()
        del data["samples"][1:5]
        self.assertIn("Sampling was interrupted.", energy.validate(data))

    def test_invalid_numbers_and_decreasing_counts_are_rejected(self):
        for field, value in (("batteryLevel", float("nan")), ("elapsedSeconds", float("inf")),
                             ("hapticRequests", -1), ("batteryLevel", True)):
            data = fixture()
            data["samples"][-1][field] = value
            self.assertTrue(energy.validate(data))
        data = fixture()
        data["samples"][5]["scrollEvents"] = 0
        self.assertIn("Activity counters decreased.", energy.validate(data))

    def test_comparison_separates_hardware_display_settings_and_workload(self):
        baseline = fixture()
        for key, value in (("hardwareModel", "different-Watch"), ("watchOS", "different-OS"),
                           ("ambientMode", "false"), ("numberSystem", "roman")):
            data = copy.deepcopy(baseline)
            data["metadata"][key] = value
            self.assertNotEqual(energy.comparison_key(baseline), energy.comparison_key(data))
        data = copy.deepcopy(baseline)
        data["configuration"]["stepsPerSecond"] = 10
        self.assertNotEqual(energy.comparison_key(baseline), energy.comparison_key(data))

    def analyse(self, reports):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()) as output:
            for index, report in enumerate(reports):
                Path(directory, f"{index}.json").write_text(json.dumps(report))
            result = energy.analyse(argparse.Namespace(reports=[Path(directory)], before="baseline", after="optimized"))
            return result, output.getvalue()

    def repeats(self, scenario="replay", after_activity=5, after_drop=.02):
        reports = []
        for label in ("baseline", "optimized"):
            for index in range(3):
                data = fixture(label, scenario=scenario,
                               activity=after_activity if label == "optimized" else 5,
                               drop=after_drop if label == "optimized" else .03)
                data["runID"] += f"-{index}"
                reports.append(data)
        return reports

    def test_comparison_requires_repetitions_and_source_fingerprints(self):
        _, text = self.analyse([fixture(), fixture("optimized")])
        self.assertIn("Need at least three repetitions", text)
        reports = self.repeats()
        reports[-1]["metadata"]["sourceFingerprint"] = "different-build"
        _, text = self.analyse(reports)
        self.assertIn("Mixed or missing source fingerprints", text)

    def test_duplicate_runs_cannot_create_fake_repetitions(self):
        _, text = self.analyse([fixture(), fixture(), fixture("optimized")])
        self.assertIn("duplicate run ID", text)
        self.assertIn("Need at least three repetitions", text)

    def test_manual_rate_mismatch_prevents_improvement_claim(self):
        _, text = self.analyse(self.repeats(scenario="manual", after_activity=2))
        self.assertIn("input rates differ", text)
        self.assertNotIn("Observed median change", text)

    def test_actual_replay_rate_mismatch_prevents_improvement_claim(self):
        _, text = self.analyse(self.repeats(after_activity=4.6))
        self.assertIn("input rates differ by more than 5%", text)
        self.assertNotIn("Observed median change", text)

    def test_different_starting_charge_prevents_improvement_claim(self):
        reports = self.repeats()
        for report in reports[3:]:
            for sample in report["samples"]:
                sample["batteryLevel"] -= .07
        _, text = self.analyse(reports)
        self.assertIn("Starting battery levels differ", text)
        self.assertNotIn("Observed median change", text)

    def test_zero_drop_does_not_claim_zero_power(self):
        _, text = self.analyse(self.repeats(after_drop=0))
        self.assertIn("did not resolve the drain", text)
        self.assertNotIn("Observed median change", text)

    def test_matched_runs_report_observation_without_claiming_proof(self):
        _, text = self.analyse(self.repeats())
        self.assertIn("Observed median change: -6.0 pp/hour", text)
        self.assertIn("not proof of savings", text)


if __name__ == "__main__":
    unittest.main()
