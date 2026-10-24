import XCTest

/// Drives Crown input or supervises timed app replay. The app measures and saves its battery report.
final class EnergyAutomationUITests: XCTestCase {
    @MainActor
    func testBatteryRun() throws {
        continueAfterFailure = false
        guard let request = try EnergyAutomationRequest.fromEnvironment() else {
            XCTFail("Run this test with energy-tests.py automate; no workload was supplied.")
            return
        }
        executionTimeAllowance = request.configuration.durationSeconds + 120
        let app = XCUIApplication()
        app.launchEnvironment[EnergyAutomationRequest.environmentKey] =
            ProcessInfo.processInfo.environment[EnergyAutomationRequest.environmentKey]
        app.launch()
        let status = app.staticTexts["energy-automation-status"]
        XCTAssertTrue(status.waitForExistence(timeout: 20), "Diagnostic automation status is missing.")
        let running = XCTNSPredicateExpectation(predicate: NSPredicate(format: "label == 'running'"), object: status)
        XCTAssertEqual(XCTWaiter.wait(for: [running], timeout: 15), .completed,
                       "Battery measurement could not start: \(status.label)")

        let started = ProcessInfo.processInfo.systemUptime
        var rotations = 0
        var wakeTaps = 0
        var nextWake = started + 20
        let usesNeutralWake = request.usesNeutralWake
        let wake = app.buttons["energy-automation-wake"]
        if usesNeutralWake { XCTAssertTrue(wake.exists, "Neutral wake control is missing.") }
        // Stop commands before the measured deadline; finishing/saving remains the app's responsibility.
        let lastCommand = started + request.configuration.durationSeconds -
            (request.configuration.scenario.usesAutomatedCrown ? abs(request.crownDelta) / request.crownVelocity + 1 : 0)
        while ProcessInfo.processInfo.systemUptime < lastCommand {
            if status.label != "running" { break }
            if request.configuration.scenario.usesAutomatedCrown {
                XCUIDevice.shared.rotateDigitalCrown(delta: CGFloat(request.crownDelta),
                                                     velocity: XCUIGestureVelocity(rawValue: CGFloat(request.crownVelocity)))
                rotations += 1
            } else if usesNeutralWake && ProcessInfo.processInfo.systemUptime >= nextWake &&
                        ProcessInfo.processInfo.systemUptime < lastCommand - 5 {
                wake.tap()
                wakeTaps += 1
                let received = XCTNSPredicateExpectation(
                    predicate: NSPredicate(format: "value == %@", String(wakeTaps)), object: wake)
                XCTAssertEqual(XCTWaiter.wait(for: [received], timeout: 2), .completed,
                               "Wake touch did not reach the neutral diagnostic control.")
                nextWake = ProcessInfo.processInfo.systemUptime + 20
            }
            Thread.sleep(forTimeInterval: usesNeutralWake ? 5 : max(0.1, request.pauseSeconds))
        }
        let remaining = started + request.configuration.durationSeconds - ProcessInfo.processInfo.systemUptime
        // Do not wait out the deadline after an interrupted/failed measurement.
        if status.label == "running" {
            if remaining > 0 { Thread.sleep(forTimeInterval: remaining) }
        }
        let finished = XCTNSPredicateExpectation(predicate: NSPredicate(format: "label != 'running'"), object: status)
        XCTAssertEqual(XCTWaiter.wait(for: [finished], timeout: 15), .completed)
        XCTAssertEqual(status.label, "completed", "Invalid battery run: \(status.label)")
        print("ENERGY_DRIVER run=\(request.runID) crownCommands=\(rotations) wakeTaps=\(wakeTaps)")
        // Keep the app installed and leave the completed report available to CoreDevice.
    }
}
