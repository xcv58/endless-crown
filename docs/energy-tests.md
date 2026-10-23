# Physical Watch energy tests

This harness records a baseline before changing the app's energy behavior. It can time a run, sample the Watch battery every 30 seconds, drive a repeatable synthetic scrolling workload, and save a JSON report. The normal haptic, statistics, persistence, timer, and scrolling paths remain intact. The haptics-disabled control skips only the scroll-triggered `play` calls.

All harness code is behind `ENERGY_TESTING`. Normal builds have no test menu, logging, or replay timers. Two optional source-identification fields in the app's Info.plist are empty in normal builds.

New build and automation commands default to the existing `optimized` variant,
which retains the current ordinary app's statistics observation, timer reuse and
batched persistence. `--variant legacy-unqualified` explicitly selects the old
unqualified diagnostic experiment with narrowed statistics observation and its
source-only fingerprint. Existing named variants and their flag-based identities
remain unchanged; select the matching variant when consuming a frozen build.

New reports record the full display mode, distinguishing Ambient from Haptics
Only as well as normal display. Analysis separates historical reports without
that field; their old ambient Boolean cannot establish the full current mode.
Runtime-profile and haptic-timing-only captures are excluded from battery
comparisons and remain available to their dedicated analyzers.

## What can be automated

| Mode | Workload | Automation |
| --- | --- | --- |
| App idle | No Crown activity | Timing, sampling, report; automated mode uses matched neutral wake touches |
| Real Crown capture | You spin normally | Timing, sampling, request counts, report |
| Scroll replay + haptics | One programmatic selected-row step per tick | Workload, timing, sampling, report |
| Scroll replay, no haptics | Same replay and bookkeeping, motor calls omitted | Workload, timing, sampling, report |

Replay changes the same scroll-position binding used by the main screen. It is **synthetic**, not a simulation of all hardware Crown events, inertia, or physical haptic delivery. Its counters verify how many steps actually reached the app's existing handler. Counted haptics are API requests, not a measurement of motor pulses.

The harness does not add a workout or request extended runtime. WatchOS may deactivate an app even when it updates its own content. Active-use runs stop and save an interrupted report if the app loses the foreground or enters Always On. Manual replay needs you to keep the Watch active. Automated replay and automated idle use test-only neutral touches to maintain active interaction, as described below. Manual idle still follows normal Watch sleep behavior. Changing wake/display settings changes the test conditions and must be recorded and held constant for both builds.

The app-closed control still needs manual starting/ending battery readings: running a logger while the app is closed would change that control. A physical check of the Crown and haptic feel also remains manual.

## Automated Watch test runner

The `automate` command builds and installs a signed Release app and a separate watchOS UI-test runner. It launches each trial with its configuration already supplied, uses Apple's public [Crown rotation API](https://developer.apple.com/documentation/xcuiautomation/xcuidevice/rotatedigitalcrown%28delta%3Avelocity%3A%29) to inject Crown rotations, waits for the app to finish measuring, retrieves the exact run-ID report, validates it, cools down, and starts the next trial. No Watch-menu navigation or manual spinning is required once the device's UI automation service is working.

```sh
python3 CrownSpin/scripts/energy-tests.py automate \
  --device WATCH_UDID --allow-provisioning-updates
```

Defaults: three 5-minute trials each of `crown` and `crown-no-haptics`, with 60 seconds between trials. Case order rotates between repetitions. The haptics-disabled Crown control preserves the existing scrolling, statistics, persistence, and timers and skips only the scroll-triggered motor calls. `--cases crown,crown-no-haptics,idle` adds the app-idle control. `--pattern`, `--crown-delta`, `--crown-velocity`, and `--pause` define the workload; keep these identical when comparing builds.

For a fixed **two app scroll changes per second**, use timed replay instead of Crown commands. This schedules one selected-row change every 0.5 seconds through the existing handler. No manual calibration is needed. A 10-minute haptics-on/off pilot pair is:

```sh
python3 CrownSpin/scripts/energy-tests.py automate \
  --device WATCH_UDID --allow-provisioning-updates \
  --seconds 600 --repetitions 1 --cases replay,replay-no-haptics \
  --steps-per-second 2 --label baseline-replay-2hz \
  --output energy-test-results/replay-2hz-pilot
```

