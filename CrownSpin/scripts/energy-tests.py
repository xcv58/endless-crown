#!/usr/bin/env python3
"""Build, retrieve, and compare local Watch battery-test reports. Python standard library only."""
import argparse
import base64
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import plistlib
import statistics
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "CrownSpin/CrownSpin.xcodeproj"
BUNDLE_ID = "media.jenny.crownspin.watchapp"
AUTOMATION_VARIANTS = {
    "legacy-unqualified": [],
    "original": ["HAPTIC_LEGACY_STATS", "HAPTIC_LEGACY_TIMER",
                 "HAPTIC_LEGACY_MENU_TIMER", "HAPTIC_LEGACY_PERSISTENCE"],
    "timer-only": ["HAPTIC_LEGACY_STATS", "HAPTIC_LEGACY_PERSISTENCE"],
    "persistence-only": ["HAPTIC_LEGACY_STATS", "HAPTIC_LEGACY_TIMER",
                         "HAPTIC_LEGACY_MENU_TIMER"],
    "optimized": ["HAPTIC_LEGACY_STATS"],
}
DEFAULT_VARIANT = "optimized"  # The current ordinary app's observation/timer/persistence paths.


def compilation_flags(variant=None):
    variant = variant or DEFAULT_VARIANT
    if variant not in AUTOMATION_VARIANTS:
        raise ValueError("Unknown automation build variant.")
    return ["ENERGY_TESTING", *AUTOMATION_VARIANTS[variant]]


def build_fingerprint(variant=None):
    source = source_fingerprint()
    # Existing source-only identities remain available by explicit selection.
    return source if variant == "legacy-unqualified" else hashlib.sha256(
        (source + "\0" + " ".join(compilation_flags(variant))).encode()).hexdigest()


def clean_device_environment():
    return {key: value for key, value in os.environ.items()
            if not key.startswith("DEVICECTL_CHILD_") and not key.startswith("CROWN_")}


