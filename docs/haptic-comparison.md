# Fast Crown haptic comparison

New preparations now default to `before,overhead-only`. `before` retains original statistics observation, both original timer-allocation paths, and immediate per-event preference updates through diagnostic flags. `overhead-only` matches the normal Release candidate: original observation and haptic triggering, reused scrolling/menu timers, and batched preferences. `after` and `stats-only` retain narrowed observation for investigation only. Existing frozen sessions and their recorded mappings are unchanged; their results do not validate the newly added menu/persistence changes.

This diagnostic comparison investigates a reported reduction in felt haptics after the first optimization pass. The effect for the initial pair is **Clicks**, as requested. It compares the original statistics observation/timer behavior with both optimizations, using the same recorder and a physical Apple Watch Ultra 2. It is separate from the battery baseline.

## Physical procedure

1. Install and activate the first masked version. The Watch shows **Start Trial 1**.
2. Tap Start, wait for **Scroll fast**, then turn the Crown continuously in one direction at the usual fast speed for 30 seconds. Keep the Watch active and use only the Crown during capture.
3. Stop when **Saved · Repeat** appears. If **Interrupted · Retry** appears, dismiss any interruption and retry; flagged captures remain preserved.
4. Record how dense/distinct the haptics felt before collecting the report and installing Trial 2.
5. Repeat the same procedure and motion for Trial 2, then record whether they felt the same or which felt less frequent. Reveal the implementation mapping only after both observations are recorded.

Starting requires an active, raised-wrist display, an unplugged Watch with a valid battery reading, at least 20% charge, and a thermal state below serious. If a start is refused, charge to at least 25% when needed, unplug, and retry with the app active. Comparison builds from the first two sessions hide the controller's refusal message and can leave the Start button unchanged. The source now displays that message while idle; the existing signed comparison builds are retained so a pair does not change builds midway through capture.

The participant operates the real Crown; synthetic replay and XCTest do not drive these captures. Neutral labels and randomized order reduce expectation effects. The mapping remains in a local manifest for reproducibility; this is not a fully blinded laboratory experiment. Physical capture and subjective feedback are required before any conclusion.

## Recorded evidence

- The controller buffers a callback timestamp, request timestamp, old/new selection IDs, effect, and whether a haptic was requested for each handled scroll change. The callback timestamp is taken after the existing scroll-change guards, before normal per-scroll work. The request timestamp is taken in the diagnostic guard just before the existing `WKInterfaceDevice.play` call; it approximates API request timing, not motor activation.
- Timing buffers are not published and are written to a report only after the run. There is no per-request file logging or on-screen counter update. Both variants use identical instrumentation; instrumentation can still add some work to the measured path.
- Existing phase, luminance, charge, thermal, settings, and completion checks retain flagged/interrupted captures. Request records must match the event counters and contain ordered, finite timestamps for the same fixed effect. The start controls and setup changes are diagnostic-only.
- Analysis reports request counts, interval percentiles, the fraction of intervals below 100 ms, callback-to-request latency, and observed selection jumps. The first two seconds are excluded from interval statistics; all raw records are retained.