Automated replay and automated idle query status about every five seconds and tap an invisible diagnostic touch target near the screen center about every twenty seconds. The target is above the normal row gestures and acknowledges each touch without changing effects, requesting haptics, or moving the scroll position. XCTest checks that each touch arrived, and the report saves `automationWakeTaps`. All replay and automated-idle conditions use the same display procedure. The actual cadence is checked from the report: replay steps must be within 2% of the target (or two steps for short runs), and app scroll events must match replay steps within two events. One missing endpoint tick is allowed. A 10-minute run therefore targets approximately 1,200 changes; a haptics-on trial should have matching haptic requests and its control should have zero.

Replay reports use `app-scroll-replay-v1`; automated idle uses `app-idle-v1`. Both record wake/status-query policy. Automated idle rejects any scroll events, replay steps, or haptic requests and requires active, non-reduced-luminance samples at regular intervals. Manual idle continues to allow suspension, while flagging duration overruns. Analysis separates them from Crown-driven trials. The rate means app scroll changes, not physical Crown rotations per second. Use `--repetitions 3` for a repeated baseline after the pilot succeeds.

For an active-display idle versus scrolling control, use the same frozen build and wake policy:

```sh
python3 CrownSpin/scripts/energy-tests.py automate \
  --device WATCH_UDID \
  --developer-dir /Applications/Xcode-27.1-beta.app/Contents/Developer \
  --seconds 600 --repetitions 1 --cases idle,replay-no-haptics \
  --steps-per-second 2 --label baseline-idle-vs-scroll \
  --skip-build --build-output /private/tmp/CrownSpinEnergyActiveIdle \
  --output energy-test-results/idle-vs-scroll
```

Build that output directory with `build-automation` first. This compares an active app with zero input against the scrolling/bookkeeping workload with app haptic calls omitted. It is separate from an idle Watch or app-closed baseline. See [the code and runtime audit](energy-audit.md) for candidates to investigate without changing feedback.

Start with a short installation/automation check:

```sh
python3 CrownSpin/scripts/energy-tests.py automate \
  --device WATCH_UDID --allow-provisioning-updates \
  --seconds 30 --repetitions 1 --cases crown --cooldown 0 --label automation-smoke
```

Use `--skip-build` only with unchanged source inputs. It requires the successful app/runner/configuration product record from `build-automation`, checks its hash and the built app fingerprint before starting and checks the installed app fingerprint in each retrieved report. The session folder under `energy-test-results/automation` contains `session.json`, per-trial test configurations/logs/result bundles, and saved reports. A missing report, failed UI test, interrupted measurement, charging, or serious thermal state stops the batch. Automated starts require at least 20% charge and a cool Watch. File transfers happen after measurement. The test configuration disables Xcode's Main Thread Checker, performance antipattern checker, code coverage, and verbose failure diagnostics, and requests screenshots instead of video recording; XCTest still runs on the Watch and performs UI queries.

Use `--developer-dir /Applications/Xcode-27.1-beta.app/Contents/Developer` to select that installed Xcode for one command without changing the Mac's global selection. Keep the same Xcode and SDK when comparing builds; the reports record them and analysis separates different toolchains.

These are **controlled UI-automation trials**, not identical to detached hand-driven use. The reports record the input driver, Crown profile when applicable, display policy, actual scroll events, and requested haptics. Analysis separates Crown-driven trials from automated replay and manual capture. Whole-device battery percentages include the test runner, automatic XCTest screenshots, and connection overhead; keep the runner/setup identical for before/after comparisons. The Watch still needs physical preparation: off the charger, unlocked, nearby, and with enough charge. No app runtime/workout override is added; automated replay and idle use the neutral interaction procedure above. Battery health and display settings are not inferred: the default conditions say they are unverified; provide `--conditions '…'` when known.

Two initial physical UI-test attempts on the Ultra 2 timed out while watchOS enabled automation mode, before a test or battery measurement began. A subsequent screenshot showed the Watch's Enter Passcode screen, even though CoreDevice reported `passcodeRequired: false` and `unlockedSinceBoot: true`. Unlock it on the wrist so it stays unlocked, off the charger, before retrying.

