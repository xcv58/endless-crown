import XCTest
import WidgetKit

final class CrownSpinComplicationTests: XCTestCase {

    private let sharedDefaults = UserDefaults(suiteName: appGroupSuiteName)

    override func setUp() {
        super.setUp()
        sharedDefaults?.removeObject(forKey: "stats.totalHaptics")
        sharedDefaults?.removeObject(forKey: "selectedHapticPattern")
        sharedDefaults?.removeObject(forKey: "currentItemNumber")
        sharedDefaults?.removeObject(forKey: CrownPositionKeys.saved)
        sharedDefaults?.removeObject(forKey: "numberSystem")
    }

    override func tearDown() {
        sharedDefaults?.removeObject(forKey: "stats.totalHaptics")
        sharedDefaults?.removeObject(forKey: "selectedHapticPattern")
        sharedDefaults?.removeObject(forKey: "currentItemNumber")
        sharedDefaults?.removeObject(forKey: CrownPositionKeys.saved)
        sharedDefaults?.removeObject(forKey: "numberSystem")
        super.tearDown()
    }

    // MARK: - CrownSpinEntry

    func testEntryStoresAllProperties() {
        let date = Date()
        let entry = CrownSpinEntry(
            date: date,
            totalHaptics: 42,
            currentPattern: "Heavy",
            patternIcon: "hammer",
            currentItemNumber: 7,
            numberSystem: .roman
        )
        XCTAssertEqual(entry.date, date)
        XCTAssertEqual(entry.totalHaptics, 42)
        XCTAssertEqual(entry.currentPattern, "Heavy")
        XCTAssertEqual(entry.patternIcon, "hammer")
        XCTAssertEqual(entry.currentItemNumber, 7)
        XCTAssertEqual(entry.numberSystem, .roman)
    }

    func testEntryDefaultValues() {
        let entry = CrownSpinEntry(
            date: Date(),
            totalHaptics: 0,
            currentPattern: "Clicks",
            patternIcon: "hand.tap",
            currentItemNumber: 0,
            numberSystem: .decimal
        )
        XCTAssertEqual(entry.totalHaptics, 0)
        XCTAssertEqual(entry.currentPattern, "Clicks")
        XCTAssertEqual(entry.patternIcon, "hand.tap")
        XCTAssertEqual(entry.currentItemNumber, 0)
        XCTAssertEqual(entry.numberSystem, .decimal)
    }

    // MARK: - CrownSpinProvider.createEntry

    func testCreateEntryWithEmptyDefaultsFallsBack() {
        let provider = CrownSpinProvider()
        let entry = provider.createEntry()
        XCTAssertEqual(entry.totalHaptics, 0)
        XCTAssertEqual(entry.currentPattern, "Clicks")
        XCTAssertEqual(entry.patternIcon, "hand.tap")
        XCTAssertEqual(entry.currentItemNumber, 0)
        XCTAssertEqual(entry.numberSystem, .decimal)
    }

    func testCreateEntryReadsFromSharedDefaults() {
        sharedDefaults?.set(123, forKey: "stats.totalHaptics")
        sharedDefaults?.set("heavy", forKey: "selectedHapticPattern")

        let provider = CrownSpinProvider()
        let entry = provider.createEntry()
        XCTAssertEqual(entry.totalHaptics, 123)
        XCTAssertEqual(entry.currentPattern, "Heavy")
        XCTAssertEqual(entry.patternIcon, "hammer")
    }

    func testCreateEntryWithInvalidPatternFallsBackToClicks() {
        sharedDefaults?.set("invalidPattern", forKey: "selectedHapticPattern")

        let provider = CrownSpinProvider()
        let entry = provider.createEntry()
        XCTAssertEqual(entry.currentPattern, "Clicks")
        XCTAssertEqual(entry.patternIcon, "hand.tap")
    }

