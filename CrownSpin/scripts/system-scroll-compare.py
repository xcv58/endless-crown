#!/usr/bin/env python3
"""Compare the native Watch app list and ordinary Endless Crown using one battery reader."""
import argparse
import base64
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import plistlib
import shutil
import subprocess
import time
import uuid

SCRIPTS = Path(__file__).resolve().parent
FIXTURE = SCRIPTS / "fixtures/SystemScrollBatteryUITests.swift"


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


energy = module("system_scroll_energy", "energy-tests.py")
comparison = module("system_scroll_restore", "energy-compare.py")


def save(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def environment(manifest):
    result = energy.clean_device_environment()
    result["DEVELOPER_DIR"] = manifest["developerDir"]
    return result


def prepare(args):
    session = args.session.resolve()
    session.mkdir(parents=True, exist_ok=True)
    source = session / "comparison-source/CrownSpin"
    if source.exists() or (session / "system-comparison.json").exists():
        raise ValueError("Preparation requires a fresh comparison source directory.")
    shutil.copytree(energy.ROOT / "CrownSpin", source,
                    ignore=shutil.ignore_patterns("build", "DerivedData", ".build", "scripts", "xcuserdata"))
    shutil.copyfile(FIXTURE, source / "CrownSpinEnergyUITests/EnergyAutomationUITests.swift")
    source_id = energy.source_fingerprint()
    fixture_id = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    identity = hashlib.sha256((source_id + fixture_id + "ordinary-release").encode()).hexdigest()
    manifest = {"status": "preparing", "device": args.device, "developerDir": args.developer_dir,
                "sourceFingerprint": source_id, "fixtureFingerprint": fixture_id,
                "buildFingerprint": identity, "build": str(session / "comparison-build"), "attempts": [],
                "restoreNormalBuildManifest": str(args.restore_normal.resolve()),
                "restoreSourceFingerprint": json.loads(args.restore_normal.read_text())["sourceFingerprint"],
                "productionChanges": False, "batteryReader": "WKInterfaceDevice-in-UI-test-runner"}
    save(session / "system-comparison.json", manifest)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=energy.ROOT, text=True).strip()
    command = ["xcodebuild", "-project", str(source / "CrownSpin.xcodeproj"), "-scheme", "CrownSpin Energy",
               "-configuration", "Release", "-destination", "id=" + args.device,
               "-derivedDataPath", manifest["build"],
               "SWIFT_ACTIVE_COMPILATION_CONDITIONS=$(inherited)",
               "ENERGY_SOURCE_REVISION=" + revision, "ENERGY_SOURCE_FINGERPRINT=" + identity,
               "build-for-testing"]
    with (session / "comparison-build.log").open("w") as log:
        result = subprocess.run(command, env=environment(manifest), stdout=log, stderr=subprocess.STDOUT)
    manifest["buildExitCode"] = result.returncode
    manifest["status"] = "ready" if result.returncode == 0 else "build-failed"
    if result.returncode == 0:
        product = Path(manifest["build"]) / "Build/Products/Release-watchos"
        for app in (product / "CrownSpin Watch App.app", product / "CrownSpinEnergyUITests-Runner.app"):
            subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        manifest["signatureVerified"] = True
    save(session / "system-comparison.json", manifest)
    print("Prepared ordinary Release app and common battery recorder:", session, flush=True)
    if result.returncode:
        raise ValueError("Build failed; inspect comparison-build.log.")


def configuration(session, manifest, request, name):
    product = Path(manifest["build"]) / "Build/Products"
    files = list(product.glob("*.xctestrun"))
    if len(files) != 1:
        raise ValueError("Expected one built UI test configuration.")
    value = plistlib.loads(files[0].read_bytes())
    targets = energy.automation_test_targets(value)
    if len(targets) != 1:
        raise ValueError("Expected one Watch UI test target.")
    target = targets[0]
    for key in ("EnvironmentVariables", "TestingEnvironmentVariables", "UITargetAppEnvironmentVariables"):
        env = target.setdefault(key, {})
        for variable in list(env):
            if variable.startswith(("CROWN_", "DEVICECTL_CHILD_")):
                env.pop(variable)
        env.pop("DYLD_INSERT_LIBRARIES", None)
    target["UITargetAppMainThreadCheckerEnabled"] = False
    target["UITargetAppPerformanceAntipatternCheckerEnabled"] = False
    target["PreferredScreenCaptureFormat"] = "screenshot"
    if request:
        target["EnvironmentVariables"]["CROWN_SYSTEM_SCROLL_REQUEST"] = \
            base64.b64encode(json.dumps(request).encode()).decode()

    def resolve(item):
        if isinstance(item, dict):
            return {k: resolve(v) for k, v in item.items()}
        if isinstance(item, list):
            return [resolve(v) for v in item]
        return item.replace("__TESTROOT__", str(product)) if isinstance(item, str) else item

    path = session / (name + ".xctestrun")
    path.write_bytes(plistlib.dumps(resolve(value)))
    return path


