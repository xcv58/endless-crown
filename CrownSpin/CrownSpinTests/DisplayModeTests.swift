import XCTest

final class DisplayModeTests: XCTestCase {
    private var defaults: UserDefaults!
    private var suiteName: String!

    override func setUp() {
        super.setUp()
        suiteName = "CrownSpinDisplayModeTests." + UUID().uuidString
        defaults = UserDefaults(suiteName: suiteName)!
    }

    override func tearDown() {
        defaults.removePersistentDomain(forName: suiteName)
        defaults = nil
        super.tearDown()
    }

    func testNewInstallationDefaultsToAmbient() {
        XCTAssertEqual(DisplayMode.load(from: defaults), .ambient)
        XCTAssertEqual(defaults.string(forKey: DisplayMode.preferenceKey), "ambient")
    }

    func testLegacyAmbientPreferenceMigrates() {
        defaults.set(true, forKey: DisplayMode.legacyAmbientKey)
        XCTAssertEqual(DisplayMode.load(from: defaults), .ambient)
    }

    func testExplicitLegacyHighContrastPreferenceMigrates() {
        defaults.set(false, forKey: DisplayMode.legacyAmbientKey)
        XCTAssertEqual(DisplayMode.load(from: defaults), .highContrast)
        XCTAssertEqual(defaults.string(forKey: DisplayMode.preferenceKey), "highContrast")
    }

    func testNewPreferenceTakesPrecedenceOverLegacyPreference() {
        defaults.set(false, forKey: DisplayMode.legacyAmbientKey)
        defaults.set("hapticsOnly", forKey: DisplayMode.preferenceKey)
        XCTAssertEqual(DisplayMode.load(from: defaults), .hapticsOnly)
    }

    func testInvalidPreferenceFallsBackToLegacyPreference() {
        defaults.set("futureMode", forKey: DisplayMode.preferenceKey)
        defaults.set(false, forKey: DisplayMode.legacyAmbientKey)
        XCTAssertEqual(DisplayMode.load(from: defaults), .highContrast)
    }

    func testEachModeSurvivesSavingAndReloading() {
        for mode in DisplayMode.allCases {
            mode.save(to: defaults)
            XCTAssertEqual(DisplayMode.load(from: defaults), mode)
        }
    }

    func testOlderBuildFallbackUsesAmbientForHapticsOnly() {
        DisplayMode.hapticsOnly.save(to: defaults)
        XCTAssertTrue(defaults.bool(forKey: DisplayMode.legacyAmbientKey))
        DisplayMode.highContrast.save(to: defaults)
        XCTAssertFalse(defaults.bool(forKey: DisplayMode.legacyAmbientKey))
    }

    func testHapticsOnlyStartsBlackAfterReload() {
        DisplayMode.hapticsOnly.save(to: defaults)
        let state = DisplayModeState(mode: DisplayMode.load(from: defaults))
        XCTAssertTrue(state.showsBlackDisplay)
    }

    func testTapRevealsControlsWithoutChangingSavedMode() {
        var state = DisplayModeState(mode: .hapticsOnly)
        state.revealControls()
        XCTAssertFalse(state.showsBlackDisplay)
        XCTAssertEqual(state.mode, .hapticsOnly)
    }

    func testNextScrollHidesRevealedControls() {
        var state = DisplayModeState(mode: .hapticsOnly)
        state.revealControls()
        state.didScroll()
        XCTAssertTrue(state.showsBlackDisplay)
    }

    func testOtherModesNeverGoBlackAfterScrolling() {
        for mode in [DisplayMode.ambient, .highContrast] {
            var state = DisplayModeState(mode: mode)
            state.didScroll()
            XCTAssertFalse(state.showsBlackDisplay)
        }
    }

    func testSelectingAnotherModeClearsTemporaryRevealState() {
        var state = DisplayModeState(mode: .hapticsOnly)
        state.revealControls()
        state.select(.ambient)
        XCTAssertFalse(state.showsBlackDisplay)
        state.select(.hapticsOnly)
        XCTAssertTrue(state.showsBlackDisplay)
    }
}