The retry with Xcode 27.1 completed on October 2, 2026: the UI runner injected five Crown rotations, the app measured 30.001 seconds, and the host retrieved the exact run-ID report. It recorded 36 scroll events and 36 haptic requests, with 80% charge at both endpoints, nominal thermal state, and no validation issues. This confirms the complete automation/export path. A zero change over 30 seconds is below useful battery resolution and is not a drain estimate. The successful session is `energy-test-results/automation-smoke/89408a55-2e20-4804-b029-684314d4f554`; its source fingerprint is `494b28d26615644bd74521256e60c2dbb02abe97205d3e1b1b7ecdd481f6899b`. Both the Xcode version and device readiness changed, so the result does not isolate the earlier timeout's cause.

The haptics-disabled Crown smoke test also passed: 30.002 seconds, 30 scroll events, zero haptic requests, and a valid retrieved report (`automation-smoke/11f80342-ae5f-4243-a653-13c80df4dbec`). A first 5-minute haptics trial passed with 324 scroll events and matching haptic requests, nominal thermal state, and 80% charge at both endpoints. The next control became inactive after 191 seconds; a subsequent screenshot showed a Time to stand notification. The host retained the flagged report and stopped the batch. Relaunching cleared the notification and allowed the control smoke test to complete. Notifications can therefore interrupt unattended trials; clear existing notifications before starting and keep notification/Focus settings consistent between builds. An interrupted trial must be excluded rather than counted as a complete measurement.

Physical XCTest Crown commands took roughly six seconds each in these trials, despite a requested half rotation at one rotation per second plus a 0.25-second pause. The configured pause is not the full observed command cadence. Reported scroll-event rates capture the resulting workload, which is intermittent and should not be equated with continuous hand spinning.

## Completed Ultra 2 baseline

On October 2, 2026, six valid 5-minute trials completed on the Ultra 2 with the same frozen diagnostic Release build. The first valid haptics trial was retained from session `a3ecabdd-9046-4566-a401-f542f54b15b7`; the five remaining trials completed in session `3c027880-a09e-4d17-91f5-dfbdc5acd311`. Each trial passed XCTest, exported its exact run-ID report, passed report validation, stayed active and unplugged, and reported nominal thermal state. The notification-interrupted control was excluded. The consolidated result is `energy-test-results/automation-baseline/summary.json`, with references to all accepted and excluded raw reports.

| Mode | Valid 5-minute trials | Reported drops, percentage points | Total scroll events | App haptic requests | Median scroll events/sec |
| --- | ---: | --- | ---: | ---: | ---: |
| Automated Crown + app haptics | 3 | 0, 0, 0 | 1,016 | 1,016 | 1.15 |
| Automated Crown, app haptics omitted | 3 | 0, 5, 0 | 1,028 | 0 | 1.13 |

Observed charge readings were only 80%, 75%, and 70%; no finer changes appeared in this dataset. The single 5-point drop occurred in a control with zero app haptic requests. This does **not** establish that the control consumes more energy, or that haptics consume none: rounding/update cadence, different starting charge, and whole-device UI-test overhead prevent that conclusion. The calculated `60 pp/hour` for that one trial is a normalization of one reported charge step, not evidence of a sustained electrical drain rate. The six accepted trials provide a reproducible workload and valid logging/export baseline, but their charge readings do not reliably quantify haptic cost. Longer measurement windows or energy profiling are needed for a useful energy comparison; a detached, hand-driven run remains the real-use reference.

## Completed fixed-rate 10-minute pilot

On October 2, 2026, the same Ultra 2 completed a timed-replay pair at two app scroll changes per second, using Clicks and the frozen diagnostic build with source fingerprint `3b6d61481cf37fb1737baac31c7bfbcb45c35b8d0cad76b53f22b1917dfae2d0`. Both trials passed XCTest and report validation, stayed active and unplugged, and reported nominal thermal state. Both received 26 neutral wake touches. Their actual scroll-event rates were 1.9983/sec, with one endpoint tick omitted at the deadline.

| Mode | Actual duration | Scroll events | App haptic requests | Reported charge | Drop, percentage points |
| --- | ---: | ---: | ---: | --- | ---: |
| Replay + Clicks | 600.001 seconds | 1,199 | 1,199 | 65% → 60% | 5 |
| Same replay, app haptics omitted | 600.001 seconds | 1,199 | 0 | 60% → 60% | 0 |

