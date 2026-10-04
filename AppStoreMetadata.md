# Endless Crown - App Store Connect Metadata

## App Information

### App Name
Endless Crown

### Subtitle (30 characters max)
Digital Crown Haptics

### Category
- Primary: Lifestyle
- Secondary: Utilities

### Content Rating
4+ (No objectionable content)

---

## Version Information

### What's New (Version 1.0.1)
Internal efficiency improvements during Crown scrolling, with the same familiar haptic feedback.

Preparation and review notes: [1.0.1 release materials](docs/releases/1.0.1/README.md).

### What's New (Version 1.0)
Initial release of Endless Crown, a watch-only haptic fidget experience for Apple Watch.

- 15 selectable haptic effects
- Digital Crown scrolling feedback
- Local usage statistics
- Ambient mode
- Apple Watch complication

---

## App Store Listing

### Promotional Text (170 characters max)
Spin the Digital Crown for quiet haptic feedback, 15 effects, number formats, local stats, ambient mode, and an Apple Watch complication.

### Description (4000 characters max)
Endless Crown is a watch-only haptic fidget that turns spinning the Apple Watch Digital Crown into quiet tactile feedback.

Open Endless Crown, rotate the Digital Crown, and feel a crisp haptic response as you scroll through an infinite numbered list. The interface stays dark and minimal, making it easy to use for a quick tactile break without pulling out your phone.

Choose from 15 haptic effects:

- Clicks
- Soft
- Heavy
- Buzz
- Ping
- Thud
- Drift
- Pulse
- Heartbeat
- Double Tap
- Gallop
- Waltz
- Staccato
- Wave
- Random

Endless Crown also includes local usage statistics, ambient mode, configurable number formats, and a WidgetKit complication that shows your current item and total haptic count.

Highlights:

- Built exclusively for Apple Watch
- Uses the Digital Crown as the main interaction
- Silent haptic feedback
- Fast effect switching
- Decimal, Roman, Binary, Hex, Octal, and Base-26 number formats
- Local-only preferences and stats
- No account, ads, analytics, or backend

How to use:

1. Open Endless Crown on Apple Watch.
2. Rotate the Digital Crown to scroll and feel haptics.
3. Tap the number line or effect chip to cycle effects.
4. Long-press the number line or effect chip to open the Effects picker.
5. Double-tap the number line or effect chip to open the menu.
6. Use the menu to change effects, number format, statistics, guide, reset, ambient mode, or menu icon visibility.

Endless Crown requires Apple Watch with watchOS 10 or later.

### Keywords (100 characters max, comma separated)
fidget,watch,focus,calm,tactile,sensory,clicks,spinner,spin,scroll,counter,relax

---

## Support Information

### Support URL
https://github.com/xcv58/endless-crown/issues

### Marketing URL (optional)
https://github.com/xcv58/endless-crown

### Privacy Policy URL
Use a public URL for `PrivacyPolicy.md`, for example:

```text
https://github.com/xcv58/endless-crown/blob/master/PrivacyPolicy.md
```

This URL is only suitable if the repository is public. If the repository is private, host the privacy policy on a public webpage before submission.

---

## App Privacy

Suggested App Store Connect answers, assuming no analytics, ads, crash reporting SDKs, or network data collection are added:

- Data Collection: No, this app does not collect data from this app.
- Tracking: No.
- Required reason APIs: UserDefaults only, declared in the app and complication privacy manifests.

---

## Screenshots

Prepared annotated Apple Watch screenshots for version 1.0.1, in upload order:

