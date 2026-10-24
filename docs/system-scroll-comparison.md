# Native app-list battery comparison

This comparison measures whole-Watch reported charge during native app-list scrolling and Endless Crown with Clicks. Both conditions use `WKInterfaceDevice` battery monitoring in the UI-test runner. The recorder continues to run while the app is in the background. The measured app is an ordinary signed Release build: `ENERGY_TESTING` and its in-app logging are disabled. Production haptic and scrolling code is copied unchanged into an isolated build directory.

The first physical capability probe used an Apple Watch Ultra 2 on watchOS 27.2. Screenshots confirmed native alphabetical-list movement. The Watch used Grid View beforehand. This Watch's left-Crown configuration required rotating tap coordinates; the failed uncorrected tap opened Settings. Failed probes are excluded.

The successful cadence probe requested half a Crown rotation at 0.5 rotations per second, nominally one second of input. Each command took approximately 6.2 seconds in both screens. The app's separate timestamp report recorded 27 requested Clicks across four gestures, with gaps of 5.23, 5.56, and 5.24 seconds between bursts. These are app requests, not measured motor pulses. This automated profile is not uninterrupted physical scrolling.

Choose an input mode before starting a full comparison:

- `manual`: the user continuously rotates the physical Crown at a similar pace in both conditions, reversing before the list's endpoints. The recorder handles timing, battery readings, foreground/thermal/charging checks, and screenshots. Its ready message precedes a 30-second warm-up; begin scrolling at that message and continue through the measured window. Manual pace is not instrumented.
- `automated`: XCTest sends the same alternating Crown commands in both conditions, half a rotation at 0.5 rotations/second every eight seconds. A 10-minute run has 75 commands, nominally 75 seconds of requested Crown rotation. Command settling and scheduled pauses occupy the rest of the window. Interpret this as a matched paced workload, not continuous-use battery drain.

First pin the accepted normal restore product with `energy-compare.py --record-normal` as described in [restoration recovery](energy-tests.md). Then prepare an isolated signed ordinary Release app and runner:

```sh
python3 CrownSpin/scripts/system-scroll-compare.py prepare \
  --session energy-test-results/system-scroll-compare/NEW-SESSION \
  --device WATCH-UDID \
  --developer-dir /Applications/Xcode-27.1-beta.app/Contents/Developer \
  --restore-normal PATH-TO-ACCEPTED-NORMAL-BUILD.json
```

After the Watch is ready and the input mode has been chosen:

```sh
python3 CrownSpin/scripts/system-scroll-compare.py run \
  --session energy-test-results/system-scroll-compare/NEW-SESSION \
  --mode manual \
  --seconds 600
```

The schedule is app list, app, app, app list, with 60-second gaps between accepted runs. Both conditions capture battery at approximately 30-second intervals and screenshots approximately every minute. Long commands are sampled after each command to avoid crossing a sampling boundary without a reading. The Watch must stay unlocked on the wrist, off its charger, and nominal in thermal state. An invalid run stops the comparison. Do not touch the Watch in automated mode. The runner selects fixed Clicks through the ordinary app's single-tap effect cycle before either condition. It verifies the Clicks label and absence of the Random dice icon.

New `hittable-list-row-or-main-screen-v3` sessions verify Clicks before warm-up,
then use the ordinary Numbers scroll-view marker during measurement. The effect
label normally fades while scrolling, so it cannot serve as a continuous-input
visibility check. Keep the selected effect unchanged and inspect screenshots;
this guard checks main-screen presence, not motor output. Existing sessions
retain their recorded earlier validation policy. The v3 guard still needs a
fresh physical manual-scrolling acceptance run before using it for measurements.

The initial Ultra 2 protocol restores Grid View and the previously accepted normal app at the end, including after a failed run. Before reusing it on another Watch or with another launcher layout, repeat the capability probe and adapt the restoration policy to that device's original setting. Inspect the native screenshots before accepting a comparison: foreground state alone does not prove the app list remained visible, and native reduced-luminance state is not independently recorded.