The summary is `energy-test-results/replay-2hz-pilot/summary.json`; it links the exact accepted reports from session `1f31e930-b7a9-4909-a49e-65f69c44e077`. These results are separate from the earlier intermittent Crown workload. The initial pair appeared consistent with haptics contributing to drain, but the reversed-order repeat below did not reproduce that difference. The reported values in this pair were only 65% and 60%, starting charge differed by five points, and the measurements include the whole Watch and UI-test overhead. Zero reported change in the control does not mean zero consumption. This remains a baseline, with no energy optimization applied.

A preceding valid 90-second replay smoke test recorded 179 scroll events, matching haptic requests, three received wake touches, and no validation issues (`replay-2hz-smoke/d7f52bba-4b52-471a-88d5-0b5f55859395`). An earlier attempt's wake touches missed the diagnostic control and changed the effect; its flagged report is retained and excluded (`replay-2hz-smoke/66f9523c-dadd-4188-8b49-f1ba3d974ad3`). Moving the transparent target to the screen center and checking each touch's acknowledgement passed on the Watch's rotated interface. No additional host screenshots were requested during the accepted measurements.

## Reversed-order repeat

Later on October 2, 2026, the Ultra 2 completed the same 10-minute pair with app haptics omitted first and Clicks second. The source fingerprint, Xcode/SDK, app settings, requested rate, and neutral wake procedure matched the pilot. Each accepted trial passed XCTest and report validation, recorded 1,199 scroll changes and 26 received wake touches, stayed active and unplugged, and reported nominal thermal state.

| Pair and order | Mode | Reported charge | Drop, percentage points |
| --- | --- | --- | ---: |
| Original, first | Haptics on | 65% → 60% | 5 |
| Original, second | Haptics omitted | 60% → 60% | 0 |
| Reversed, first | Haptics omitted | 55% → 50% | 5 |
| Reversed, second | Haptics on | 50% → 50% | 0 |

The original difference reversed. Across the two accepted trials per mode, each mode showed five total reported percentage points of loss over 20 minutes. Both modes performed 2,398 scroll changes; the haptics condition requested 2,398 haptics and the control requested zero. This does not establish equal electrical energy consumption or that haptics cost nothing. It shows that these coarse whole-Watch readings do not reliably isolate haptic cost. Starting charge differed, and there are only two trials per mode. A reported five-point loss cannot be assigned to 1,199 haptic requests from this dataset.

The combined summary is `energy-test-results/replay-2hz-repeat/summary.json`, which links all four accepted reports and the excluded attempt. The accepted reversed pair is session `401587ee-f546-45bb-99b5-4431a1e12e2b`. An earlier control in session `01519d94-c37b-4082-a673-b40622768c76` was interrupted after 554.211 seconds at 20:50 by a Time to stand notification; a screenshot taken after the stopped measurement confirmed the notification. The flagged report was retained and excluded. Relaunching cleared the notification, and the replacement pair completed without changing settings or the source build.

To repeat in reverse order using the existing unchanged build:

```sh
python3 CrownSpin/scripts/energy-tests.py automate \
  --device WATCH_UDID \
  --developer-dir /Applications/Xcode-27.1-beta.app/Contents/Developer \
  --seconds 600 --repetitions 1 --cases replay-no-haptics,replay \
  --steps-per-second 2 --label baseline-replay-2hz \
  --skip-build --build-output /private/tmp/CrownSpinEnergyReplay2Hz \
  --output energy-test-results/replay-2hz-repeat
```

## Active-display idle versus scrolling

The Ultra 2 completed a fresh 10-minute pair on October 2, 2026 after automated idle adopted the same neutral wake and status-query procedure as replay. Both trials used source fingerprint `82f628e733dd53c85537e856476c8cfa3b7dd15a5003866725a84d7e541d926c`, unchanged settings (Clicks, ambient styling enabled, hidden menu, decimal numbers), Xcode build `27A9269`, and SDK `watchos27.0`. Neither had an attached profiler.

| Mode | Reported charge | Scroll changes | App haptic requests | Confirmed wake touches |
| --- | --- | ---: | ---: | ---: |
| Active app idle, 10 minutes | 45% → 45% | 0 | 0 | 27 |
| 2 Hz replay, haptics omitted, 10 minutes | 40% → 40% | 1,199 | 0 | 26 |

