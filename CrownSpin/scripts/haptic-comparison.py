#!/usr/bin/env python3
"""Prepare masked builds and collect a user-operated fast-Crown comparison. Local only."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import plistlib
import random
import shutil
import subprocess
import uuid

spec = importlib.util.spec_from_file_location("energy", Path(__file__).with_name("energy-tests.py"))
energy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(energy)

VARIANTS = {
    "before": ["HAPTIC_LEGACY_STATS", "HAPTIC_LEGACY_TIMER",
               "HAPTIC_LEGACY_MENU_TIMER", "HAPTIC_LEGACY_PERSISTENCE"],
    "after": [],
    "stats-only": ["HAPTIC_LEGACY_TIMER", "HAPTIC_LEGACY_MENU_TIMER", "HAPTIC_LEGACY_PERSISTENCE"],
    "timer-only": ["HAPTIC_LEGACY_STATS", "HAPTIC_LEGACY_MENU_TIMER", "HAPTIC_LEGACY_PERSISTENCE"],
    # Same statistics observation and overhead changes as the normal Release app.
    "overhead-only": ["HAPTIC_LEGACY_STATS"],
}
PATTERNS = ["clicks", "ping", "soft", "drift", "pulse", "wave", "doubleTap", "gallop",
            "heartbeat", "staccato", "waltz", "buzz", "heavy", "thud"]


def save(session, manifest):
    path = session / "comparison.json"
    path.write_text(json.dumps(manifest, indent=2))
    path.chmod(0o600)


def environment(developer_dir):
    result = {key: value for key, value in os.environ.items()
              if not key.startswith("DEVICECTL_CHILD_") and
              key not in {"CROWN_ENERGY_REQUEST", "CROWN_HAPTIC_COMPARISON", "CROWN_START_DIAGNOSTICS"}}
    result["DEVELOPER_DIR"] = str(developer_dir)
    return result


def prepare(args):
    energy.build_cache.validate_output(args.output)
    if args.rebuild_session:
        energy.build_cache.validate_output(args.rebuild_session)
    order = args.variants.split(",")
    if len(order) != 2 or len(set(order)) != 2 or any(v not in VARIANTS for v in order):
        raise ValueError("Specify two distinct comparison variants.")
    if args.rebuild_session:
        session = args.rebuild_session.resolve()
        previous = json.loads((session / "comparison.json").read_text())
        if any("launchedAt" in trial for trial in previous["trials"]):
            raise ValueError("Cannot replace builds after a physical trial has been launched.")
        if set(order) != {t["variant"] for t in previous["trials"]}:
            raise ValueError("Rebuilding must retain the same variants.")
        order = [t["variant"] for t in previous["trials"]]
        shutil.copyfile(session / "comparison.json", session / f"comparison-prior-{uuid.uuid4()}.json")
    else:
        session = args.output.resolve() / str(uuid.uuid4())
        session.mkdir(parents=True)
        random.SystemRandom().shuffle(order)
    source = energy.source_fingerprint()
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=energy.ROOT, text=True).strip()
    manifest = {"schemaVersion": 1, "sessionID": session.name, "status": "building",
                "device": args.device, "developerDir": str(args.developer_dir.resolve()),
                "sourceFingerprint": source, "durationSeconds": args.seconds,
                "trials": [{"label": f"Trial {i + 1}", "variant": v} for i, v in enumerate(order)],
                "purpose": "Physical Crown haptic feel and request timing; not battery measurement"}
    save(session, manifest)
    print(f"Comparison session: {session}", flush=True)
    for index, trial in enumerate(manifest["trials"], 1):
        if energy.source_fingerprint() != source:
            raise ValueError("Sources changed during preparation. Start a fresh comparison.")
        build = session / f"trial-{index}-build"
        flags = ["ENERGY_TESTING"] + VARIANTS[trial["variant"]]
        fingerprint = hashlib.sha256((source + "\0" + " ".join(flags)).encode()).hexdigest()
        command = ["xcodebuild", "-project", str(energy.PROJECT), "-scheme", "CrownSpin Watch App",
                   "-configuration", "Release", "-destination", f"id={args.device}",
                   "-derivedDataPath", str(build),
                   "SWIFT_ACTIVE_COMPILATION_CONDITIONS=$(inherited) " + " ".join(flags),
                   f"ENERGY_SOURCE_REVISION={revision}", f"ENERGY_SOURCE_FINGERPRINT={fingerprint}", "build"]
        print(f"Building {trial['label']}…", flush=True)
        log_path = session / f"trial-{index}-build.log"
        if log_path.exists():
            shutil.copyfile(log_path, session / f"trial-{index}-build-prior-{uuid.uuid4()}.log")
        with log_path.open("w") as log:
            build = energy.build_cache.build_products(command, output=session / "products", env=environment(args.developer_dir),
                log=log, fresh=getattr(args, "fresh_build", False), profile="app")
        app = build / "Build/Products/Release-watchos/CrownSpin Watch App.app"
        info = plistlib.loads((app / "Info.plist").read_bytes())
        if info.get("EnergySourceFingerprint") != fingerprint:
            raise ValueError("Built app has the wrong comparison fingerprint.")
        trial.update(app=str(app), fingerprint=fingerprint, status="built")
        save(session, manifest)
    manifest["status"] = "ready"
    save(session, manifest)
    (args.output.resolve() / "latest-session.txt").write_text(str(session) + "\n")
    print("Both signed builds are ready. Version mapping stays hidden until results are collected.", flush=True)


def install(args):
    session = args.session.resolve()
    manifest = json.loads((session / "comparison.json").read_text())
    trial = manifest["trials"][args.trial - 1]
    env = environment(Path(manifest["developerDir"]))
    request = {"trialLabel": trial["label"], "pattern": args.pattern,
               "durationSeconds": manifest["durationSeconds"]}
    launch_environment = {"CROWN_HAPTIC_COMPARISON":
                          base64.b64encode(json.dumps(request).encode()).decode()}
    print(f"Installing {trial['label']} ({args.pattern}, {manifest['durationSeconds']:g} seconds)…", flush=True)
    with (session / f"trial-{args.trial}-install.log").open("w") as log:
        subprocess.run(["xcrun", "devicectl", "device", "install", "app", "--device", manifest["device"],
                        trial["app"], "--timeout", "120"], env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    trial.update(pattern=args.pattern, launchedAt=datetime.now(timezone.utc).isoformat(), status="installed")
    save(session, manifest)
    launch = ["xcrun", "devicectl", "device", "process", "launch", "--device", manifest["device"],
              "--terminate-existing", "--activate", "--environment-variables", json.dumps(launch_environment),
              "--json-output", str(session / f"trial-{args.trial}-launch.json"), energy.BUNDLE_ID]
    with (session / f"trial-{args.trial}-launch.log").open("w") as log:
        subprocess.run(launch, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    print(f"Ready: tap Start {trial['label']} on the Watch; wait for Scroll fast, then use the Crown until Saved appears.")


def percentile(values, percent):
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * percent / 100
    low, high = math.floor(index), math.ceil(index)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def timing_metrics(report):
    issues = energy.validate(report)
    if issues:
        raise ValueError("Invalid physical run: " + " ".join(issues))
    if report["configuration"].get("captureHapticTiming") is not True:
        raise ValueError("Request timing was not enabled.")
    timings = report.get("hapticTimings")
    if not isinstance(timings, list) or not timings:
        raise ValueError("No haptic timing records.")
    endpoint = report["samples"][-1]
    if len(timings) != endpoint["scrollEvents"] or \
            sum(t.get("requestsHaptic") is True for t in timings) != endpoint["hapticRequests"]:
        raise ValueError("Timing records disagree with activity counters.")
    previous = -1
    for t in timings:
        callback, request = t.get("callbackElapsedSeconds"), t.get("requestElapsedSeconds")
        if not energy.number(callback) or not energy.number(request) or \
                not 0 <= callback <= request <= endpoint["elapsedSeconds"] or callback < previous or \
                t.get("pattern") != report["configuration"]["pattern"] or \
                not isinstance(t.get("requestsHaptic"), bool) or \
                not isinstance(t.get("newPosition"), int) or isinstance(t["newPosition"], bool) or \
                (t.get("oldPosition") is not None and
                 (not isinstance(t["oldPosition"], int) or isinstance(t["oldPosition"], bool))):
            raise ValueError("Invalid request timestamp, effect, or selection position.")
        previous = request
    # Retain all raw events, but exclude the first two seconds from timing statistics.
    steady = [t for t in timings if t["requestsHaptic"] and t["requestElapsedSeconds"] >= 2]
    intervals = [(b["requestElapsedSeconds"] - a["requestElapsedSeconds"]) * 1000
                 for a, b in zip(steady, steady[1:])]
    latency = [(t["requestElapsedSeconds"] - t["callbackElapsedSeconds"]) * 1000 for t in steady]
    deltas = [abs(t["newPosition"] - t["oldPosition"]) for t in steady if t["oldPosition"] is not None]
    return {"scrollEvents": endpoint["scrollEvents"], "hapticRequests": endpoint["hapticRequests"],
            "durationSeconds": endpoint["elapsedSeconds"], "steadyRequests": len(steady),
            "requestIntervalMs": {f"p{p}": percentile(intervals, p) for p in (10, 50, 90, 99)},
            "requestIntervalsUnder100msPercent": 100 * sum(v < 100 for v in intervals) / len(intervals) if intervals else None,
            "callbackToRequestMs": {f"p{p}": percentile(latency, p) for p in (50, 90, 99)},
            "selectionJumpsLargerThanOne": sum(delta > 1 for delta in deltas),
            "totalAbsoluteSelectionDelta": sum(deltas),
            "motorDeliveryMeasured": False}


def collect(args):
    session = args.session.resolve()
    manifest = json.loads((session / "comparison.json").read_text())
    trial = manifest["trials"][args.trial - 1]
    if "launchedAt" not in trial:
        raise ValueError("This trial has not been installed and launched.")
    destination = session / f"trial-{args.trial}-reports"
    destination.mkdir(exist_ok=True)
    with (session / f"trial-{args.trial}-fetch.log").open("w") as log:
        subprocess.run(["xcrun", "devicectl", "device", "copy", "from", "--device", manifest["device"],
                        "--domain-type", "appDataContainer", "--domain-identifier", energy.BUNDLE_ID,
                        "--source", "Documents/EnergyTests", "--destination", str(destination), "--timeout", "30"],
                       env=environment(Path(manifest["developerDir"])), stdout=log, stderr=subprocess.STDOUT, check=True)
    launched = datetime.fromisoformat(trial["launchedAt"])
    matches = []
    for path in destination.rglob("*.json"):
        r = json.loads(path.read_text())
        if r.get("metadata", {}).get("comparisonTrial") == trial["label"] and \
                r["metadata"].get("sourceFingerprint") == trial["fingerprint"] and \
                datetime.fromisoformat(r["startedAt"].replace("Z", "+00:00")) >= launched:
            matches.append((r["startedAt"], path, r))
    if not matches:
        raise ValueError("No matching capture yet. Complete the on-Watch trial before collecting.")
    _, path, report = max(matches, key=lambda item: item[0])
    metrics = timing_metrics(report)
    trial.update(status="collected", report=str(path), metrics=metrics, notes=args.notes)
    save(session, manifest)
    print(json.dumps({"trial": trial["label"], "metrics": metrics}, indent=2))


def summarize(args):
    manifest = json.loads((args.session / "comparison.json").read_text())
    if any(t.get("status") != "collected" for t in manifest["trials"]):
        raise ValueError("Collect both physical captures before comparing.")
    reports = [json.loads(Path(t["report"]).read_text()) for t in manifest["trials"]]
    if energy.comparison_key(reports[0]) != energy.comparison_key(reports[1]):
        raise ValueError("Watch, effect, workload, or recorded settings differ between trials.")
    result = {"trials": [{"trial": t["label"], **({"variant": t["variant"]} if args.reveal else {}),
                           "metrics": t["metrics"], "notes": t.get("notes", "")} for t in manifest["trials"]],
              "limitations": ["Manual Crown speed is not controlled; one pair is a diagnostic check, not causal proof.",
                              "Selection deltas are scroll-position observations, not physical Crown angles.",
                              "Request times and intervals do not measure motor output or felt pulse count.",
                              "This comparison is excluded from battery analyses."]}
    output = args.session / ("revealed-summary.json" if args.reveal else "masked-summary.json")
    output.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare")
    p.add_argument("--device", required=True)
    p.add_argument("--developer-dir", required=True, type=Path)
    p.add_argument("--seconds", type=float, choices=(15, 20, 30, 45, 60), default=30)
    p.add_argument("--variants", default="before,overhead-only")
    p.add_argument("--output", type=Path, default=Path("energy-test-results/haptic-comparison"))
    p.add_argument("--rebuild-session", type=Path, help="Refresh unlaunched builds while retaining their masked order")
    p.add_argument("--fresh-build", action="store_true", help="Use new internal compiler workspaces")
    p.set_defaults(function=prepare)
    p = commands.add_parser("install")
    p.add_argument("--session", required=True, type=Path)
    p.add_argument("--trial", required=True, type=int, choices=(1, 2))
    p.add_argument("--pattern", required=True, choices=PATTERNS)
    p.set_defaults(function=install)
    p = commands.add_parser("collect")
    p.add_argument("--session", required=True, type=Path)
    p.add_argument("--trial", required=True, type=int, choices=(1, 2))
    p.add_argument("--notes", default="")
    p.set_defaults(function=collect)
    p = commands.add_parser("summarize")
    p.add_argument("--session", required=True, type=Path)
    p.add_argument("--reveal", action="store_true")
    p.set_defaults(function=summarize)
    args = parser.parse_args()
    try:
        args.function(args)
        return 0
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"Error: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
