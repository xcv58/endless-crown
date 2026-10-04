# Endless Crown 1.0.1 release preparation

Planned version: **1.0.1 (15)**. App Store app ID: **6777250620**.

This is a maintenance update for the existing Watch-only app. The public App Store lookup returned version 1.0 during preparation. Build 15 follows the repository's build 14; its availability in App Store Connect must be confirmed before upload.

## Ready-to-use copy

- [What's New, English (U.S.)](whats-new-en-US.txt)
- [App Review notes, English (U.S.)](review-notes-en-US.txt)
- [Existing listing metadata](../../../AppStoreMetadata.md)

Listing description, subtitle, keywords, privacy answers, pricing, and screenshots have no change required by this patch. Existing screenshots are in [AppStoreAssets](../../../CrownSpin/AppStoreAssets/Screenshots).

## Included changes

- Reuse the scrolling idle timer and menu hide timer during ongoing input, keeping their existing 1.5-second and 3-second deadlines.
- Batch total haptics, peak speed, and the complication's current item on one nominal two-second timer. More input does not postpone an existing batch.
- Submit pending values on idle, scene inactivity/background, session boundaries, resets, and number-format changes before widget reloads.
- Preserve the original statistics observation, live counter publications, effect selection, and per-scroll haptic request logic.
- Name exported IPAs using the archived version and build, with an optional IPA_OUTPUT override.

The energy-test app, UI automation, experimental haptic/statistics variants, and battery reporting are outside this release patch.

## Evidence and limitation

The accepted normal build received the user's manual feedback: "I tried it, and it feels normal." Source comparison also checks that haptic requests, Random selection, preview feedback, rebalancing, and live haptic recording match the original implementation. The version-bumped distribution build still needs its own final device acceptance.

The original-versus-optimized battery pilot was inconclusive. In a later phased ten-minute comparison on one Ultra 2, both the native app list and the optimized app reported five percentage points of charge loss per run. That experiment did not compare the original app with the optimized app and did not reproduce continuous fast spinning. These results do not establish battery savings; consumer copy makes no such claim.

Live statistics remain immediate. Pending persisted totals, peak speed, and current item can lag the app by the nominal two-second batching interval, which may run later if the run loop is busy. Abrupt termination before submission can lose the latest batch. UserDefaults storage is itself asynchronous; submitting a batch is not a synchronous disk flush.

## Release validation and remaining steps

Local preparation passed:

- 55 statistics tests and four tests of the source-extracted menu timer on macOS. The timer holder does not test mounted Watch UI or physical motor delivery.
- Source comparison against the accepted normal app and original haptic implementation; no diagnostic build flags or energy-report keys in the release sources.
- Signed archive and App Store distribution export with stable Xcode 27.0 (27A266a). All three bundles contain version 1.0.1/build 15; signatures and non-debuggable App Store distribution profiles verified.

This Mac has no Watch simulator runtime installed. The repository's GitHub Tests workflow runs the Watch simulator unit suite on the pull request.

Preparation status is recorded in the local release validation report. Before store delivery:

- Confirm version 1.0.1 and build 15 are unused in App Store Connect.
- Upload the prepared distribution build and wait for processing.
- Install that processed build through TestFlight on Apple Watch; check fast Clicks and Random, effect switching, menu timing, retained statistics, counter reset, number formats, and the complication.
- Select the build, paste the prepared What's New and App Review notes, retain the existing listing assets, and submit for review.
- Choose the desired public-release timing after review.

Upload, TestFlight assignment, submission, and public release are separate steps and are not performed as part of this preparation.