Both passed XCTest and report validation, stayed active and unplugged, and reported nominal thermal state. Each saved 22 samples with a maximum gap near 30 seconds. The wake policy matched; actual touch counts differed by one because of UI-action/query overhead. The session is `idle-vs-scroll/8b9f7cce-dc2a-45ce-bb18-a6a36e102352`; `energy-test-results/idle-vs-scroll/summary.json` links the two exact accepted reports. No attempts in this pair were excluded.

The reported five-point charge change appeared between the idle endpoint at 22:05:53 and the scrolling start at 22:07:35, during cooldown and relaunch/setup. It cannot be allocated to either measured workload. This pair does not show that idle or scrolling costs no energy, nor establish equal consumption: reported charge is coarse, initial charge differed, and there is one trial per condition. The old haptics-on/off pairs use a different diagnostic source fingerprint and are not pooled with these trials. The [energy audit](energy-audit.md) separates source-backed optimization candidates from runtime evidence.

## Automated overhead comparison pilot

The October 3 comparison uses two signed Release automation variants from the same frozen app sources. `build-automation` and `automate` accept `--variant original` or `--variant optimized`. The original variant restores the original statistics observation, scrolling-idle timer, menu timer, and immediate preference writes. The optimized variant also retains the original statistics observation and haptic behavior, but uses the approved timer reuse and batched preference writes. Explicit variant identities include their compilation flags, so reports cannot silently mix these two binaries. Use `--variant legacy-unqualified` explicitly for historical source-only identities; new commands default to the current ordinary observation path.

`CrownSpin/scripts/energy-compare.py --session SESSION_DIR` runs a prepared `comparison.json` manifest. It verifies the source/build identities, requires a valid 15-second check for each variant, then runs four 10-minute Clicks trials at two app scroll changes per second in original/optimized/optimized/original order, with 60-second cooldowns. The short checks are excluded from battery analysis. It retrieves and validates each exact run-ID report, preserves failures, retries one interrupted battery capture, and restores the accepted normal optimized app when the batch completes or stops. Restoration has its own recorded install and launch results; a launch timeout does not confirm that the app is open. Replay changes the normal cumulative statistics, and existing app settings remain in place.

Four trials provide two observations per build, below the existing three-run analysis threshold. The pilot summary is descriptive and does not establish battery savings. Charge readings include the whole Watch and UI-test supervision; starting charge and setup history can differ. Synthetic 2 Hz replay does not represent very fast physical Crown input. A hidden menu does not exercise the menu-timer optimization. Independent brightness and battery-health measurements are still absent.

The first two startup attempts stopped before measurement while XCTest timed out enabling automation mode. A screenshot during the second attempt showed **Enter Passcode**, despite CoreDevice reporting no passcode required earlier. These attempts contain no accepted battery data. The Watch must stay unlocked on the wrist, off its charger, for the next startup check; the runner handles neutral display-wake touches once UI automation has initialized. Failed session artifacts are retained under `overhead-energy-compare/3f412bf5-2b5f-4252-9e9d-c17531da95a0` and `overhead-energy-compare/c83804ab-aebc-48d9-a92e-2ad66002c316`.

A further retry also timed out before testing. Capturing the screen **during** the next excluded startup check showed that starting the runner brought up Enter Passcode again. After the user entered the code on that prompt, the test passed, retrieved its exact report, and validated 29 scroll changes with 29 haptic requests over 15.002 seconds, active and unplugged with nominal thermal state. Its 70% endpoints are below useful battery resolution; the captured screen and test supervision also exclude it from battery analysis. The diagnostic session is `overhead-energy-compare/30dd9daf-14d6-4f6e-8905-49b79aadba3b`. The normal optimized app was restored successfully before starting the fresh comparison session.

Both variant startup checks passed in session `overhead-energy-compare/a91486b9-f2ac-444f-9ad6-89ee236d7f25`, but its first long original capture and automatic retry lost the foreground after 152.038 and 167.016 seconds. Their final samples record `inactive` with luminance not reduced, unplugged power, and nominal thermal state; neither is an accepted 10-minute measurement. Earlier XCTest screenshots show the running app, and the retry's failure screenshot shows Control Center. The physical or system action that opened it has not yet been established. The host preserved both flagged reports and restored the normal optimized app successfully. Opening Control Center, switching apps, or adding manual Crown/button input changes the measured conditions; leave the app visible throughout automated replay.

