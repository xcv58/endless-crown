#!/usr/bin/env python3
"""Compare diagnostic app CPU accounting; never infer electrical battery savings."""
import argparse
import importlib.util
import json
from pathlib import Path
import statistics
import time

spec = importlib.util.spec_from_file_location("comparison", Path(__file__).with_name("energy-compare.py"))
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)
VARIANTS = ("original", "timer-only", "persistence-only", "optimized")
SCHEDULE = [*VARIANTS, *reversed(VARIANTS)]


def summarize(manifest):
    accepted = [e for e in manifest["attempts"] if e["phase"] == "runtime" and e["status"] == "completed"]
    if [(e["slot"], e["variant"]) for e in accepted] != list(enumerate(SCHEDULE, 1)):
        raise ValueError("The balanced runtime schedule did not complete exactly once per slot.")
    rows, seen, keys = [], set(), set()
    for entry in accepted:
        report = json.loads(Path(entry["report"]).read_text())
        issues = comparison.energy.validate(report) + comparison.report_identity_issues(
            report, manifest, entry["variant"], manifest["durationSeconds"])
        if issues or report["runID"] in seen:
            raise ValueError("Invalid or duplicate runtime report: " + str(issues))
        seen.add(report["runID"])
        keys.add(comparison.energy.comparison_key(report))
        first, last = report["runtimeProfile"]["samples"][0], report["runtimeProfile"]["samples"][-1]
        cpu = last["userCPUSeconds"] - first["userCPUSeconds"] + last["systemCPUSeconds"] - first["systemCPUSeconds"]
        elapsed = last["elapsedSeconds"] - first["elapsedSeconds"]
        body = last["contentViewBodyUpdates"] - first["contentViewBodyUpdates"]
        activity = report["samples"][-1]
        rows.append({"slot": entry["slot"], "variant": entry["variant"], "runID": report["runID"],
                     "seconds": elapsed, "appCPUSeconds": cpu, "appCPUSecondsPerMinute": cpu * 60 / elapsed,
                     "bodyUpdates": body, "scrollChanges": activity["scrollEvents"],
                     "hapticRequests": activity["hapticRequests"], "wakeTaps": report["metadata"].get("automationWakeTaps"),
                     "work": last["work"], "report": entry["report"]})
    if len(keys) != 1:
        raise ValueError("Runtime workload conditions differ between slots.")
    groups = {v: [r for r in rows if r["variant"] == v] for v in VARIANTS}
    return {"rows": rows, "recordedConditionsMatched": True,
            "descriptiveCPUSecondsPerMinute": {
                v: {"median": statistics.median(r["appCPUSecondsPerMinute"] for r in rs),
                    "min": min(r["appCPUSecondsPerMinute"] for r in rs),
                    "max": max(r["appCPUSecondsPerMinute"] for r in rs)} for v, rs in groups.items()},
            "batterySavingEstablished": False,
            "limitations": ["App CPU time from getrusage excludes GPU, haptic motor, display and other Watch processes.",
                            "Two observations per variant are descriptive; they do not establish a reliable effect size.",
                            "Nested handler scopes measure wall time and must not be added together or treated as CPU time.",
                            "ContentView body counts exclude descendant view evaluations and rendering work.",
                            "Diagnostic counters and matched XCTest accessibility/wake activity add overhead.",
                            "The hidden-menu workload does not exercise visible-menu timer reuse.",
                            "Synthetic 2 Hz replay does not establish fast physical Crown or felt haptic equivalence."]}


def completed_prefix(manifest):
    accepted = [e for e in manifest["attempts"] if e["phase"] == "runtime" and e["status"] == "completed"]
    if [(e["slot"], e["variant"]) for e in accepted] != list(enumerate(SCHEDULE[:len(accepted)], 1)):
        raise ValueError("Accepted captures are not a unique schedule prefix.")
    seen = set()
    for entry in accepted:
        report = json.loads(Path(entry["report"]).read_text())
        if comparison.energy.validate(report) or comparison.report_identity_issues(
                report, manifest, entry["variant"], manifest["durationSeconds"]) or report["runID"] in seen:
            raise ValueError("Cannot resume an invalid accepted capture.")
        seen.add(report["runID"])
    return len(accepted)


def run(session, resume=False, restore_only=False):
    path = session / "comparison.json"
    manifest = json.loads(path.read_text())
    if restore_only:
        return comparison.retry_restore(session, manifest)
    if manifest["schedule"] != SCHEDULE:
        raise ValueError("Use the balanced runtime schedule.")
    if resume:
        if manifest["status"] != "stopped":
            raise ValueError("Resume only a stopped session.")
        completed = completed_prefix(manifest)
    else:
        if manifest["status"] != "ready" or manifest["attempts"]:
            raise ValueError("Use a fresh prepared balanced runtime session.")
        completed = 0
    if not manifest.get("runtimeProfile") or manifest.get("batteryBaseline") is not False:
        raise ValueError("Runtime captures must be explicitly separated from battery trials.")
    comparison.verify_builds(manifest)
    manifest.update(status="running", startedAt=comparison.now())
    comparison.save(path, manifest)
    try:
        for slot, variant in enumerate(SCHEDULE[completed:], completed + 1):
            if slot > 1:
                time.sleep(manifest["cooldownSeconds"])
            print(f"Runtime slot {slot}/{len(SCHEDULE)}: {variant}", flush=True)
            retry = max((e["attempt"] for e in manifest["attempts"] if e["phase"] == "runtime" and e["slot"] == slot), default=0)
            entry = comparison.run_attempt(session, manifest, variant, manifest["durationSeconds"], "runtime", slot, retry=retry)
            if entry["status"] != "completed" and entry.get("reportStatus") == "interrupted":
                print("Interrupted capture excluded; one retry of the same slot.", flush=True)
                time.sleep(manifest["cooldownSeconds"])
                entry = comparison.run_attempt(session, manifest, variant, manifest["durationSeconds"], "runtime", slot, retry=retry + 1)
            if entry["status"] != "completed":
                raise ValueError("Invalid runtime capture; stopped. See " + entry["log"])
            report = json.loads(Path(entry["report"]).read_text())
            last = report["runtimeProfile"]["samples"][-1]
            print(f"Validated {entry['runID']}; CPU counter {last['userCPUSeconds'] + last['systemCPUSeconds']:.4f}s", flush=True)
        comparison.save(session / "summary.json", summarize(manifest))
        manifest.update(status="completed", completedAt=comparison.now())
    except BaseException as error:
        manifest.update(status="stopped", error=str(error), stoppedAt=comparison.now())
        raise
    finally:
        comparison.restore_after_capture(session, manifest)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--resume", action="store_true", help="Validate accepted prefix and continue a stopped frozen session")
    parser.add_argument("--restore-only", action="store_true", help="Retry failed normal-app restoration without repeating captures")
    arguments = parser.parse_args()
    run(arguments.session.resolve(), resume=arguments.resume, restore_only=arguments.restore_only)
