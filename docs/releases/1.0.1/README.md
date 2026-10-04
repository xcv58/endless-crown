# Endless Crown 1.0.1 release preparation

Planned version: **1.0.1 (15)**. App Store app ID: **6777250620**.

This is a maintenance update for the existing Watch-only app. App Store Connect shows released version 1.0/build 15. The prepared distribution archive is version 1.0.1/build 15; binary upload and processing remain pending.

## Ready-to-use copy

- [What's New, English (U.S.)](whats-new-en-US.txt)
- [App Review notes, English (U.S.)](review-notes-en-US.txt)
- [Existing listing metadata](../../../AppStoreMetadata.md)

Listing description, subtitle, keywords, privacy answers, and pricing have no change required by the production patch. A new set of six annotated Apple Watch screenshots is prepared in the [editable screenshot kit](../../../CrownSpin/AppStoreAssets/ScreenshotKit/README.md), with explanations around authentic app captures, official Watch artwork on the first image, and larger bezel-free feature screens. See the [gallery](../../../CrownSpin/AppStoreAssets/ScreenshotKit/preview.html) for the upload order.

## App Store draft prepared

On October 4, 2026, version **1.0.1** was created in App Store Connect in **Prepare for Submission**. The six English (U.S.) Watch screenshots were uploaded and ordered from Crown hero through Ambient Mode. What's New and App Review notes were saved, and the existing promotional text was retained. A page reload confirmed the assets and copy persisted. The inherited manual release choice remains selected.

[Store draft](https://appstoreconnect.apple.com/apps/6777250620/distribution/ios/version/inflight) · [Preparation record](app-store-preparation.json)

No build is selected. Binary upload, TestFlight acceptance, App Review submission, and public release remain pending.

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

- Upload the prepared distribution build and wait for processing.
- Install that processed build through TestFlight on Apple Watch; check fast Clicks and Random, effect switching, menu timing, retained statistics, counter reset, number formats, and the complication.
- Select the processed build, confirm the already-saved release copy and six Watch screenshots, and submit for review when authorized.
- Choose the desired public-release timing after review.

The draft metadata and screenshots are saved. Binary upload, TestFlight assignment, App Review submission, and public release are separate steps and have not been performed.
