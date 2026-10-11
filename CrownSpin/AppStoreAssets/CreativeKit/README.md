# Endless Crown App Store creative assets

**October 11 publication update:** Chrome sign-in restored. Header v4 and search v3 are approved and published on the released 1.0.1 English (U.S.) default placements; the updated existing Reddit CPP is Approved with its link enabled. Exact asset usage and fresh reference crops are verified. The daily review task is complete, so its deleted automation was not recreated. New physical Store propagation is unverified; the separate CPP Watch screenshot omission remains.

## Published replacement without canvas bands

[Header v4 and search v3](production/2026-10-10-fullbleed-c-v3/README.md) replace the baked-in charcoal surround with photographic extensions. Both are Approved and published. Apple reference previews pass on iPhone light/dark and iPad portrait light/landscape dark. The existing Reddit CPP update is Approved; previous v2 assets remain preserved as references.

## Selected artwork

**The user selected [C — Close tactile detail](candidates/fresh-screenshot-round2/03-close-crop.png).** Its art direction, single visible Crown and counter 4698 are retained in the [current production package](production/2026-10-10-fullbleed-c-v3/README.md). All prior versions remain preserved in the [v2 archive](production/2026-10-07-selected-c-v1/README.md). The [Reddit custom page](custom-product-pages/reddit-haptic-fidget/README.md) retains its promotional text, four keywords and public ID, but the complete Chrome page still omits Watch screenshots; the ordinary listing retains its gallery and remains recommended for promotion. October 10 user iPhone captures verify previous v2 artwork only.

[Compare the four fresh concepts](candidates/fresh-screenshot-round2/preview.html) · [Exact prompts and provenance](candidates/fresh-screenshot-round2/README.md). They were generated from the authentic 4698 app capture and official hardware reference. All prior versions remain preserved.

The original [candidate 3, version 3](candidates/03-editorial-wrist-v3.png) is on hold for duplicated Crown geometry. The subsequent repair-round option 4 recommendation was withdrawn after the user still saw a double Crown. All earlier files remain intact.

The later [production/2026-10-06-editorial-v1](production/2026-10-06-editorial-v1/README.md) package is retained as a rejected attempt for reference. A live check found one incomplete search-image entry from that upload, with no dimensions or review status. It remains unselected. It was not submitted for review or published by this workflow. Do not submit or select its assets for Store placement.

The earlier artwork below remains preserved. The [reference archive](references/2026-10-06-before-creative-upload/backup-manifest.json) also retains the original creative exports and the existing six Store screenshots. Check the selected C production package's delivery record for live upload/review state.

Local first design draft, prepared October 6, 2026. Not uploaded, submitted, approved, or published.

## Artwork

The core message is **Turn the Crown. Feel the haptics.** with **A haptic fidget for Apple Watch.** as a short explanation. It follows the existing screenshot kit's charcoal background and pale sage type. The complete official Watch frame surrounds the authentic main-screen capture; no UI, displayed statistics, haptic behavior, or battery savings are invented.

- `exports/endless-crown-header-en-US.jpg`: 3840 × 1646, product-page header.
- `exports/endless-crown-search-en-US.jpg`: 1920 × 1280, search result.
- `preview.html`: review gallery.
- `manifest.json` and `template.html`: editable copy, source provenance, and layout.

The images complement the existing six Apple Watch screenshots. No pricing, external links, awards, download prompts, or battery-life claims appear in the creative.

## Eligibility and release boundary

Apple documents these placements for iOS/iPadOS 27 and later. Endless Crown is a Watch-only app represented by an iOS record in App Store Connect. A live read-only check confirmed the released 1.0.1 page exposes **Header and Search Results**, **Browse Assets**, and the new **Asset Library** with approved Watch screenshots. This establishes that the asset-management controls are available for this app; it does not independently prove visibility in the native Watch App Store.

Apple permits standalone creative-asset review in Asset Library and selection of approved assets on a released version without a new binary. Before publishing, confirm compatibility in **Works With** and use the native preview to check cropping, metadata overlays, devices, orientations, and light/dark appearances. These drafts use conservative spacing; exact Apple-template safe areas have not been independently validated.

## Render again

Obtain the official Apple Watch Series 11 46mm Space Gray/Black Sport Band PNG and its license from [Apple Design Resources](https://developer.apple.com/design/resources/#product-bezels), as described in the existing `ScreenshotKit/README.md`. Place the unmodified PNG at the ignored path `resources/apple-watch-series-11-46mm-space-gray-black-sport-band.png`. The expected source hash is in `manifest.json`. Do not commit or separately distribute Apple's standalone resource.

Serve `CrownSpin/AppStoreAssets` locally. Open `CreativeKit/template.html?placement=header` at 3840 × 1646 CSS pixels and `?placement=search` at 1920 × 1280. Wait until `main[data-ready="true"]` is present and images/fonts are loaded, capture the full artwork, and export opaque JPEGs. Validate final dimensions, visual bounds, and source hashes.

Apple owns the device artwork. Apple Watch is a trademark of Apple Inc., registered in the U.S. and other countries.

## Primary guidance

- [Apple's October 5 announcement](https://developer.apple.com/news/?id=ljpl7kyn)
- [Asset best practices and resources](https://developer.apple.com/app-store/asset-best-practices/)
- [Creative-asset specifications](https://developer.apple.com/help/app-store-connect/reference/app-information/creative-assets-specifications)
- [Manage App Store assets](https://developer.apple.com/help/app-store-connect/manage-app-information/manage-your-app-store-assets)