Keep runs equal in duration. If percentage changes are too coarse, extend both conditions equally and reverse the order again. Two runs per condition are descriptive. Differences include display content, rendering, animations, system haptics, and app-requested haptics; this is not a direct measurement of haptic motor energy or an optimization saving.

The initial physical capability and short cadence evidence are saved under `energy-test-results/system-scroll-compare/8dd63745-3352-4020-8a2f-b63481885046/`. The completed longer-phase comparison is saved in the October 3 session below.

## Longer scrolling phases

`run` also accepts `--delta`, `--velocity`, and `--period`. Probe a candidate on both screens before using these arguments. The period includes the requested rotation and XCTest settling. Reports distinguish nominal requested rotation seconds from total Crown-call time; neither is independently measured motor activity or native moving time.

The October 3 longer-rotation calibration is under `energy-test-results/system-scroll-phases/e2e29841-8c06-41a8-8479-f523e3274176/`. Requested 1-, 4-, 10-, and 20-second commands took roughly 6.2, 9.2, 15.2, and 25.2 seconds. App diagnostic timestamps confirm sustained requests within the faster bursts and reversal gaps. The 0.1-rotation/second app candidate produced no callbacks and must not be counted as continuous active input.

Screenshot review excluded the initial native range probe: resetting with a large positive rotation returned to the Favorites screen. Some larger commands entered the alphabetical list and the longest reached its endpoint. The corrected protocol explicitly reopens All Apps after resets, leaves a margin above the measured reversal, and checks wide native Icon rows at sampling checkpoints. Carousel foreground state alone cannot distinguish Favorites from the alphabetical list. These row-shape checks are specific to the physically probed Ultra 2/watchOS layout; inspect screenshots before accepting results on another setup.

Use calibration, then two-minute validation on each screen, then the equal-duration app-list/app/app/app-list comparison. Save invalid attempts separately. Keep the runner alive within each measured window. Record remaining pauses and label the result as a phased workload if those pauses remain; do not claim uninterrupted fast scrolling.

The October 3 retry excluded a larger four-rotation candidate after it returned to Favorites. A smaller two-rotation candidate passed the original row-existence checks, but screenshots showed a Stand goal notification covering the list. That run is also excluded. The updated screen check requires a hittable visible row or Clicks label and rejects Carousel alerts and Dismiss controls. Screenshot review remains required. Temporarily enable Do Not Disturb and dismiss existing notifications before a comparison; notifications from system features can still require exclusion even with Focus enabled.

After alert dismissal and Do Not Disturb, both short validations passed. The final profile used two rotations at 0.25 rotations/second every 20 seconds: 30 commands and nominally 240 seconds of requested rotation in each 600-second trial. All four trials passed, including screenshot review: native list 40% to 35%, Clicks 35% to 30%, Clicks 30% to 25%, native list 25% to 20%. The runner recorded 32 health samples and 11 screenshots per trial. Grid View and the accepted normal app were restored successfully. Detailed results are in that session's `results.md` and `battery-comparison-summary.json`.

Every trial showed a five-percentage-point reported decrease. This is a descriptive baseline for the matched phased workload, with no resolved difference between conditions. Coarse readings, two repetitions, automation overhead, and different rendering/haptics prevent treating it as equal energy consumption, isolated haptic cost, continuous fast-use drain, or an original-versus-optimized battery saving.

Preparation records the app identity and a hash of the prepared product set, including its runner. Each execution verifies those products before device work; rebuild or missing identity records require fresh preparation. Grid restoration must expose the List View switch after selecting Grid View, rather than accepting the tap alone. At the deadline, the runner takes its final battery endpoint before any due periodic screenshot or accessibility check. Battery elapsed time comes from that endpoint. These UI assumptions still require the fresh physical acceptance described above.

Preparation uses the [internal compiler cache](energy-tests.md#internal-compiler-cache), with separate retained app/runner generations. Add `--fresh-build` for a new compiler workspace. Session paths, trial mappings, copied source, logs and reports remain separate from disposable DerivedData. Existing session artifacts are not migrated or deleted.