def source_fingerprint():
    digest = hashlib.sha256()
    directories = [ROOT / "CrownSpin" / name for name in
                   ("CrownSpin Watch App", "CrownSpin Complication", "CrownSpinTests", "CrownSpinEnergyUITests")]
    paths = sorted(path for directory in directories for path in directory.rglob("*")
                   if path.is_file() and not any(part.startswith(".") for part in path.relative_to(directory).parts))
    paths += [PROJECT / "project.pbxproj"]
    for path in paths:
        if any(part in {"build", "DerivedData", ".build"} for part in path.parts):
            continue
        digest.update(str(path.relative_to(ROOT)).encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def build(args):
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    destination = f"id={args.device}" if args.device else "generic/platform=watchOS"
    automation = getattr(args, "automation", False)
    variant = getattr(args, "variant", None)
    command = ["xcodebuild", "-project", str(PROJECT), "-scheme", "CrownSpin Energy" if automation else "CrownSpin Watch App",
               "-configuration", "Release", "-destination", destination,
               "-derivedDataPath", str(args.output.resolve()),
               "SWIFT_ACTIVE_COMPILATION_CONDITIONS=$(inherited) " + " ".join(compilation_flags(variant)),
               f"ENERGY_SOURCE_REVISION={revision}",
               f"ENERGY_SOURCE_FINGERPRINT={build_fingerprint(variant)}"]
    if not args.device or args.unsigned:
        command.append("CODE_SIGNING_ALLOWED=NO")
    if args.allow_provisioning_updates:
        command.append("-allowProvisioningUpdates")
    command.append("build-for-testing" if automation else "build")
    subprocess.run(command, check=True, cwd=ROOT, env=clean_device_environment())
    print(f"App: {args.output.resolve() / 'Build/Products/Release-watchos/CrownSpin Watch App.app'}")
    if not args.device or args.unsigned:
        print("Compile-only unsigned app. Build for your Watch with --device before installing.")


def fetch(args):
    # CoreDevice requires the local destination directory to exist.
    args.output.mkdir(parents=True, exist_ok=True)
    subprocess.run(["xcrun", "devicectl", "device", "copy", "from", "--device", args.device,
                    "--domain-type", "appDataContainer", "--domain-identifier", BUNDLE_ID,
                    "--source", "Documents/EnergyTests", "--destination", str(args.output.resolve())], check=True)


def verify(args):
    """Run reports, statistics, and a source-extracted menu timer on the Mac, without motor/UI claims."""
    with tempfile.TemporaryDirectory(prefix="crown-energy-tests-") as directory:
        temporary = Path(directory)
        sources = temporary / "Sources/EnergyTestModel"
        tests = temporary / "Tests/EnergyTestModelTests"
        sources.mkdir(parents=True)
        tests.mkdir(parents=True)
        (temporary / "Package.swift").write_text('''// swift-tools-version: 5.9
import PackageDescription
let package = Package(name: "EnergyTestModel", platforms: [.macOS(.v14)], targets: [
    .target(name: "EnergyTestModel", swiftSettings: [.define("ENERGY_TESTING")]),
    .testTarget(name: "EnergyTestModelTests", dependencies: ["EnergyTestModel"],
                swiftSettings: [.define("ENERGY_TESTING")])
])
''')
        (sources / "EnergyTestReport.swift").write_text(
            (ROOT / "CrownSpin/CrownSpin Watch App/EnergyTestReport.swift").read_text())
        (tests / "EnergyTestReportTests.swift").write_text(
            "@testable import EnergyTestModel\n" +
            (ROOT / "CrownSpin/CrownSpinTests/EnergyTestReportTests.swift").read_text())
        (sources / "HapticStats.swift").write_text(
            (ROOT / "CrownSpin/CrownSpin Watch App/HapticStats.swift").read_text())
        # Keep the actual number helpers; only the WatchKit effect enum is omitted on macOS.
        pattern_source = (ROOT / "CrownSpin/CrownSpin Watch App/HapticPattern.swift").read_text()
        suite_line = next(line for line in pattern_source.splitlines() if line.startswith("let appGroupSuiteName ="))
        (sources / "NumberFormatting.swift").write_text(
            "import Foundation\n" + suite_line + "\n" +
            pattern_source[pattern_source.index("enum NumberSystem:"):])
        (tests / "HapticStatsTests.swift").write_text(
            "@testable import EnergyTestModel\n" +
            (ROOT / "CrownSpin/CrownSpinTests/HapticStatsTests.swift").read_text())
        view_source = (ROOT / "CrownSpin/CrownSpin Watch App/ContentView.swift").read_text()
        menu_method = view_source[view_source.index("    private func revealMenuButton() {"):
                                  view_source.index("    // MARK: - Persistence")]
        menu_delay = next(line.strip() for line in view_source.splitlines()
                          if "static let menuAutoHideDelay:" in line)
        (sources / "MenuTimerProbe.swift").write_text(
            "import SwiftUI\n"
            "final class MenuRuntimeProbe {\n"
            "    func beginWork() -> TimeInterval? { nil }\n"
            "    func endWork(_ name: String, since start: TimeInterval?) {}\n}\n"
            "final class MenuTimerProbe {\n    let energyTests = MenuRuntimeProbe()\n"
            "    enum Constants { " + menu_delay + " }\n"
            "    var menuButtonTimer: Timer?\n    var isMenuButtonHidden = false\n"
            "    var showMenuButton = true\n    var showMenu = false\n"
            "    var isBlackDisplay = false\n"
            "    deinit { menuButtonTimer?.invalidate() }\n" +
            # A class holder needs explicit capture; ContentView's value-type method does not.
            menu_method.replace("private func revealMenuButton", "func revealMenuButton")
                       .replace("DispatchQueue.main.async {", "DispatchQueue.main.async { [self] in") + "}\n")
        (tests / "ScrollOverheadTimerTests.swift").write_text(
            "@testable import EnergyTestModel\n" +
            (ROOT / "CrownSpin/scripts/tests/ScrollOverheadTimerTests.swift").read_text())
        subprocess.run(["xcrun", "swift", "test", "--package-path", str(temporary)], check=True)
    subprocess.run([sys.executable, "-m", "unittest", "discover", "-s",
                    str(ROOT / "CrownSpin/scripts/tests"), "-p", "test_*.py", "-v"], check=True)


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate(report):
    """Do not trust an unflagged report as proof of a completed physical battery run."""
    issues = list(report.get("issues", []))
    config, metadata = report.get("configuration", {}), report.get("metadata", {})
    requires_active_display = config.get("scenario") != "idle" or metadata.get("inputDriver") == "app-idle-v1"
    samples = report.get("samples", [])
    if report.get("schemaVersion") != 1:
        issues.append("Unsupported report version.")
    if metadata.get("simulator") != "false":
        issues.append("Not a physical Watch battery measurement.")
    if report.get("status") != "completed":
        issues.append("Run did not complete.")
    duration, rate = config.get("durationSeconds"), config.get("stepsPerSecond")
    if not number(duration) or not 15 <= duration <= 3600:
        issues.append("Invalid duration.")
    if not number(rate) or not 1 <= rate <= 10:
        issues.append("Invalid replay rate.")
    if not config.get("conditions", "").strip() or not config.get("label", "").strip():
        issues.append("Missing build label or test conditions.")
    if config.get("scenario") not in {"idle", "manual", "crown", "crown-no-haptics", "replay", "replay-no-haptics"}:
        issues.append("Unknown scenario.")
    if len(samples) < 2:
        return sorted(set(issues + ["Missing battery endpoints."]))
    for sample in samples:
        level = sample.get("batteryLevel")
        if not number(level) or not 0 <= level <= 1:
            issues.append("Battery level unavailable.")
        if sample.get("powerState") != "unplugged":
            issues.append("Charging or unknown battery state observed.")
        if not number(sample.get("elapsedSeconds")):
            issues.append("Invalid sample time.")
        if sample.get("thermalState", 2) >= 2:
            issues.append("Serious or critical thermal state observed.")
        for counter in ("scrollEvents", "hapticRequests", "replaySteps"):
            if type(sample.get(counter)) is not int or sample[counter] < 0:
                issues.append("Invalid activity counters.")
        if requires_active_display and (
                sample.get("scenePhase") != "active" or sample.get("luminanceReduced") is not False):
            issues.append("Active-use run lost the foreground or entered Always On.")
    if issues:
        return sorted(set(issues))
    elapsed = samples[-1]["elapsedSeconds"] - samples[0]["elapsedSeconds"]
    if abs(elapsed - duration) > max(2, duration * .02):
        issues.append("Measured duration differs from requested duration.")
    for previous, sample in zip(samples, samples[1:]):
        if sample["elapsedSeconds"] <= previous["elapsedSeconds"]:
            issues.append("Non-monotonic samples.")
        if requires_active_display and sample["elapsedSeconds"] - previous["elapsedSeconds"] > 60:
            issues.append("Sampling was interrupted.")
        if any(sample[key] < previous[key] for key in ("scrollEvents", "hapticRequests", "replaySteps")):
            issues.append("Activity counters decreased.")
    if samples[-1]["batteryLevel"] > samples[0]["batteryLevel"] + .00001:
        issues.append("Battery level increased during the run.")
    last = samples[-1]
    if config["scenario"] == "idle" and (last["scrollEvents"] or last["hapticRequests"] or last["replaySteps"]):
        issues.append("Input or haptics occurred during the idle control.")
    elif config["scenario"] == "manual" and not (last["scrollEvents"] and last["hapticRequests"]):
        issues.append("No real Crown activity was captured.")
    elif config["scenario"] in {"crown", "crown-no-haptics"}:
        if metadata.get("inputDriver") != "xcuitest-crown-v1" or last["replaySteps"]:
            issues.append("Automated Crown run has an invalid input driver.")
        if not last["scrollEvents"]:
            issues.append("No automated Crown activity was captured.")
        if config["scenario"] == "crown-no-haptics" and last["hapticRequests"]:
            issues.append("Haptics occurred in the haptics-disabled control.")
        if config["scenario"] == "crown" and last["hapticRequests"] != last["scrollEvents"]:
            issues.append("Haptic requests did not match scroll events.")
    elif config["scenario"].startswith("replay"):
        if last["replaySteps"] < duration * rate * .9:
            issues.append("Replay did not maintain the requested rate.")
        if metadata.get("inputDriver") == "app-scroll-replay-v1" and (
                abs(last["replaySteps"] - duration * rate) > max(2, duration * rate * .02) or
                abs(last["scrollEvents"] - last["replaySteps"]) > 2):
            issues.append("Automated replay did not maintain the fixed scroll rate.")
        if not last["replaySteps"] or abs(last["scrollEvents"] - last["replaySteps"]) > max(2, last["replaySteps"] * .1):
            issues.append("Scroll events did not match replay steps.")
        if config["scenario"] == "replay-no-haptics" and last["hapticRequests"]:
            issues.append("Haptics occurred in the haptics-disabled control.")
        if config["scenario"] == "replay" and last["hapticRequests"] != last["scrollEvents"]:
            issues.append("Haptic requests did not match scroll events.")
    if config.get("captureRuntimeProfile") is True:
        issues.extend(validate_runtime_profile(report))
    return sorted(set(issues))


def validate_runtime_profile(report):
    profile = report.get("runtimeProfile", {})
    runtime = profile.get("samples", []) if isinstance(profile, dict) else []
    samples = report.get("samples", [])
    if len(runtime) < 2 or len(runtime) != len(samples):
        return ["Missing runtime profile endpoints or workload coverage."]
    if report.get("metadata", {}).get("diagnosticPurpose") != "runtime-profile-v1":
        return ["Runtime capture is missing its profiling-only identity."]
    previous = None
    for actual, battery in zip(runtime, samples):
        if not isinstance(actual, dict) or any(not number(actual.get(key)) or actual[key] < 0
            for key in ("elapsedSeconds", "userCPUSeconds", "systemCPUSeconds")) or \
                abs(actual["elapsedSeconds"] - battery["elapsedSeconds"]) > .1 or \
                not isinstance(actual.get("contentViewBodyUpdates"), int) or actual["contentViewBodyUpdates"] < 0 or \
                not isinstance(actual.get("work"), dict):
            return ["Invalid runtime profile counters or workload coverage."]
        for timing in actual["work"].values():
            if not isinstance(timing, dict) or not isinstance(timing.get("calls"), int) or timing["calls"] < 0 or \
                    any(not number(timing.get(key)) or timing[key] < 0 for key in ("totalWallSeconds", "maximumWallSeconds")) or \
                    timing["maximumWallSeconds"] > timing["totalWallSeconds"] + .000001:
                return ["Invalid runtime work timing."]
        if previous:
            if actual["elapsedSeconds"] <= previous["elapsedSeconds"] or any(actual[key] < previous[key]
                for key in ("userCPUSeconds", "systemCPUSeconds", "contentViewBodyUpdates")) or any(
                key not in actual["work"] or actual["work"][key]["calls"] < timing["calls"] or
                actual["work"][key]["totalWallSeconds"] < timing["totalWallSeconds"]
                for key, timing in previous["work"].items()):
                return ["Non-monotonic runtime profile counters."]
        previous = actual
    return []


def comparison_key(report):
    config, meta = report["configuration"], report["metadata"]
    return (config["scenario"], config["pattern"], config["durationSeconds"],
            config["stepsPerSecond"] if config["scenario"].startswith("replay") else None,
            config["conditions"], *(meta.get(key, "unknown") for key in
                ("hardwareModel", "watchOS", "ambientMode", "displayMode", "numberSystem", "menuHidden", "diagnosticVersion",
                 "inputDriver", "crownInputProfile", "displayPolicy", "builtSDK", "xcodeBuild",
                 "wakeTapIntervalSeconds", "statusPollIntervalSeconds")),
            report["samples"][0]["thermalState"])


def metrics(report):
    first, last = report["samples"][0], report["samples"][-1]
    seconds = last["elapsedSeconds"] - first["elapsedSeconds"]
    drop = (first["batteryLevel"] - last["batteryLevel"]) * 100
    return drop * 3600 / seconds, last["scrollEvents"] / seconds, drop


def automation_test_targets(value):
    """Support both Xcode xctestrun formats without rewriting unrelated settings."""
    result = []
    if isinstance(value, dict):
        if value.get("IsUITestBundle") and value.get("BlueprintName") == "CrownSpinEnergyUITests":
            result.append(value)
        else:
            for child in value.values():
                result.extend(automation_test_targets(child))
    elif isinstance(value, list):
        for child in value:
            result.extend(automation_test_targets(child))
    return result


def automate(args):
    if not (15 <= args.seconds <= 900 and 1 <= args.repetitions <= 6 and 0 <= args.cooldown <= 600):
        raise ValueError("Use 15–900 seconds, 1–6 repetitions, and 0–600 seconds of cooldown.")
    cases = args.cases.split(",")
    if not cases or any(case not in {"crown", "crown-no-haptics", "replay", "replay-no-haptics", "idle"} for case in cases):
        raise ValueError("Cases must be crown, crown-no-haptics, replay, replay-no-haptics, or idle.")
    if not number(args.steps_per_second) or not 1 <= args.steps_per_second <= 10:
        raise ValueError("Replay rate must be 1–10 scroll changes per second.")
    if (not number(args.crown_delta) or not .05 <= abs(args.crown_delta) <= 5 or
            not number(args.crown_velocity) or not .1 <= args.crown_velocity <= 5 or
            not number(args.pause) or not 0 <= args.pause <= 10):
        raise ValueError("Invalid automated Crown workload.")
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    session = args.output / str(uuid.uuid4())
    session.mkdir()
    drivers = sorted({"app-scroll-replay-v1" if case.startswith("replay") else
                      "app-idle-v1" if case == "idle" else "xcuitest-crown-v1" for case in cases})
    manifest = {"sessionID": session.name, "device": args.device, "label": args.label,
                "variant": getattr(args, "variant", None) or DEFAULT_VARIANT,
                "inputDrivers": drivers, "runs": [], "status": "preparing"}
    manifest_path = session / "session.json"

    def save_manifest():
        manifest_path.write_text(json.dumps(manifest, indent=2))

    save_manifest()
    print(f"Automation session: {session}", flush=True)
    try:
        if not args.skip_build:
            print("Building signed Release app and UI-test runner…", flush=True)
            with (session / "build.log").open("w") as log:
                revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
                command = ["xcodebuild", "-project", str(PROJECT), "-scheme", "CrownSpin Energy",
                    "-configuration", "Release", "-destination", f"id={args.device}",
                    "-derivedDataPath", str(args.build_output.resolve()),
                    "SWIFT_ACTIVE_COMPILATION_CONDITIONS=$(inherited) " +
                    " ".join(compilation_flags(getattr(args, "variant", None))),
                    f"ENERGY_SOURCE_REVISION={revision}",
                    f"ENERGY_SOURCE_FINGERPRINT={build_fingerprint(getattr(args, 'variant', None))}"]
                if args.allow_provisioning_updates:
                    command.append("-allowProvisioningUpdates")
                subprocess.run(command + ["build-for-testing"], cwd=ROOT, stdout=log,
                               stderr=subprocess.STDOUT, check=True, env=clean_device_environment())
        app = args.build_output / "Build/Products/Release-watchos/CrownSpin Watch App.app"
        app_info = plistlib.loads((app / "Info.plist").read_bytes())
        fingerprint = app_info.get("EnergySourceFingerprint")
        if not fingerprint or fingerprint != build_fingerprint(getattr(args, "variant", None)):
            raise ValueError("Built app does not match current sources. Rebuild before measuring.")
        manifest["sourceFingerprint"] = fingerprint
        test_files = sorted((args.build_output / "Build/Products").glob("*.xctestrun"),
                            key=lambda path: path.stat().st_mtime, reverse=True)
        if not test_files:
            raise ValueError("No built UI test configuration found.")
        original = plistlib.loads(test_files[0].read_bytes())
        if len(automation_test_targets(original)) != 1:
            raise ValueError("Expected exactly one CrownSpinEnergyUITests target.")
        reports_directory = session / "reports"
        manifest["status"] = "running"
        save_manifest()
        # Rotate case order between repetitions to reduce always-testing-one-case-last bias.
        schedule = [case for repeat in range(args.repetitions)
                    for case in cases[repeat % len(cases):] + cases[:repeat % len(cases)]]
        for index, case in enumerate(schedule):
            run_id = str(uuid.uuid4()).upper()
            request = {"runID": run_id, "configuration": {"scenario": case, "label": args.label,
                       "durationSeconds": args.seconds, "stepsPerSecond": args.steps_per_second if case.startswith("replay") or case == "idle" else 5,
                       "pattern": args.pattern, "conditions": args.conditions},
                       "crownDelta": args.crown_delta, "crownVelocity": args.crown_velocity,
                       "pauseSeconds": args.pause}
            if getattr(args, "runtime_profile", False):
                request["configuration"]["captureRuntimeProfile"] = True
            configuration = copy.deepcopy(original)
            target = automation_test_targets(configuration)[0]
            target["UITargetAppMainThreadCheckerEnabled"] = False
            target["UITargetAppPerformanceAntipatternCheckerEnabled"] = False
            target["PreferredScreenCaptureFormat"] = "screenshot"
            for environment_name in ("EnvironmentVariables", "TestingEnvironmentVariables", "UITargetAppEnvironmentVariables"):
                environment = target.get(environment_name, {})
                for key in list(environment):
                    if key.startswith("CROWN_") or key.startswith("DEVICECTL_CHILD_"):
                        environment.pop(key)
                libraries = environment.get("DYLD_INSERT_LIBRARIES", "").split(":")
                libraries = [item for item in libraries if item and "libMainThreadChecker" not in item]
                if libraries:
                    environment["DYLD_INSERT_LIBRARIES"] = ":".join(libraries)
                else:
                    environment.pop("DYLD_INSERT_LIBRARIES", None)
            target.setdefault("EnvironmentVariables", {})["CROWN_ENERGY_REQUEST"] = \
                base64.b64encode(json.dumps(request).encode()).decode()
            test_path = session / f"{index + 1:02d}-{case}.xctestrun"
            test_path.write_bytes(plistlib.dumps(configuration))
            # __TESTROOT__ paths are relative to the xctestrun file; preserve the built products root.
            root = str(test_files[0].parent.resolve())
            def resolve_paths(value):
                if isinstance(value, dict):
                    return {key: resolve_paths(child) for key, child in value.items()}
                if isinstance(value, list):
                    return [resolve_paths(child) for child in value]
                return value.replace("__TESTROOT__", root) if isinstance(value, str) else value
            test_path.write_bytes(plistlib.dumps(resolve_paths(configuration)))
            entry = {"runID": run_id, "scenario": case, "status": "running"}
            manifest["runs"].append(entry)
            save_manifest()
            print(f"Run {index + 1}/{len(schedule)}: {case}, {args.seconds:g} seconds", flush=True)
            command = ["xcodebuild", "test-without-building", "-xctestrun", str(test_path),
                       "-destination", f"id={args.device}", "-parallel-testing-enabled", "NO",
                       "-enableCodeCoverage", "NO", "-collect-test-diagnostics", "never",
                       "-resultBundlePath", str(session / f"{index + 1:02d}-{case}.xcresult"),
                       "-test-timeouts-enabled", "YES", "-maximum-test-execution-time-allowance",
                       str(int(args.seconds + 150))]
            with (session / f"{index + 1:02d}-{case}.log").open("w") as log:
                result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                        timeout=args.seconds + 240, env=clean_device_environment())
            entry["testExitCode"] = result.returncode
            # Retrieve only after the measured run. No polling/file transfer while measuring.
            with (session / "fetch.log").open("a") as log:
                reports_directory.mkdir(exist_ok=True)
                fetched = subprocess.run(["xcrun", "devicectl", "device", "copy", "from", "--device", args.device,
                    "--domain-type", "appDataContainer", "--domain-identifier", BUNDLE_ID,
                    "--source", "Documents/EnergyTests", "--destination", str(reports_directory),
                    "--timeout", "30"], stdout=log, stderr=subprocess.STDOUT, env=clean_device_environment())
            matching = list(reports_directory.rglob(f"{run_id}.json")) if fetched.returncode == 0 else []
            if len(matching) != 1:
                entry["status"] = "failed"
                save_manifest()
                raise ValueError(f"Run {run_id} did not produce one retrievable report "
                                 f"(UI test exit {result.returncode}). See {session / f'{index + 1:02d}-{case}.log'}.")
            report = json.loads(matching[0].read_text())
            issues = validate(report)
            if report["metadata"].get("sourceFingerprint") != fingerprint:
                issues.append("Installed app differs from the built source fingerprint.")
            entry.update(status="completed" if not issues and result.returncode == 0 else "flagged",
                         issues=issues, report=str(matching[0]))
            save_manifest()
            if entry["status"] != "completed":
                raise ValueError(f"Run was invalid; batch stopped. See {session}.")
            rate, activity, drop = metrics(report)
            print(f"  Saved: {drop:.2f} pp; {rate:.1f} pp/hour; {activity:.2f} scroll events/sec", flush=True)
            if index + 1 < len(schedule) and args.cooldown:
                print(f"Cooldown: {args.cooldown:g} seconds", flush=True)
                time.sleep(args.cooldown)
        manifest["status"] = "completed"
        save_manifest()
        return analyse(argparse.Namespace(reports=[reports_directory], before=args.label, after="optimized"))
    except BaseException as error:
        manifest.update(status="stopped", error=str(error))
        save_manifest()
        raise


