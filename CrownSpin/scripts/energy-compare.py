#!/usr/bin/env python3
"""Run a local, counterbalanced Watch energy pilot and restore the normal app."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import plistlib
import statistics
import subprocess
import sys
import time

spec = importlib.util.spec_from_file_location("energy", Path(__file__).with_name("energy-tests.py"))
energy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(energy)


def save(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def now():
    return datetime.now(timezone.utc).isoformat()


def verify_builds(manifest):
    if energy.source_fingerprint() != manifest["sourceFingerprint"]:
        raise ValueError("App sources changed after preparation; do not mix builds.")
    for variant, build in manifest["variants"].items():
        info = plistlib.loads((Path(build["build"]) / "Build/Products/Release-watchos/CrownSpin Watch App.app/Info.plist").read_bytes())
        if info.get("EnergySourceFingerprint") != build["fingerprint"] or \
                build["fingerprint"] != energy.build_fingerprint(variant):
            raise ValueError("Variant identity mismatch: " + variant)
        if not list((Path(build["build"]) / "Build/Products").glob("*.xctestrun")):
            raise ValueError("Missing automation runner: " + variant)


def report_identity_issues(report, manifest, variant, duration):
    expected = {"label": variant, "scenario": manifest["scenario"], "durationSeconds": duration,
                "stepsPerSecond": manifest["stepsPerSecond"], "pattern": manifest["pattern"],
                "conditions": manifest["conditions"]}
    if manifest.get("runtimeProfile"):
        expected["captureRuntimeProfile"] = True
    issues = []
    if any(report.get("configuration", {}).get(key) != value for key, value in expected.items()):
        issues.append("Captured configuration differs from the requested slot.")
    if report.get("metadata", {}).get("sourceFingerprint") != manifest["variants"][variant]["fingerprint"]:
        issues.append("Unexpected installed build fingerprint.")
    return issues


def run_attempt(session, manifest, variant, duration, phase, slot, retry=0):
    verify_builds(manifest)
    name = f"{phase}-{slot}-{variant}-attempt-{retry + 1}"
    output = session / name
    log_path = session / (name + ".log")
    entry = {"phase": phase, "slot": slot, "variant": variant, "attempt": retry + 1,
             "startedAt": now(), "status": "running", "log": str(log_path)}
    manifest["attempts"].append(entry)
    manifest["currentAttempt"] = name
    save(session / "comparison.json", manifest)
    command = [sys.executable, str(Path(__file__).with_name("energy-tests.py")), "automate",
               "--device", manifest["device"], "--variant", variant,
               "--developer-dir", manifest["developerDir"], "--seconds", str(duration),
               "--repetitions", "1", "--cases", manifest["scenario"],
               "--steps-per-second", str(manifest["stepsPerSecond"]),
               "--pattern", manifest["pattern"], "--label", variant,
               "--conditions", manifest["conditions"], "--cooldown", "0", "--skip-build",
               "--build-output", manifest["variants"][variant]["build"], "--output", str(output)]
    if manifest.get("runtimeProfile"):
        command.append("--runtime-profile")
    with log_path.open("w") as log:
        result = subprocess.run(command, cwd=energy.ROOT, env=energy.clean_device_environment(),
                                stdout=log, stderr=subprocess.STDOUT)
    entry.update(exitCode=result.returncode, endedAt=now(), status="failed")
    child_manifests = list(output.glob("*/session.json"))
    if len(child_manifests) == 1:
        child = json.loads(child_manifests[0].read_text())
        entry["automationSession"] = str(child_manifests[0])
        if len(child.get("runs", [])) == 1:
            run = child["runs"][0]
            entry.update(runID=run["runID"], issues=run.get("issues", []))
            if run.get("report"):
                report_path = Path(run["report"])
                report = json.loads(report_path.read_text())
                entry.update(report=str(report_path), reportStatus=report.get("status"))
                issues = energy.validate(report)
                issues.extend(report_identity_issues(report, manifest, variant, duration))
                entry["issues"] = issues
                if result.returncode == 0 and run.get("status") == "completed" and not issues:
                    entry["status"] = "completed"
                    rate, activity, drop = energy.metrics(report)
                    entry.update(dropPercentagePoints=drop, ratePercentagePointsPerHour=rate,
                                 handledChangesPerSecond=activity)
    save(session / "comparison.json", manifest)
    return entry


def summarize(manifest):
    if manifest.get("runtimeProfile"):
        raise ValueError("Runtime profiles belong in the runtime analyzer, not a battery summary.")
    accepted = [e for e in manifest["attempts"] if e["phase"] == "battery" and e["status"] == "completed"]
    if len(accepted) != len(manifest["schedule"]) or \
            [(e["slot"], e["variant"]) for e in accepted] != list(enumerate(manifest["schedule"], 1)):
        raise ValueError("The requested schedule did not complete exactly once per slot.")
    seen, rows, keys = set(), [], set()
    for entry in accepted:
        report = json.loads(Path(entry["report"]).read_text())
        config, metadata = report.get("configuration", {}), report.get("metadata", {})
        if config.get("captureRuntimeProfile") is True or config.get("captureHapticTiming") is True or \
                metadata.get("diagnosticPurpose") in {"runtime-profile-v1", "haptic-timing-only"}:
            raise ValueError("Profiling and haptic-timing captures are not battery observations.")
        if energy.validate(report) or report_identity_issues(report, manifest, entry["variant"],
                                                           manifest["durationSeconds"]) or report["runID"] in seen:
            raise ValueError("Invalid or duplicate accepted report.")
        seen.add(report["runID"])
        keys.add(energy.comparison_key(report))
        first, last = report["samples"][0], report["samples"][-1]
        rate, activity, drop = energy.metrics(report)
        rows.append({"slot": entry["slot"], "variant": entry["variant"], "runID": report["runID"],
                     "startReportedPercent": first["batteryLevel"] * 100,
                     "endReportedPercent": last["batteryLevel"] * 100,
                     "dropPercentagePoints": drop, "ratePercentagePointsPerHour": rate,
                     "seconds": last["elapsedSeconds"] - first["elapsedSeconds"],
                     "handledChanges": last["scrollEvents"], "hapticRequests": last["hapticRequests"],
                     "replaySteps": last["replaySteps"], "wakeTaps": report["metadata"].get("automationWakeTaps"),
                     "changesPerSecond": activity, "menuHidden": report["metadata"].get("menuHidden"),
                     "report": entry["report"]})
    groups = {v: [r for r in rows if r["variant"] == v] for v in ("original", "optimized")}
    return {"rows": rows, "recordedConditionsMatched": len(keys) == 1,
            "descriptiveMediansPercentagePointsPerHour": {
                v: statistics.median(r["ratePercentagePointsPerHour"] for r in rs) for v, rs in groups.items()
            } if len(keys) == 1 else None,
            "batterySavingEstablished": False,
            "limitations": ["Two runs per build: descriptive pilot, below the three-run analysis threshold.",
                            "Reported whole-Watch charge is coarse; equal endpoints do not mean equal power.",
                            "Starting charge and between-run installation/cooldown history can differ.",
                            "Timed 2 Hz app replay is not physical fast-Crown input or measured motor delivery.",
                            "UI-test supervision and neutral wake touches add matched workload overhead.",
                            "Existing app settings were preserved; a hidden menu does not exercise menu-timer savings.",
                            "Brightness and battery health were not independently measured."]}


def restore_normal(session, manifest):
    normal_path = Path(manifest["restoreNormalBuildManifest"])
    normal = json.loads(normal_path.read_text())
    app = Path(normal["app"])
    info = plistlib.loads((app / "Info.plist").read_bytes())
    if info.get("EnergySourceFingerprint") != manifest.get("restoreSourceFingerprint", manifest["sourceFingerprint"]) or \
            info.get("CFBundleIdentifier") != energy.BUNDLE_ID:
        raise ValueError("Normal restore app has the wrong identity.")
    env = energy.clean_device_environment()
    env["DEVELOPER_DIR"] = manifest["developerDir"]
    command = ["xcrun", "devicectl", "device", "install", "app", "--device", manifest["device"],
               str(app), "--timeout", "120", "--json-output", str(session / "restore-install.json")]
    with (session / "restore-install.log").open("w") as log:
        result = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT)
    manifest["normalRestore"] = {"installExitCode": result.returncode, "app": str(app), "attemptedAt": now()}
    save(session / "comparison.json", manifest)
    if result.returncode:
        raise ValueError("Normal app could not be restored; see restore-install.log.")
    with (session / "restore-launch.log").open("w") as log:
        launched = subprocess.run(["xcrun", "devicectl", "device", "process", "launch", "--device", manifest["device"],
            "--terminate-existing", "--activate", "--timeout", "20", "--json-output", str(session / "restore-launch.json"),
            energy.BUNDLE_ID], env=env, stdout=log, stderr=subprocess.STDOUT)
    manifest["normalRestore"].update(installed=True, launchExitCode=launched.returncode,
                                     automationLaunchVariablesAbsent=True)
    normal.update(installed=True, lastRestoredAt=now(), lastRestoreSession=str(session),
                  lastRestoreLaunchExit=launched.returncode)
    save(normal_path, normal)
    save(session / "comparison.json", manifest)
    if launched.returncode:
        raise ValueError("Normal app was installed but could not be opened; see restore-launch.log.")
    print("Normal optimized app restored and opened.", flush=True)


def run(args):
    session = args.session.resolve()
    manifest = json.loads((session / "comparison.json").read_text())
    if manifest["status"] != "ready" or manifest["attempts"]:
        raise ValueError("Run only a fresh prepared session.")
    if manifest.get("runtimeProfile"):
        raise ValueError("Use runtime-compare.py for the prepared runtime-profile session.")
    verify_builds(manifest)
    manifest.update(status="running", startedAt=now())
    save(session / "comparison.json", manifest)
    try:
        for slot, variant in enumerate(("original", "optimized"), 1):
            print(f"Excluded 15-second automation check: {variant}", flush=True)
            entry = run_attempt(session, manifest, variant, 15, "smoke", slot)
            if entry["status"] != "completed":
                raise ValueError("Automation check failed; no long battery trial started. See " + entry["log"])
        for slot, variant in enumerate(manifest["schedule"], 1):
            if manifest["cooldownSeconds"]:
                print(f"Cooldown: {manifest['cooldownSeconds']} seconds", flush=True)
                time.sleep(manifest["cooldownSeconds"])
            print(f"Battery run {slot}/{len(manifest['schedule'])}: {variant}, {manifest['durationSeconds']} seconds", flush=True)
            entry = run_attempt(session, manifest, variant, manifest["durationSeconds"], "battery", slot)
            # A notification/background interruption may clear on relaunch; preserve it and retry once.
            if entry["status"] != "completed" and entry.get("reportStatus") == "interrupted":
                print("Interrupted capture excluded; cooldown and one retry of the same slot.", flush=True)
                time.sleep(manifest["cooldownSeconds"])
                entry = run_attempt(session, manifest, variant, manifest["durationSeconds"], "battery", slot, retry=1)
            if entry["status"] != "completed":
                raise ValueError("Battery capture failed; comparison stopped. See " + entry["log"])
            print(f"Saved: {entry['dropPercentagePoints']:.2f} percentage points; matched report validated.", flush=True)
        save(session / "summary.json", summarize(manifest))
        manifest.update(status="completed", completedAt=now())
    except BaseException as error:
        manifest.update(status="stopped", error=str(error), stoppedAt=now())
        raise
    finally:
        save(session / "comparison.json", manifest)
        try:
            restore_normal(session, manifest)
        except Exception as error:
            manifest["restoreError"] = str(error)
            save(session / "comparison.json", manifest)
            print("RESTORE NEEDS ATTENTION: " + str(error), flush=True)
    if manifest.get("restoreError"):
        raise ValueError(manifest["restoreError"])
    print("Pilot complete. Charge observations are descriptive; no battery saving is established.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True, type=Path)
    args = parser.parse_args()
    try:
        run(args)
        return 0
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print("Error: " + str(error), flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