    func testCreateEntryReadsCorrectPatternForEachCase() {
        let provider = CrownSpinProvider()
        for pattern in HapticPattern.allCases {
            sharedDefaults?.set(pattern.rawValue, forKey: "selectedHapticPattern")
            let entry = provider.createEntry()
            XCTAssertEqual(entry.currentPattern, pattern.displayName,
                "Pattern mismatch for \(pattern.rawValue)")
            XCTAssertEqual(entry.patternIcon, pattern.icon,
                "Icon mismatch for \(pattern.rawValue)")
        }
    }

    func testCreateEntryDateIsApproximatelyNow() {
        let before = Date()
        let provider = CrownSpinProvider()
        let entry = provider.createEntry()
        let after = Date()
        XCTAssertGreaterThanOrEqual(entry.date, before)
        XCTAssertLessThanOrEqual(entry.date, after)
    }

    func testCreateEntryWithLargeHapticCount() {
        sharedDefaults?.set(1_500_000, forKey: "stats.totalHaptics")

        let provider = CrownSpinProvider()
        let entry = provider.createEntry()
        XCTAssertEqual(entry.totalHaptics, 1_500_000)
    }

    // MARK: - Widget Kind

    func testComplicationKind() {
        let complication = CrownSpinComplication()
        XCTAssertEqual(complication.kind, "CrownSpinComplication")
    }

    // MARK: - Shared Defaults Key Names

    func testSharedDefaultsUsesCorrectTotalHapticsKey() {
        sharedDefaults?.set(999, forKey: "stats.totalHaptics")
        let provider = CrownSpinProvider()
        let entry = provider.createEntry()
        XCTAssertEqual(entry.totalHaptics, 999)
    }

    func testSharedDefaultsUsesCorrectPatternKey() {
        sharedDefaults?.set("wave", forKey: "selectedHapticPattern")
        let provider = CrownSpinProvider()
        let entry = provider.createEntry()
        XCTAssertEqual(entry.currentPattern, "Wave")
        XCTAssertEqual(entry.patternIcon, "water.waves")
    }

    func testSharedDefaultsUsesCorrectNumberSystemKey() {
        sharedDefaults?.set("base26", forKey: "numberSystem")
        let provider = CrownSpinProvider()
        let entry = provider.createEntry()
        XCTAssertEqual(entry.numberSystem, .base26)
    }

    // MARK: - Entry Conforms to TimelineEntry

    func testEntryConformsToTimelineEntry() {
        let entry = CrownSpinEntry(
            date: Date(),
            totalHaptics: 0,
            currentPattern: "Clicks",
            patternIcon: "hand.tap",
            currentItemNumber: 0,
            numberSystem: .decimal
        )
        // TimelineEntry requires a `date` property
        let _: Date = entry.date
        XCTAssertNotNil(entry.date)
    }

    // MARK: - Current Item Number

    func testCreateEntryReadsLegacyMirrorBeforeAppMigration() {
        sharedDefaults?.set(99, forKey: "currentItemNumber")

        let provider = CrownSpinProvider()
        let entry = provider.createEntry()
        XCTAssertEqual(entry.currentItemNumber, 99)
        XCTAssertNil(sharedDefaults?.object(forKey: CrownPositionKeys.saved))
    }

    func testCreateEntryWithNegativeItemNumber() {
        sharedDefaults?.set(-42, forKey: CrownPositionKeys.saved)

        let provider = CrownSpinProvider()
        let entry = provider.createEntry()
        XCTAssertEqual(entry.currentItemNumber, -42)
    }

    func testCreateEntryPrefersMigratedZeroOverTheLegacyMirror() {
        sharedDefaults?.set(900, forKey: "currentItemNumber")
        sharedDefaults?.set(0, forKey: CrownPositionKeys.saved)
        XCTAssertEqual(CrownSpinProvider().createEntry().currentItemNumber, 0)
    }

    func testCreateEntryItemNumberDefaultsToZeroWhenAbsent() {
        let provider = CrownSpinProvider()
        let entry = provider.createEntry()
        XCTAssertEqual(entry.currentItemNumber, 0)
    }

