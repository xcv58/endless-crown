# Endless Crown App Store screenshot kit

Prepared for **1.0.1**, English (U.S.). Six upload images, each **416 × 496 pixels**, PNG, RGB, with no alpha channel.

[View the gallery](preview.html) · [Contact sheet](contact-sheet.png) · [First-image comparison](comparison.html) · [Export images](en-US/)

## Upload order and copy

| Order | File | Headline | Explanation |
| --- | --- | --- | --- |
| 1 | `01-spin.png` | Turn the Crown. | Feel the haptics. |
| 2 | `02-effects.png` | 15 ways to feel it. | Find your favorite haptic effect. |
| 3 | `03-gestures.png` | Simple by design. | Tap to switch. Long-press to explore. |
| 4 | `04-numbers.png` | Count your way. | Six formats. One endless scroll. |
| 5 | `05-stats.png` | See your spin stats. | Session and all-time stats, kept locally. |
| 6 | `06-ambient.png` | A quieter screen. | Ambient mode keeps the visuals subtle. |

Unzip the prepared download and upload the six individual PNG files to the **Apple Watch** screenshots slot in this order. The contact sheet and HTML gallery are review material and should not be uploaded as screenshots. All Watch localizations must use the same screenshot dimensions. No iPhone screenshot set is needed for this Watch-only app.

## Design decisions

The opening image explains the core interaction; the next two communicate effect choice and simple gestures. The remaining images cover number formats, local statistics, and Ambient Mode. Each card has one headline and one short explanation. The first image places the complete authentic app capture inside official Apple Watch Series 11 artwork so the Digital Crown interaction is recognizable. The five feature images remain bezel-free, with app captures occupying about 62% of each image area. Capture aspect ratios are preserved, and no text covers controls.

The restrained dark background and pale sage headings follow the existing product site's palette. A bright High Contrast capture opens the set; the subdued Ambient capture closes it. These are actual app appearance modes, rather than edited UI. Original captures, clocks, displayed counters, and interface text are retained. Only the first image has a device bezel. There are no invented screens, fake statistics, promotional prices, or battery-life claims. Ambient Mode refers to dimmer visuals, not an always-on or keep-awake feature.

The source captures already exist in [Screenshots](../Screenshots/). The 1.0.1 app changes timer and persistence internals while retaining these screens and controls. This redesign typesets explanations around existing authentic captures; it does not claim a fresh Simulator capture.

## Watch hero and comparison

[Compare the two layouts](comparison.html) uses identical copy and the same authentic capture. The hero uses the complete official Space Gray 46mm Apple Watch Series 11 with Black Sport Band, proportionally scaled without cropping, rotation, extra effects, or hardware changes. The native 416 × 496 capture fits Apple's matching 416 × 496 transparent screen aperture exactly. The frame is 245 × 385 pixels on the export; app details are smaller here, so hardware is used on this simple first screen only.

The prior first screenshot is retained in `variants/01-spin-original.png`; `variants/01-spin-flat.png` is the comparison with the new copy and no frame. Neither variant is included in the upload ZIP.

Apple owns the device artwork. The standalone PNG and supplied license are stored locally in ignored `resources/` and excluded from export archives and Git. To reproduce the render on another machine, download [Apple Watch Series 11 product bezels](https://devimages-cdn.apple.com/design/resources/download/Bezel-Apple-Watch-Series-11-2025.dmg) from [Apple Design Resources](https://developer.apple.com/design/resources/#product-bezels), review the included license, and copy `PNG/Sport Band/Apple Watch S11 - 46mm - Aluminum Space Gray + Sport Band Black.png` to `resources/apple-watch-series-11-46mm-space-gray-black-sport-band.png`. Provenance, screen placement, and the original resource hash are recorded in `manifest.json`. Rendered material is for this watchOS app; do not extract or redistribute Apple's standalone template content.

Apple Watch is a trademark of Apple Inc., registered in the U.S. and other countries.

## Apple's guidance used

- [Product-page guidance](https://developer.apple.com/app-store/product-page/): lead with the app's essence and give later screenshots a main benefit or feature.
- [App Review guideline 2.3.3](https://developer.apple.com/app-store/review/guidelines/#accurate-metadata): show the app in use; explanatory text and image overlays are allowed.
- [Screenshot specifications](https://developer.apple.com/help/app-store-connect/reference/app-information/screenshot-specifications/): 416 × 496 is an accepted Watch size, with one consistent size across all Watch localizations.
- [Marketing artwork guidance](https://developer.apple.com/app-store/marketing/guidelines/): use official hardware images as supplied, keep promotional copy outside them, and preserve their proportions and complete appearance.
- [Watch metadata guidance](https://developer.apple.com/help/app-store-connect/create-an-app-record/add-watchos-app-information/): Watch-only apps do not need iPhone screenshots.

The layout choices are our design interpretation of these rules; Apple does not prescribe this exact style or guarantee review approval or conversion improvement.

## Edit and render

- Edit `manifest.json` to change copy or capture selection.
- Edit `template.html` to adjust typography and layout.
- `render.mjs` creates the six PNGs, gallery, contact sheet, and geometry/hash report.

With Node.js and a matching Playwright installation:

```bash
cd CrownSpin/AppStoreAssets/ScreenshotKit
npm install
npx playwright install chromium
npm run render
```

For the bundled Codex runtime on this Mac, using a separate headless Chrome profile:

```bash
SCREENSHOT_CHROMIUM_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
NODE_PATH=/Users/yihong/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules \
/Users/yihong/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node render.mjs
```

The renderer checks text bounds, separation from the capture, aspect ratio, loaded image assets, and browser errors. `render-report.json` records copy, source hashes, export hashes, and measured geometry. System font rendering is platform-dependent; use macOS to reproduce the current design closely.

All six English (U.S.) PNGs were uploaded to the version 1.0.1 Apple Watch screenshot slot and saved in the specified order on October 4, 2026. A page reload confirmed the screenshots and release copy persisted. The version is **Prepare for Submission**; binary upload and App Review submission remain pending. See the [store preparation record](../../../docs/releases/1.0.1/app-store-preparation.json).
