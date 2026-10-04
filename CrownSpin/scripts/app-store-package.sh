#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROJECT_PATH="$ROOT_DIR/CrownSpin/CrownSpin.xcodeproj"
EXPORT_OPTIONS="$ROOT_DIR/CrownSpin/AppStoreExportOptions.plist"
ARCHIVE_PATH="${ARCHIVE_PATH:-/tmp/CrownSpin-submit.xcarchive}"
EXPORT_PATH="${EXPORT_PATH:-/tmp/CrownSpin-submit-export}"
IPA_OUTPUT="${IPA_OUTPUT:-}"
MODE="${1:-export}"

case "$MODE" in
  export|upload)
    ;;
  *)
    echo "Usage: $0 [export|upload]" >&2
    exit 64
    ;;
esac

rm -rf "$ARCHIVE_PATH" "$EXPORT_PATH"

xcodebuild \
  -project "$PROJECT_PATH" \
  -scheme CrownSpin \
  -configuration Release \
  -archivePath "$ARCHIVE_PATH" \
  -allowProvisioningUpdates \
  archive

if [[ "$MODE" == "upload" ]]; then
  TMP_EXPORT_OPTIONS="$(mktemp /tmp/CrownSpinUploadExportOptions.XXXXXX.plist)"
  cp "$EXPORT_OPTIONS" "$TMP_EXPORT_OPTIONS"
  /usr/libexec/PlistBuddy -c 'Set :destination upload' "$TMP_EXPORT_OPTIONS"
  xcodebuild \
    -exportArchive \
    -archivePath "$ARCHIVE_PATH" \
    -exportPath "$EXPORT_PATH" \
    -exportOptionsPlist "$TMP_EXPORT_OPTIONS" \
    -allowProvisioningUpdates
  rm -f "$TMP_EXPORT_OPTIONS"
else
  xcodebuild \
    -exportArchive \
    -archivePath "$ARCHIVE_PATH" \
    -exportPath "$EXPORT_PATH" \
    -exportOptionsPlist "$EXPORT_OPTIONS" \
    -allowProvisioningUpdates
  VERSION="$(/usr/libexec/PlistBuddy -c 'Print :ApplicationProperties:CFBundleShortVersionString' "$ARCHIVE_PATH/Info.plist")"
  BUILD="$(/usr/libexec/PlistBuddy -c 'Print :ApplicationProperties:CFBundleVersion' "$ARCHIVE_PATH/Info.plist")"
  IPA_OUTPUT="${IPA_OUTPUT:-$ROOT_DIR/CrownSpin/AppStoreBuilds/CrownSpin-$VERSION-$BUILD.ipa}"
  mkdir -p "$(dirname "$IPA_OUTPUT")"
  cp "$EXPORT_PATH/CrownSpin.ipa" "$IPA_OUTPUT"
  echo "Exported IPA: $IPA_OUTPUT"
fi
