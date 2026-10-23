import XCTest

/// Runs the actual menu-timer method extracted into a macOS state holder by `verify`.
/// These tests do not exercise Watch UI rendering or physical haptic delivery.
final class ScrollOverheadTimerTests: XCTestCase {
    func testContinuedInputReusesTimerAndMovesThreeSecondDeadline() throws {
        let menu = MenuTimerProbe()
        menu.revealMenuButton()
        let first = try XCTUnwrap(menu.menuButtonTimer)
        let originalDeadline = first.fireDate
        Thread.sleep(forTimeInterval: 0.01)
        menu.revealMenuButton()
        XCTAssertTrue(first === menu.menuButtonTimer)
        XCTAssertTrue(first.isValid)
        XCTAssertGreaterThan(first.fireDate, originalDeadline)
        XCTAssertEqual(first.fireDate.timeIntervalSinceNow, 3, accuracy: 0.1)
    }

    func testHiddenMenuAndOpenMenuCancelAutoHide() throws {
        let menu = MenuTimerProbe()
        menu.revealMenuButton()
        let first = try XCTUnwrap(menu.menuButtonTimer)
        menu.isMenuButtonHidden = true
        menu.revealMenuButton()
        XCTAssertFalse(first.isValid)
        XCTAssertFalse(menu.showMenuButton)

        menu.isMenuButtonHidden = false
        menu.revealMenuButton()
        let second = try XCTUnwrap(menu.menuButtonTimer)
        menu.showMenu = true
        menu.revealMenuButton()
        XCTAssertFalse(second.isValid)
        XCTAssertTrue(menu.showMenuButton)
    }

    func testCancelledTimerIsReplacedWhenInputResumes() throws {
        let menu = MenuTimerProbe()
        menu.revealMenuButton()
        let first = try XCTUnwrap(menu.menuButtonTimer)
        first.invalidate()
        menu.revealMenuButton()
        let second = try XCTUnwrap(menu.menuButtonTimer)
        XCTAssertFalse(first === second)
        XCTAssertTrue(second.isValid)
        XCTAssertEqual(second.fireDate.timeIntervalSinceNow, 3, accuracy: 0.1)
    }

    func testHideCallbackRespectsAnOpenMenu() throws {
        let menu = MenuTimerProbe()
        menu.revealMenuButton()
        try XCTUnwrap(menu.menuButtonTimer).fire()
        RunLoop.main.run(until: Date(timeIntervalSinceNow: 0.02))
        XCTAssertFalse(menu.showMenuButton)

        menu.revealMenuButton()
        menu.showMenu = true
        try XCTUnwrap(menu.menuButtonTimer).fire()
        RunLoop.main.run(until: Date(timeIntervalSinceNow: 0.02))
        XCTAssertTrue(menu.showMenuButton)
    }
}