1. [**Turn the Crown.**](CrownSpin/AppStoreAssets/ScreenshotKit/en-US/01-spin.png) — Feel the haptics.
2. [**15 ways to feel it.**](CrownSpin/AppStoreAssets/ScreenshotKit/en-US/02-effects.png) — Find your favorite haptic effect.
3. [**Simple by design.**](CrownSpin/AppStoreAssets/ScreenshotKit/en-US/03-gestures.png) — Tap to switch. Long-press to explore.
4. [**Count your way.**](CrownSpin/AppStoreAssets/ScreenshotKit/en-US/04-numbers.png) — Six formats. One endless scroll.
5. [**See your spin stats.**](CrownSpin/AppStoreAssets/ScreenshotKit/en-US/05-stats.png) — Session and all-time stats, kept locally.
6. [**A quieter screen.**](CrownSpin/AppStoreAssets/ScreenshotKit/en-US/06-ambient.png) — Ambient mode keeps the visuals subtle.

Each PNG is `416 x 496`, RGB, with no alpha channel. This is an accepted Apple Watch Series 12 / Series 11 / Series 10 screenshot size. The same size must be used across every Watch localization. Six files are prepared within Apple's limit of ten.

[Preview gallery](CrownSpin/AppStoreAssets/ScreenshotKit/preview.html) · [Editable kit and upload notes](CrownSpin/AppStoreAssets/ScreenshotKit/README.md)

The first image places the authentic app capture inside official Apple Watch Series 11 hardware artwork to show the Digital Crown. The remaining five images use larger, bezel-free app captures. Captures are complete and proportionate below the explanatory text; original screen content is retained. The existing raw JPEG captures remain in `CrownSpin/AppStoreAssets/Screenshots/`.

Uploaded all six English (U.S.) PNGs to the version 1.0.1 Apple Watch screenshot slot on October 4, 2026, in the order shown above. Save and page reload confirmed persistence. The version is **Prepare for Submission**; no build is selected and App Review submission remains pending. See the [preparation record](docs/releases/1.0.1/app-store-preparation.json).

---

## App Preview Video (Optional)

App previews are optional. If you create one later:

1. Show Endless Crown launching on Apple Watch.
2. Rotate the Digital Crown.
3. Switch effects.
4. Open the Effects picker.
5. Show the complication on a watch face.

---

## Localization

Primary language: English (U.S.)

Additional localizations can wait until after 1.0 unless you plan a multi-region launch with translated metadata and screenshots.

---

## Pricing

Suggested starting price: Free or $0.99.

In-app purchases: None.

---

## Age Rating Questionnaire Answers

| Question | Answer |
| --- | --- |
| Cartoon or Fantasy Violence | None |
| Realistic Violence | None |
| Sexual Content or Nudity | None |
| Profanity or Crude Humor | None |
| Alcohol, Tobacco, or Drug Use | None |
| Simulated Gambling | None |
| Horror/Fear Themes | None |
| Medical/Treatment Information | None |
| Unrestricted Web Access | No |

Expected result: 4+

---

## Review Notes

Endless Crown is a watch-only Digital Crown haptic fidget app. It has no login, backend, ads, analytics, purchases, or special permissions.

How to test:

1. Install Endless Crown on Apple Watch.
2. Open the app.
3. Rotate the Digital Crown to scroll and feel haptic feedback.
4. Tap the number line or effect chip to cycle effects.
5. Long-press the number line or effect chip to open the Effects picker.
6. Double-tap the number line or effect chip to open the menu.
7. In the menu, try Numbers, Statistics, Guide, Ambient Mode, and Hide Menu Icon.
8. Add the Endless Crown complication to a watch face to view the current item and haptic count.

Note: The simulator can verify UI behavior, but physical haptic feedback requires an Apple Watch.

---

## Checklist Before Submission

- [x] App icons generated.
- [x] Apple Watch screenshots prepared.
- [x] Privacy manifests added.
- [x] Release build verified.
- [x] Watch simulator tests passed.
- [x] App Store distribution profiles available for all three bundle IDs.
- [x] App Store Connect IPA exported.
- [x] App Store Connect app record created for `media.jenny.crownspin`.
- [ ] Privacy policy hosted at a public URL.
- [ ] Support URL confirmed public and accessible.
- [x] App tested on a physical Apple Watch through TestFlight.
- [x] Build uploaded to App Store Connect.
- [x] Build selected for submission.
