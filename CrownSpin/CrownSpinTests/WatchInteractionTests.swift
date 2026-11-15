import XCTest

final class WatchInteractionTests: XCTestCase {
    func testMenuSelectionWaitsForDismissalAndRejectsCompetingRoutes() {
        var presentation = WatchPresentation()
        XCTAssertTrue(presentation.present(.menu))
        presentation.selectMenuDestination(.sheet(.effects))
        XCTAssertNil(presentation.sheet)
        XCTAssertFalse(presentation.present(.guide))
        presentation.selectMenuDestination(.sheet(.statistics))
        presentation.dismissSheet()
        presentation.sheetDidDismiss()
        XCTAssertEqual(presentation.sheet, .effects)
    }

    func testResetConfirmationFollowsMenuDismissal() {
        var presentation = WatchPresentation()
        presentation.present(.menu)
        presentation.selectMenuDestination(.resetCounter)
        XCTAssertFalse(presentation.isConfirmingReset)
        presentation.sheetDidDismiss()
        XCTAssertTrue(presentation.isConfirmingReset)
        XCTAssertFalse(presentation.present(.effects))
        presentation.dismissReset()
        XCTAssertTrue(presentation.present(.effects))
        presentation.dismissSheet()
        XCTAssertFalse(presentation.present(.menu))
        presentation.sheetDidDismiss()
        XCTAssertTrue(presentation.present(.menu))
    }

    func testStartupAndRecenteringDoNotProduceScrollInput() {
        var state = CrownScrollState(center: 500)
        XCTAssertNil(state.receivedPosition(499))
        state.initialPositionDidSettle()
        XCTAssertNil(state.receivedPosition(499))
        XCTAssertEqual(state.receivedPosition(99), 99)
        state.beganScrolling()
        state.recentered(at: 500)
        XCTAssertNil(state.receivedPosition(500))
        XCTAssertTrue(state.isScrolling)
        XCTAssertEqual(state.receivedPosition(501), 501)
    }

    func testIdleAndDisappearanceEndTheCurrentBurst() {
        var state = CrownScrollState(center: 500)
        state.initialPositionDidSettle()
        state.beganScrolling()
        state.becameIdle()
        XCTAssertEqual(state.phase, .idle)
        state.beganScrolling()
        state.leftScreen()
        state.becameIdle()
        XCTAssertEqual(state.phase, .positioning)
        XCTAssertNil(state.receivedPosition(499))
    }
}