### Completed comparison

The fresh October 3 session `overhead-energy-compare/32695491-dcd7-4360-bd03-dc1a2deb805f` completed all four slots. Each passed XCTest, exact run-ID retrieval, report validation, variant fingerprint checks, and recorded-condition matching. Each measured approximately 600 seconds, 1,199 scroll changes, 1,199 haptic requests, and 26 acknowledged wake touches. Across 88 samples, power stayed unplugged, scene state stayed active, luminance was not reduced, and thermal state stayed nominal.

| Run | Variant | Reported charge | Drop, percentage points |
| --- | --- | --- | ---: |
| 1 | Original | 65% → 65% | 0 |
| 2 | Optimized | 65% → 60% | 5 |
| 3 | Optimized | 60% → 55% | 5 |
| 4 | Original | 55% → 50% | 5 |

The optimized runs showed greater reported loss in this pilot: ten total percentage points over twenty measured minutes, versus five for the original runs. **No battery saving was demonstrated.** Two observations per build, coarse whole-Watch readings, different starting levels, and setup/cooldown history do not establish the cause or a reliable regression. The menu remained hidden, so this workload does not test menu-timer savings. No matched CPU profile was captured. The API request counts match; delivered motor pulses and very fast physical Crown input were not measured.

The final original slot first stopped after 266.453 seconds when a **Time to stand** notification appeared at 2:50 p.m. Its flagged report and XCTest screenshot were retained and excluded; the automatic retry completed without changing settings. The normal optimized app was then restored and opened successfully, with automation launch variables absent. `results.md`, `summary.json`, `verification.json`, and `comparison.json` in the completed session preserve the human-readable result, exact reports, all attempts, and restoration evidence. Earlier failed sessions and short checks are not pooled with this comparison.

## Runtime accounting comparison

`build-automation` and `automate` also accept `--variant timer-only` and `--variant persistence-only`. All four named variants retain the original statistics observation and haptic path. Timer-only reuses both timers with immediate preferences; persistence-only batches preferences with the original timers. `optimized` combines both candidates. Variant identities include the compilation flags.

`automate --runtime-profile` enables diagnostic-only `getrusage` CPU accounting, a count of `ContentView.body` evaluations, and nested wall-time scopes around the scroll handler, haptics/statistics, scrolling-idle timer, and menu timer. CPU snapshots align with the existing battery samples. The optional report fields remain compatible with earlier reports. These captures carry `diagnosticPurpose: runtime-profile-v1` and are excluded from battery analysis. The normal Release binary excludes the instrumentation.

`runtime-compare.py --session SESSION_DIR` consumes a frozen prepared `comparison.json`, validates exact run-ID reports and compiled identities, and compares original/timer-only/persistence-only/optimized followed by the reverse order. The October 3 protocol uses one minute per slot at two timed Clicks scroll changes per second, with fifteen-second cooldowns and unchanged neutral-wake supervision. It excludes interruptions, retries one interrupted slot, stops on other invalid captures, and restores the accepted normal app. `--resume` validates the accepted schedule prefix and unchanged sources before continuing a stopped batch. Failed attempts remain preserved; valid slots are not repeated.

The manifest identifies the exact accepted restoration binary separately when new diagnostic-only source changes alter the profiling-build fingerprint. This is permitted only after verifying the normal behavior is unchanged; the October 3 source check removes only the newly added conditional diagnostic snippets and compares the remainder with the accepted source verbatim.

App CPU accounting excludes other processes, display power, the haptic motor, and GPU energy. Nested wall-time scopes include waiting and must not be summed or called CPU time. Parent-body counts exclude descendant view evaluations. Counter collection and XCTest accessibility/wake queries add overhead, and two captures per variant provide descriptive evidence. A hidden menu does not exercise visible-menu timer reuse. These numbers cannot establish battery savings or equivalence during fast physical Crown input.

## Verify and build

From the repository root:

```sh
python3 CrownSpin/scripts/energy-tests.py verify
python3 CrownSpin/scripts/energy-tests.py build
```