    // MARK: - formatItemNumber

    func testFormatItemNumberSmallValues() {
        XCTAssertEqual(formatItemNumber(0), "0")
        XCTAssertEqual(formatItemNumber(42), "42")
        XCTAssertEqual(formatItemNumber(9999), "9999")
        XCTAssertEqual(formatItemNumber(-5), "-5")
        XCTAssertEqual(formatItemNumber(-9999), "-9999")
    }

    func testFormatItemNumberThousands() {
        XCTAssertEqual(formatItemNumber(10_000), "10.0K")
        XCTAssertEqual(formatItemNumber(12_500), "12.5K")
        XCTAssertEqual(formatItemNumber(999_949), "999.9K")
        XCTAssertEqual(formatItemNumber(-50_000), "-50.0K")
    }

    func testFormatItemNumberMillions() {
        XCTAssertEqual(formatItemNumber(999_950), "1.0M")
        XCTAssertEqual(formatItemNumber(1_000_000), "1.0M")
        XCTAssertEqual(formatItemNumber(1_500_000), "1.5M")
        XCTAssertEqual(formatItemNumber(25_000_000), "25.0M")
        XCTAssertEqual(formatItemNumber(-2_000_000), "-2.0M")
    }

    func testFormatItemNumberBillionsAndTrillions() {
        XCTAssertEqual(formatItemNumber(999_949_999), "999.9M")
        XCTAssertEqual(formatItemNumber(999_950_000), "1.0B")
        XCTAssertEqual(formatItemNumber(1_000_000_000), "1.0B")
        XCTAssertEqual(formatItemNumber(100_000_000_000), "100.0B")
        XCTAssertEqual(formatItemNumber(-5_000_000_000), "-5.0B")
        XCTAssertEqual(formatItemNumber(999_950_000_000), "1.0T")
        XCTAssertEqual(formatItemNumber(1_000_000_000_000), "1.0T")
        XCTAssertEqual(formatItemNumber(-1_000_000_000_000), "-1.0T")
    }

    func testFormatItemNumberExtremeBounds() {
        // Int.min must not crash (abs(Int.min) would overflow)
        let result = formatItemNumber(Int.min)
        XCTAssertFalse(result.isEmpty)
        // Int.max should format without crashing
        let maxResult = formatItemNumber(Int.max)
        XCTAssertFalse(maxResult.isEmpty)
    }

    // MARK: - formatHapticNumber

    func testFormatHapticNumberSmallValues() {
        XCTAssertEqual(formatHapticNumber(0), "0")
        XCTAssertEqual(formatHapticNumber(999), "999")
    }

    func testFormatHapticNumberThousands() {
        XCTAssertEqual(formatHapticNumber(1_000), "1.0K")
        XCTAssertEqual(formatHapticNumber(1_500), "1.5K")
        XCTAssertEqual(formatHapticNumber(999_949), "999.9K")
    }

    func testFormatHapticNumberBoundary() {
        // 999,950+ should show as M, not "1000.0K"
        XCTAssertEqual(formatHapticNumber(999_950), "1.0M")
        XCTAssertEqual(formatHapticNumber(999_999), "1.0M")
    }

    func testFormatHapticNumberMillions() {
        XCTAssertEqual(formatHapticNumber(1_000_000), "1.0M")
        XCTAssertEqual(formatHapticNumber(1_500_000), "1.5M")
        XCTAssertEqual(formatHapticNumber(25_000_000), "25.0M")
    }

    func testFormatHapticNumberBillionsAndTrillions() {
        XCTAssertEqual(formatHapticNumber(999_950_000), "1.0B")
        XCTAssertEqual(formatHapticNumber(1_000_000_000), "1.0B")
        XCTAssertEqual(formatHapticNumber(100_000_000_000), "100.0B")
        XCTAssertEqual(formatHapticNumber(999_950_000_000), "1.0T")
        XCTAssertEqual(formatHapticNumber(1_000_000_000_000), "1.0T")
    }
}