def execute(session, manifest, request, name, method="testComparison"):
    path = configuration(session, manifest, request, name)
    seconds = request["seconds"] if request else 0
    command = ["xcodebuild", "test-without-building", "-xctestrun", str(path),
               "-destination", "id=" + manifest["device"], "-parallel-testing-enabled", "NO",
               "-enableCodeCoverage", "NO", "-collect-test-diagnostics", "never",
               "-resultBundlePath", str(session / (name + ".xcresult")),
               "-only-testing:CrownSpinEnergyUITests/SystemScrollBatteryUITests/" + method,
               "-test-timeouts-enabled", "YES", "-maximum-test-execution-time-allowance", str(int(seconds + 180))]
    with (session / (name + ".log")).open("w") as log:
        process = subprocess.Popen(command, env=environment(manifest), stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            log.write(line)
            log.flush()
            if line.startswith("SYSTEM_SCROLL_") and not line.startswith("SYSTEM_SCROLL_REPORT "):
                print(line.strip(), flush=True)
        code = process.wait()
    records = [line.split(" ", 1)[1] for line in (session / (name + ".log")).read_text().splitlines()
               if line.startswith("SYSTEM_SCROLL_REPORT ")]
    report = json.loads(base64.b64decode(records[0])) if len(records) == 1 else None
    if report:
        save(session / (name + ".json"), report)
    return code, report


def validate(report, request):
    if not report:
        return ["No unique battery report was captured."]
    issues = list(report.get("issues", []))
    for key in ("runID", "condition", "mode", "delta", "velocity", "period"):
        if report.get(key) != request[key]:
            issues.append("Workload identity differs: " + key)
    if request.get("screenValidation") and report.get("screenValidation") != request["screenValidation"]:
        issues.append("Screen validation protocol differs.")
    if report.get("durationSeconds") != request["seconds"]:
        issues.append("Requested duration differs.")
    if report.get("batteryReader") != "WKInterfaceDevice-in-UI-test-runner":
        issues.append("Battery reader differs.")
    elapsed = report.get("elapsedSeconds", -1)
    if not math.isfinite(elapsed) or abs(elapsed - request["seconds"]) > 2:
        issues.append("Measured duration differs.")
    samples = report.get("samples", [])
    if len(samples) < 2 or samples[0]["elapsedSeconds"] > 1 or \
            abs(samples[-1]["elapsedSeconds"] - request["seconds"]) > 2:
        issues.append("Battery samples do not cover the measured window.")
    previous = -1
    for sample in samples:
        level, offset = sample["batteryLevel"], sample["elapsedSeconds"]
        if not math.isfinite(level) or not 0 <= level <= 1 or \
                not math.isfinite(offset) or offset < previous or (previous >= 0 and offset - previous > 40) or \
                sample["batteryState"] != 1 or sample["thermalState"] != 0 or not sample["foreground"]:
            issues.append("Invalid battery, thermal, foreground, or sample ordering.")
        if request.get("screenValidation") and sample.get("screenVerified") is not True:
            issues.append("Measured screen changed or was not verified.")
        previous = offset
    gestures = report.get("gestures", [])
    count = math.floor(request["seconds"] / request["period"]) if request["mode"] == "automated" else 0
    if len(gestures) != count:
        issues.append("Crown command count differs.")
    for index, gesture in enumerate(gestures):
        planned = index * request["period"]
        expected = request["delta"] if index % 2 == 0 else -request["delta"]
        if gesture["plannedSeconds"] != planned or gesture["delta"] != expected or \
                not 0 <= gesture["startedSeconds"] - planned <= 1 or \
                not gesture["startedSeconds"] <= gesture["endedSeconds"] <= planned + request["period"]:
            issues.append("Crown command cadence or direction differs.")
    return issues


def run(args):
    session = args.session.resolve()
    manifest = json.loads((session / "system-comparison.json").read_text())
    if manifest["status"] != "ready" or manifest["attempts"]:
        raise ValueError("Use a fresh prepared session.")
    if energy.source_fingerprint() != manifest["sourceFingerprint"] or \
            hashlib.sha256(FIXTURE.read_bytes()).hexdigest() != manifest["fixtureFingerprint"]:
        raise ValueError("Sources changed after preparation.")
    delta, velocity, period = args.delta, args.velocity, args.period
    manifest.update(status="running", mode=args.mode, durationSeconds=args.seconds,
                    crownDelta=delta, crownVelocity=velocity, crownPeriodSeconds=period,
                    nominalRotationSecondsPerCommand=delta / velocity,
                    schedule=["app-list", "app", "app", "app-list"])
    save(session / "system-comparison.json", manifest)
    try:
        for slot, condition in enumerate(manifest["schedule"], 1):
            request = {"runID": str(uuid.uuid4()), "condition": condition, "mode": args.mode,
                       "seconds": args.seconds, "delta": delta, "velocity": velocity, "period": period,
                       "screenValidation": "hittable-list-row-or-main-screen-v3"}
            name = f"trial-{slot}-{condition}"
            print(f"Trial {slot}/4: {condition}, {args.seconds:g} seconds, {args.mode}", flush=True)
            code, report = execute(session, manifest, request, name)
            issues = validate(report, request)
            entry = {"request": request, "testExitCode": code, "issues": issues,
                     "report": str(session / (name + ".json")),
                     "status": "accepted" if code == 0 and not issues else "excluded"}
            if report:
                entry["nominalRequestedRotationSeconds"] = len(report["gestures"]) * delta / velocity
                entry["totalCrownCallSeconds"] = sum(g["endedSeconds"] - g["startedSeconds"]
                                                     for g in report["gestures"])
            manifest["attempts"].append(entry)
            save(session / "system-comparison.json", manifest)
            if entry["status"] != "accepted":
                raise ValueError("Trial invalid; comparison stopped. See trial log and report.")
            first, last = report["samples"][0], report["samples"][-1]
            print(f"Recorded charge: {first['batteryLevel'] * 100:.0f}% to {last['batteryLevel'] * 100:.0f}%", flush=True)
            if slot < 4:
                time.sleep(60)
        manifest["status"] = "complete-needs-screenshot-review"
        manifest["batterySavingEstablished"] = False
        manifest["limitations"] = [
            "Whole-Watch battery readings are coarse; equal readings do not imply zero energy use.",
            "Two runs per condition are a descriptive comparison.",
            "Screenshot capture and UI-test supervision contribute matched overhead.",
            "Native reduced-luminance state is not independently sampled.",
            "App-list and app rendering and system haptics differ.",
            "Automated input contains settling gaps; manual Crown pace is not instrumented."]
    except BaseException as error:
        manifest.update(status="stopped", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        # The initial physical probe established that the user's launcher used Grid View.
        # Attempt both restorations even if one raises, and never report a
        # successful comparison when required cleanup failed.
        cleanup_errors = []
        try:
            code, _ = execute(session, manifest, None, "restore-grid", "testRestoreGrid")
            manifest["gridRestoreTestExitCode"] = code
            if code != 0:
                raise ValueError(f"Grid restoration failed with exit code {code}.")
        except BaseException as error:
            cleanup_errors.append(error)
            manifest["gridRestoreError"] = f"{type(error).__name__}: {error}"
        try:
            comparison.restore_normal(session, manifest)
        except BaseException as error:
            cleanup_errors.append(error)
            manifest["normalRestoreError"] = f"{type(error).__name__}: {error}"
        if cleanup_errors:
            manifest.update(status="restoration-failed", restorationErrors=[f"{type(error).__name__}: {error}" for error in cleanup_errors])
        save(session / "system-comparison.json", manifest)
        if cleanup_errors:
            if any(not isinstance(error, Exception) for error in cleanup_errors):
                raise next(error for error in cleanup_errors if not isinstance(error, Exception))
            raise ValueError("Required restoration failed; see system-comparison.json.") from cleanup_errors[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare")
    p.add_argument("--session", type=Path, required=True)
    p.add_argument("--device", required=True)
    p.add_argument("--developer-dir", required=True)
    p.add_argument("--restore-normal", type=Path, required=True)
    p.set_defaults(function=prepare)
    p = commands.add_parser("run")
    p.add_argument("--session", type=Path, required=True)
    p.add_argument("--mode", choices=["manual", "automated"], required=True)
    p.add_argument("--seconds", type=float, default=600)
    p.add_argument("--delta", type=float, default=.5, help="Rotations in each alternating Crown command")
    p.add_argument("--velocity", type=float, default=.5, help="Requested Crown rotations per second")
    p.add_argument("--period", type=float, default=8, help="Seconds allocated to each Crown command, including settling")
    p.set_defaults(function=run)
    args = parser.parse_args()
    if args.command == "run" and (not math.isfinite(args.seconds) or not 16 <= args.seconds <= 1800):
        parser.error("Use 16–1800 seconds.")
    if args.command == "run" and (any(not math.isfinite(value) or value <= 0
                                     for value in (args.delta, args.velocity, args.period)) or
                                  args.delta / args.velocity >= args.period or
                                  args.seconds / args.period < 2):
        parser.error("Use positive finite Crown parameters, leave time for command settling, and include at least two commands.")
    args.function(args)


if __name__ == "__main__":
    main()