`verify` runs report-validation and statistics XCTest cases, a source-extracted menu-timer method in a macOS state holder, and the Python analysis/comparison tests. The actual statistics source and number-formatting helpers are compiled in a temporary local Swift package. It needs Xcode and Python 3, with no third-party packages or Watch runtime. The holder checks Foundation timer behavior; it does not test Watch rendering or motor delivery. Fixtures and host checks are not battery measurements.

Without `--device`, `build` performs an unsigned Release compile check. It does not install, upload, or alter the Watch. Build for the physical Watch when it is available to Xcode:

```sh
python3 CrownSpin/scripts/energy-tests.py build --device WATCH_UDID --output /tmp/CrownSpinEnergyBaseline
```

The project keeps its configured signing team. If provisioning needs refreshing, explicitly add `--allow-provisioning-updates`. The script stamps the Git revision and a fingerprint of the actual source, assets, and project so uncommitted baseline and optimized builds remain distinguishable. Freeze a build while collecting its repetitions.

The signed app is `/tmp/CrownSpinEnergyBaseline/Build/Products/Release-watchos/CrownSpin Watch App.app`. Install through the connected Watch's Xcode tooling. If the Watch is exposed to CoreDevice, this command can install the built app:

```sh
xcrun devicectl device install app --device WATCH_UDID '/tmp/CrownSpinEnergyBaseline/Build/Products/Release-watchos/CrownSpin Watch App.app'
```