Apple documents that overlapping haptic requests interrupt the active effect and impose at least a 100 ms delay before new feedback. Closely spaced requests may therefore warrant investigation, but this logger cannot determine whether requests actually overlap or how many pulses the wearer feels. See [Apple's `play(_:)` documentation](https://developer.apple.com/documentation/watchkit/wkinterfacedevice/play(_:)).

Manual speed is not controlled. Selection-ID deltas are observations of SwiftUI scroll position, not raw Crown rotation or guaranteed individual row crossings. Differences in request counts or timing from one pair do not establish a regression by themselves; use the subjective comparison and recorded input differences together.

## Local commands

Use the installed Xcode that supports the physical Watch. Builds use signed Release configuration and the existing bundle ID; installing another trial preserves app data. The source fingerprint plus compile flags uniquely identify each variant.

```sh
python3 CrownSpin/scripts/haptic-comparison.py prepare \
  --device 00008310-000D7BC03C08A01E \
  --developer-dir /Applications/Xcode-27.1-beta.app/Contents/Developer

python3 CrownSpin/scripts/haptic-comparison.py install \
  --session SESSION_DIRECTORY --trial 1 --pattern clicks

# Only after the participant finishes the on-Watch run:
python3 CrownSpin/scripts/haptic-comparison.py collect \
  --session SESSION_DIRECTORY --trial 1 --notes 'Participant observation'

# Repeat install/collect for trial 2, using clicks again.
python3 CrownSpin/scripts/haptic-comparison.py summarize \
  --session SESSION_DIRECTORY --reveal
```

Reports are selected by trial label, effective build fingerprint, and capture time after the recorded launch. The newest matching capture is validated; a flagged newest capture cannot silently be replaced with an older successful one. All fetched reports remain available.

If a repeatable difference appears, prepare comparisons using `--variants before,stats-only` and `--variants before,timer-only` to isolate the changes. After the statistics comparison, a normal Release again uses the original `@StateObject` statistics observation and retains candidate timer reuse. Narrow statistics observation remains available only in diagnostic variants. A normal Release excludes the recorder and comparison controls.

## Preparation status

Both signed variants compiled, and 16 Swift report checks, 20 existing Python validator checks, and 3 new timing-analysis checks passed. The initial new Swift test used an invalid ten-minute sample gap; its corrected 30-second fixture passed. No physical comparison has been completed merely by these build/test results.

The initial session is `energy-test-results/haptic-comparison/abdf7e10-888b-405e-8689-1686f065ca2a/`. On October 3, the participant confirmed both trials were done. Both physical captures were retrieved and passed validation, and the recorded Watch, effect, workload, and settings matched. Before revealing the mapping, the participant reported: "I feel trail 2 is more denser and natural. Trail 1 feels sparse and has gap". This observation is stored verbatim in `comparison.json`.

The revealed mapping is **Trial 1: both optimizations (`after`)**, **Trial 2: original behavior (`before`)**. The preference supports investigating a perceived regression; one manually paced pair does not prove causation. `revealed-summary.json` records the mapping, timing metrics, and participant feedback.

| Measurement | Trial 1 | Trial 2 |
| --- | ---: | ---: |
| Capture duration | 30.002 s | 30.031 s |
| Handled scroll changes / haptic requests | 513 / 513 | 536 / 536 |
| Median request interval, after first 2 s | 37.794 ms | 40.247 ms |
| Median callback-to-request time | 1.008 ms | 1.027 ms |
| Request intervals below 100 ms | 93.42% | 93.00% |

Every handled scroll change requested a haptic in both captures. These records show API request timing; they do not measure delivered or felt pulses. Manual input differed between runs, and one pair cannot establish equivalence or attribute a perceived difference to either optimization. No battery conclusion is drawn from these trials.

The descriptive request-stream check (`request-stream-details.json`) found 4 versus 6 steady request gaps above 200 ms; maximum gaps were 313 versus 383 ms for optimized versus original behavior. The optimized capture does not show an excess of long gaps in this request stream, despite the reported sparse feel. This does not invalidate the observation: request timing and motor output are different measurements. Rapid-request interaction with the haptic engine is a hypothesis, not an established explanation.

A new masked pair was prepared with `--variants before,stats-only`, keeping the original timer in both variants. This isolates the statistics observation change before deciding whether either optimization preserves the experience. Both signed Release builds completed with the expected source fingerprints. Its session is `energy-test-results/haptic-comparison/b0537b80-bac0-463e-a490-36699be95eb7/`, with neutral labels **Stats Trial 1** and **Stats Trial 2**. Both versions were installed and activated with Clicks and a 30-second manual capture request; no synthetic replay or XCTest driver was launched.

The participant confirmed Stats Trial 1 was done. Its capture passed validation: 568 handled scroll changes and 568 haptic requests over 30.035 seconds. Before reveal, the participant described its feel as "Somewhere in between" when asked whether it felt dense and natural, sparse with gaps, or between those descriptions. At that stage, Stats Trial 2 was installed and awaiting physical capture and comparison feedback, and the mapping remained masked.

The participant then reported that tapping Start Stats Trial 2 left the button unchanged. A fresh report retrieval found no matching Stats Trial 2 capture. Stats Trial 1's latest endpoint was 15% charge, below the harness's 20% start guard. The blocked attempt did not persist its exact refusal reason, so low charge is the likely blocker rather than a directly logged start error. The hidden refusal-message path was verified in source and corrected for future builds. Unsigned diagnostic and normal Release compile checks passed, with the new error-display marker present only in the diagnostic binary; neither compile-check build was installed. The participant was asked to charge to at least 25%, unplug, and retry the installed Stats Trial 2. Device status, retrieved reports, diagnosis, and compile-check logs are under the session's `trial-2-start-debug/` directory. These timing captures are excluded from battery analysis.

The participant later reported 31% charge and confirmed the Watch was unplugged, unlocked, and awake, but Start still appeared unchanged. That contradicts low charge as a sufficient explanation for the continuing failure. A separate signed diagnostic with the same compile-time behavior as frozen Stats Trial 2 was installed. It displays refusal messages and records start snapshots only when explicitly launched with `CROWN_START_DIAGNOSTICS=1`; comparison launches strip that troubleshooting flag. Its launch enables battery monitoring earlier, and its automatic start attempt succeeded with reported charge 30%, unplugged power, active phase, unreduced luminance, and nominal temperature. That automatic 15-second check had no Crown driver and is flagged/excluded.

The participant also completed a valid manual **Check** capture in the diagnostic build: 15.022 seconds, 244 handled scroll changes, and 244 haptic requests. This establishes that a manual tap started the diagnostic capture after relaunch. It is excluded from the statistics comparison because its duration/build and troubleshooting setup differ. It does not identify the exact original failure: the process, battery-monitoring preparation, and visible diagnostic UI changed together. Stale battery readings and the original button path remain hypotheses. The original matched Stats Trial 2 build was restored and activated for its 30-second Clicks comparison, with its expected fingerprint and no troubleshooting or automatic-start launch flags. Earlier reports and launch evidence remain preserved. The current normal Release compile passed and excludes the troubleshooting/error-display markers.

The participant then completed Stats Trial 2 and reported before reveal: "Done. It feels dense and natural. But when i scroll really fast, it feel not so dense." Its 30.010-second capture passed validation and matched the first trial's recorded Watch, effect, workload, and settings. The mapping was revealed only afterward: **Stats Trial 1 was `stats-only`**, **Stats Trial 2 was `before`**; both used the original timer.

| Measurement | Stats Trial 1: narrower observation | Stats Trial 2: original observation |
| --- | ---: | ---: |
| Participant description | Somewhere in between | Dense and natural; thinner when really fast |
| Duration | 30.035 s | 30.010 s |
| Handled changes / haptic requests | 568 / 568 | 516 / 516 |
| Average request rate | 18.91/s | 17.19/s |
| Median steady request interval | 38.273 ms | 42.519 ms |
| Steady request intervals below 100 ms | 94.19% | 89.98% |
| Steady request gaps above 200 ms | 12 | 7 |

One haptic was requested for every handled change in both. The narrower-observation capture had more requests, despite the less favorable subjective description. The data support retaining original observation as a conservative experience decision; they do not prove the mechanism or a causal regression. Manual pace differed, initial charge was 20% versus 30%, and recharging/relaunch separated the captures. The very-fast subjective portion was not timestamped, so it cannot be correlated with a specific interval segment. Apple's documented interruption behavior is a plausible explanation for thinner feedback at high request rates, including in the original build. Intervals below 100 ms do not prove the engine was engaged or requests overlapped. No motor output or energy saving was measured. See `revealed-summary.json` and `interpretation.json` in the statistics session.

The normal source restores original statistics observation; its Release compile passed and diagnostic markers are absent from its binary. The next masked pair, `--variants before,timer-only`, retains original observation in both variants and differs only in timer reuse. Both signed Release builds passed with expected source fingerprints. Its session is `energy-test-results/haptic-comparison/feecaef3-36c4-4982-8b2b-112996368728/`, with neutral labels **Timer Trial 1** and **Timer Trial 2**. Both trials were installed and activated with Clicks, a 30-second manual request, and no troubleshooting or automatic-start flags.

The participant completed Timer Trial 1 and reported before reveal: "Done. It feels sparse not natural". Its capture passed validation, with 527 handled scroll changes and 527 haptic requests over 30.033 seconds. Timer Trial 2 then completed and the participant reported, again before reveal: "Done. It feels better but still not so dense". Its capture passed validation and matched the first trial's recorded conditions.

The revealed mapping is **Timer Trial 1: original timer (`before`)**, **Timer Trial 2: reused timer (`timer-only`)**. Both retain original statistics observation.

| Measurement | Original timer | Reused timer |
| --- | ---: | ---: |
| Participant description | Sparse; not natural | Better; still not so dense |
| Duration | 30.033 s | 30.004 s |
| Handled changes / haptic requests | 527 / 527 | 529 / 529 |
| Average request rate | 17.55/s | 17.63/s |
| Median steady request interval | 41.983 ms | 40.789 ms |
| Steady request intervals below 100 ms | 90.52% | 91.52% |
| Steady request gaps above 200 ms | 9 | 8 |
| Reported charge at both endpoints | 25% | 25% |

The timer pair does not show lost API requests or a reduced median API request rate with timer reuse, and the participant preferred the reused-timer variant. The original timer also felt sparse in this round. Across all three pairs, the second trial received more favorable feedback even though the timer pair assigned the original version to the first trial. Order, practice, manual input, and haptic-engine/system variability remain possible contributors; no consistent code-caused sparse-feel regression or motor-delivery mechanism is established. A single pair cannot establish equivalence across effects and speeds. Request timings are not motor output, and these captures do not measure battery savings.

The retained change for normal use is timer reuse with the same 1.5-second idle deadline, plus original statistics observation. No request throttle or haptic-pattern change was introduced. A signed normal Release build passed, with diagnostic markers absent, and was installed and activated on the Ultra 2 without comparison or automation launch variables. Everyday acceptance of that normal build remains separate from the instrumented comparison. Results and limitations are saved in the timer session's `revealed-summary.json` and `interpretation.json`; normal-build provenance and launch evidence are in `normal-timer-only-build.json` and `normal-timer-only-launch.json`.

The later menu/persistence optimization pass was installed as a normal Release on the Ultra 2. The user reported "I tried it, and it feels normal," accepting its feel in an unmasked manual check. This feedback applies to the later build (`65a1b587…`), not the earlier frozen timer-only comparison; effects/speeds/duration were unspecified. It does not measure battery savings. See the subsequent-overhead section of [the energy audit](energy-audit.md).