def analyse(args):
    paths = set()
    for path in args.reports:
        paths.update(path.rglob("*.json") if path.is_dir() else [path])
    groups, seen, excluded_count = {}, set(), 0
    for path in sorted(paths):
        try:
            report = json.loads(path.read_text())
            problems = validate(report)
            run_id = report.get("runID")
            if not run_id or run_id in seen:
                problems.append("Missing or duplicate run ID.")
            if problems:
                print(f"FLAGGED {path.name}: {'; '.join(problems)}")
                continue
            seen.add(run_id)
            if report["configuration"].get("captureRuntimeProfile") is True:
                print(f"PROFILE {path.name}: excluded from battery comparison")
                excluded_count += 1
                continue
            if report["configuration"].get("captureHapticTiming") is True or \
                    report["metadata"].get("diagnosticPurpose") == "haptic-timing-only":
                print(f"TIMING {path.name}: excluded from battery comparison")
                excluded_count += 1
                continue
            rate, activity, drop = metrics(report)
            config = report["configuration"]
            print(f"{config['label']} / {config['scenario']} / {config['pattern']}: "
                  f"{drop:.2f} pp over {report['samples'][-1]['elapsedSeconds']:.0f}s; "
                  f"{rate:.1f} pp/hour; {activity:.2f} scroll events/sec")
            groups.setdefault(comparison_key(report), {}).setdefault(config["label"], []).append(report)
        except (ValueError, KeyError, TypeError, AttributeError, OSError) as error:
            print(f"FLAGGED {path.name}: malformed report ({error})")
    if not groups:
        print("No valid physical Watch runs to compare.")
        return 0 if excluded_count else 1
    for key, labels in groups.items():
        print(f"\nMatched condition: {key[0]} / {key[1]} / {key[2]:g}s / {key[4]}")
        for label, runs in sorted(labels.items()):
            rates = [metrics(run)[0] for run in runs]
            print(f"  {label}: n={len(runs)}, median={statistics.median(rates):.1f} pp/hour, "
                  f"range={min(rates):.1f}–{max(rates):.1f}")
        if args.before not in labels or args.after not in labels:
            print("  Need both requested build labels for a comparison.")
            continue
        before, after = labels[args.before], labels[args.after]
        if min(len(before), len(after)) < 3:
            print("  Need at least three repetitions per build; no improvement conclusion.")
            continue
        if any(len({r["metadata"].get("sourceFingerprint", "unknown") for r in runs}) != 1
               or any(r["metadata"].get("sourceFingerprint", "unknown") in ("unknown", "") for r in runs)
               for runs in (before, after)):
            print("  Mixed or missing source fingerprints; cannot compare build labels.")
            continue
        if key[0] != "idle":
            activity_before = statistics.median(metrics(r)[1] for r in before)
            activity_after = statistics.median(metrics(r)[1] for r in after)
            tolerance = .1 if key[0] == "manual" else .05
            if abs(activity_after / activity_before - 1) > tolerance:
                print(f"  Observed input rates differ by more than {tolerance * 100:.0f}%; cannot compare.")
                continue
        start_before = statistics.median(r["samples"][0]["batteryLevel"] for r in before)
        start_after = statistics.median(r["samples"][0]["batteryLevel"] for r in after)
        if abs(start_before - start_after) > .05:
            print("  Starting battery levels differ by more than 5 percentage points; cannot compare.")
            continue
        rate_before = statistics.median(metrics(r)[0] for r in before)
        rate_after = statistics.median(metrics(r)[0] for r in after)
        if min(rate_before, rate_after) <= 0:
            print("  Battery readings did not resolve the drain; use longer runs.")
            continue
        print(f"  Observed median change: {rate_after - rate_before:+.1f} pp/hour "
              f"({(rate_after / rate_before - 1) * 100:+.1f}%).")
    print("\nBattery percentages are coarse whole-device estimates. A median difference alone is not proof of savings.")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("build", help="Build a diagnostic Release app; no install or upload")
    p.add_argument("--device", help="Physical Watch UDID; omit for an unsigned compile check")
    p.add_argument("--variant", choices=AUTOMATION_VARIANTS, default=DEFAULT_VARIANT, help="Default: current normal app paths; legacy-unqualified is an explicit historical experiment")
    p.add_argument("--unsigned", action="store_true")
    p.add_argument("--allow-provisioning-updates", action="store_true")
    p.add_argument("--output", type=Path, default=Path("/tmp/CrownSpinEnergyBuild"))
    p.set_defaults(function=build)
    p = sub.add_parser("build-automation", help="Build the signed Release app and Watch UI-test runner")
    p.add_argument("--device", required=True)
    p.add_argument("--variant", choices=AUTOMATION_VARIANTS, default=DEFAULT_VARIANT)
    p.add_argument("--allow-provisioning-updates", action="store_true")
    p.add_argument("--output", type=Path, default=Path("/tmp/CrownSpinEnergyAutomation"))
    p.set_defaults(function=build, automation=True, unsigned=False)
    p = sub.add_parser("automate", help="Build, drive Crown input or timed replay, fetch and validate repeated trials")
    p.add_argument("--device", required=True)
    p.add_argument("--variant", choices=AUTOMATION_VARIANTS, default=DEFAULT_VARIANT)
    p.add_argument("--label", default="baseline")
    p.add_argument("--conditions", default="Same Watch and unchanged settings; battery health/display settings unverified; UI testing attached")
    p.add_argument("--seconds", type=float, default=300)
    p.add_argument("--repetitions", type=int, default=3)
    p.add_argument("--cases", default="crown,crown-no-haptics")
    p.add_argument("--steps-per-second", type=float, default=2, help="Timed app replay rate; does not set Crown velocity")
    p.add_argument("--pattern", choices=["clicks", "ping", "soft", "drift", "pulse", "wave", "doubleTap",
                                        "gallop", "heartbeat", "staccato", "waltz", "buzz", "heavy", "thud"], default="clicks")
    p.add_argument("--crown-delta", type=float, default=-.5)
    p.add_argument("--crown-velocity", type=float, default=1)
    p.add_argument("--pause", type=float, default=.25)
    p.add_argument("--cooldown", type=float, default=60)
    p.add_argument("--skip-build", action="store_true")
    p.add_argument("--runtime-profile", action="store_true", help="Collect app CPU and handler wall time; exclude from battery comparisons")
    p.add_argument("--allow-provisioning-updates", action="store_true")
    p.add_argument("--build-output", type=Path, default=Path("/tmp/CrownSpinEnergyAutomation"))
    p.add_argument("--output", type=Path, default=Path("energy-test-results/automation"))
    p.set_defaults(function=automate)
    p = sub.add_parser("fetch", help="Retrieve saved reports from a connected Watch")
    p.add_argument("--device", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.set_defaults(function=fetch)
    p = sub.add_parser("verify", help="Run Swift report and Python comparison tests on this Mac")
    p.set_defaults(function=verify)
    p = sub.add_parser("analyse", help="Validate and compare exported JSON reports")
    p.add_argument("reports", nargs="+", type=Path)
    p.add_argument("--before", default="baseline")
    p.add_argument("--after", default="optimized")
    p.set_defaults(function=analyse)
    for child in sub.choices.values():
        child.add_argument("--developer-dir", type=Path, help="Use an installed Xcode for this command only")
    args = parser.parse_args()
    try:
        if args.developer_dir:
            developer_directory = args.developer_dir.resolve()
            if not (developer_directory / "usr/bin/xcodebuild").is_file():
                raise ValueError("Developer directory must contain usr/bin/xcodebuild.")
            os.environ["DEVELOPER_DIR"] = str(developer_directory)
        return args.function(args) or 0
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