If the command-line installer drops the connection, use Xcode → Open Developer Tool → Device Hub, select the Watch, and open Info → Apps. Click Add and select the signed app bundle. This path successfully installed the baseline on the Ultra 2 after two command-line attempts failed with a remote connection error. Apple describes the [Device Hub Apps inspector](https://developer.apple.com/documentation/xcode/managing-apps-on-devices); its documented distribution format is an `.ipa`, while this local development `.app` was also accepted.

Launch it from the Watch itself, off the charger and detached from the debugger. A development installation may replace the installed app with the same bundle ID; it shares the normal preferences and local statistics. Replay increments normal statistics just like scrolling.

## Capture the Ultra 2 baseline

1. First measure the unmodified App Store app manually if you want an independent real-world reference. Record Watch model, watchOS, battery health, display settings, start/end percentages, effect, elapsed time, and activity.
2. In the diagnostic app, open Menu → Energy Tests. Select Real Crown capture, 10 minutes, and Clicks initially.
3. Set the label to `baseline`. In Conditions, record the particular Watch, battery health, brightness, Always On, wake duration, connectivity, and wrist/display procedure. Keep this exact text for later matching trials. Setup is saved for repeat runs.
4. Tap Start. After setup dismisses and one second of settling, measurement begins. Spin as normally as possible. Timing and logging finish automatically; do not change effects or open controls during the run.
5. Reopen Energy Tests to see the result. Flagged trials are retained for diagnosis but excluded from comparisons. Repeat at least three times per condition, with comparable starting charge and a cool Watch. Use a similar recorded scroll-event rate in every trial.
6. Capture App idle and the replay/haptics-disabled controls when feasible. Idle timers may be suspended by watchOS; returning late produces a duration-overrun flag rather than pretending the trial finished on time.

Runs save to `Documents/EnergyTests/<run-id>.json`. Battery readings stay in memory until the run ends, then the report is written once. A force quit or crash before completion can lose that unfinished run. Battery monitoring is enabled before measurement and restored afterward. No report is sent over the network while measuring.

Reports contain requested/actual timing, charge and power-state samples, lifecycle and luminance state, thermal state, source identification, settings, scroll events, and haptic requests. Unknown battery readings, charging, serious thermal pressure, changed settings, interruptions, missed replay work, and duration overruns are flagged. Sampling cannot detect every brief event between samples; keep the Watch unplugged throughout each trial.

## Retrieve and compare

For a Watch exposed to `devicectl`:

```sh
python3 CrownSpin/scripts/energy-tests.py fetch --device WATCH_UDID --output energy-test-results
python3 CrownSpin/scripts/energy-tests.py analyse energy-test-results --before baseline --after optimized
```

If that file service is unavailable, retrieve the app container through Xcode's device tooling and analyse its `Documents/EnergyTests` folder. Listing, copying, and export of the Ultra 2's completed 30-second automated Crown report have been verified. The script creates the local destination directory before copying, as CoreDevice requires.

After an optimization, build the same diagnostic Release variant, change only the label to `optimized`, and repeat the same cases. Do not change haptic timing or effects for the first optimization pass.

Analysis rejects flagged, malformed, simulated, and duplicate runs. It groups by hardware, watchOS, settings, conditions, workload, duration, toolchain, and initial thermal state. A comparison needs at least three repetitions per label, consistent source fingerprints within each label, starting charge within five percentage points, and comparable observed input rates (5% for replay and automated Crown, 10% for manual Crown capture). It prints medians and ranges in **battery percentage points per hour**, not electrical power or remaining runtime. Zero battery change does not establish zero consumption; use longer runs when readings do not resolve the drain. A difference in medians alone is not proof of savings.

## Evidence and current limits

The harness has been compiled for physical-watch Release targets with and without the diagnostic flag. Fourteen shared report XCTest cases and twenty Python analysis/automation tests passed on the Mac. On October 2, 2026, the signed diagnostic Release app (version 1.0, build 14) was installed through Device Hub on the physical Apple Watch Ultra 2 running watchOS 27.2. The normal Release binary excludes the diagnostic controller. The Xcode 27.1 runner subsequently passed both physical Crown smoke modes, completed the six valid Crown baseline trials, and passed the fixed-rate replay smoke, 10-minute pilot pair, and reversed-order pair above. All accepted reports were retrieved and validated. Automated idle was then aligned with replay, the fresh 10-minute idle/scrolling pair completed, and a separate physical CPU trace was recovered as described in [the audit](energy-audit.md). All profiling-only runs are excluded from battery comparisons. The host does not request extra screenshots or stream the display during measurement; XCTest captures its own UI-action screenshots in result bundles. No watchOS Simulator runtime was available during initial development. The observed battery readings do not resolve haptic energy cost. Subsequent candidate changes and physical haptic acceptance are tracked in [the energy audit](energy-audit.md) and [haptic comparisons](haptic-comparison.md); no measured battery saving has been established.

Apple documents [Watch battery monitoring](https://developer.apple.com/documentation/watchkit/wkinterfacedevice/isbatterymonitoringenabled), [battery-level values and unavailable readings](https://developer.apple.com/documentation/watchkit/wkinterfacedevice/batterylevel), and [foreground/background execution](https://developer.apple.com/documentation/watchkit/background-execution). Its [haptic playback documentation](https://developer.apple.com/documentation/watchkit/wkinterfacedevice/play%28_%3A%29) explains why API-request counts do not guarantee uninterrupted motor feedback.

Restoration is part of completing a pilot or runtime comparison. A failed install or launch leaves `status: restoration-failed` with the capture outcome and cleanup error recorded separately. Retry only that cleanup with `energy-compare.py --session SESSION --restore-only` (or the same option on `runtime-compare.py`); prior restore logs and state are retained before retry. This performs device installation and launch, so use it only for an authorized physical session. It does not repeat captured trials.

Haptics Only captures record whether the display started black or with controls revealed; these states and older reports with unknown state stay separate. Revealing controls during a capture flags that run. Ordinary scroll-to-black behavior remains part of the selected workload.

A failed automation rebuild invalidates its success record before compilation. `--skip-build` refuses old or changed app/runner/configuration products, including directories prepared before product records were introduced. Rebuild those in a fresh output directory; existing evidence is retained.


Before starting a new pilot, runtime comparison or native-list comparison, pin
its already accepted normal app locally:

```sh
python3 CrownSpin/scripts/energy-compare.py --record-normal PATH-TO-ACCEPTED-NORMAL-BUILD.json
```

The record must identify the app and source fingerprint and have
`diagnosticMarkersAbsent: true` from normal-build acceptance. This command
checks the current executable for diagnostic markers and records a fingerprint
of the complete app bundle, including permissions and signature files. It does
not install or launch anything and does not establish physical acceptance. A
changed product cannot overwrite an existing fingerprint: accept the new normal
build separately with a new record. Comparisons verify the recorded product
before device work and again before restoration. Legacy records without a
product fingerprint must be verified and recorded before reuse; source identity
alone cannot distinguish the explicit legacy diagnostic variant from a normal
app built from the same source.
