import XCTest
import WatchKit

/// Copied into an isolated test project. The measured app uses an ordinary Release build.
final class SystemScrollBatteryUITests: XCTestCase {
    struct Request: Decodable {
        let runID: String
        let condition: String
        let mode: String
        let seconds: Double
        let delta: Double
        let velocity: Double
        let period: Double
        let screenValidation: String?
    }

    @MainActor
    func testComparison() throws {
        continueAfterFailure = false
        guard let text = ProcessInfo.processInfo.environment["CROWN_SYSTEM_SCROLL_REQUEST"],
              let data = Data(base64Encoded: text) else {
            throw XCTSkip("Supply a workload with system-scroll-compare.py.")
        }
        let request = try JSONDecoder().decode(Request.self, from: data)
        executionTimeAllowance = request.seconds + 180
        let watch = WKInterfaceDevice.current()
        watch.isBatteryMonitoringEnabled = true
        defer { watch.isBatteryMonitoringEnabled = false }
        let app = XCUIApplication()
        app.launchEnvironment = [:]
        app.launch()
        try selectClicks(in: app)
        var foreground = app
        if request.condition == "app-list" {
            foreground = try enterList(from: app)
            // Leave a margin above the upper reversal so overscroll cannot return to Favorites.
            XCUIDevice.shared.rotateDigitalCrown(delta: CGFloat(-request.delta - 0.5),
                velocity: XCUIGestureVelocity(rawValue: CGFloat(request.velocity)))
        }
        attach("before-" + request.condition)
        print("SYSTEM_SCROLL_READY condition=\(request.condition) mode=\(request.mode)")
        Thread.sleep(forTimeInterval: request.mode == "manual" ? 30 : 2)
        let initialScreen = request.screenValidation == nil || comparisonScreenPresent(foreground, condition: request.condition)
        XCTAssertTrue(initialScreen, "Measured screen was not ready")
        let start = ProcessInfo.processInfo.systemUptime
        var samples: [[String: Any]] = []
        var gestures: [[String: Any]] = []
        var issues: [String] = []
        func sample() {
            let elapsed = ProcessInfo.processInfo.systemUptime - start
            let level = watch.batteryLevel
            let state = watch.batteryState.rawValue
            let thermal = ProcessInfo.processInfo.thermalState.rawValue
            let active = foreground.state == .runningForeground
            let verified = samples.isEmpty ? initialScreen :
                (request.screenValidation == nil || comparisonScreenPresent(foreground, condition: request.condition))
            samples.append(["elapsedSeconds": elapsed, "batteryLevel": level,
                            "batteryState": state, "thermalState": thermal,
                            "foreground": active, "screenVerified": verified])
            if level < 0 || level > 1 { issues.append("Unknown battery reading") }
            if state != WKInterfaceDeviceBatteryState.unplugged.rawValue { issues.append("Watch is not unplugged") }
            if thermal != 0 { issues.append("Non-nominal thermal state") }
            if !active { issues.append("Foreground interrupted") }
            if !verified { issues.append("Measured screen changed") }
        }
        sample()
        print("SYSTEM_SCROLL_STARTED condition=\(request.condition)")
        var nextSample = 30.0
        var nextImage = 60.0
        let count = Int(floor(request.seconds / request.period))
        while issues.isEmpty && ProcessInfo.processInfo.systemUptime - start < request.seconds {
            if request.mode == "automated" {
                if gestures.count >= count { break }
                let planned = Double(gestures.count) * request.period
                waitUntil(start + planned)
                let actual = ProcessInfo.processInfo.systemUptime - start
                let delta = gestures.count.isMultiple(of: 2) ? request.delta : -request.delta
                XCUIDevice.shared.rotateDigitalCrown(delta: CGFloat(delta),
                    velocity: XCUIGestureVelocity(rawValue: CGFloat(request.velocity)))
                let end = ProcessInfo.processInfo.systemUptime - start
                gestures.append(["plannedSeconds": planned, "startedSeconds": actual,
                                 "endedSeconds": end, "delta": delta])
                if actual - planned > 1 { issues.append("Crown schedule started late") }
                if end > planned + request.period { issues.append("Crown command exceeded its slot") }
            } else {
                Thread.sleep(forTimeInterval: min(1, max(0, start + request.seconds - ProcessInfo.processInfo.systemUptime)))
            }
            let elapsed = ProcessInfo.processInfo.systemUptime - start
            // Long blocking rotations can straddle a 30-second sampling boundary.
            // Sample at every completed long command rather than allowing a 50+ second gap.
            if elapsed >= nextSample || (request.mode == "automated" && request.period >= 20) {
                sample()
                nextSample = elapsed + 30
                print("SYSTEM_SCROLL_PROGRESS condition=\(request.condition) seconds=\(Int(elapsed)) battery=\(watch.batteryLevel) commands=\(gestures.count)")
            }
            if elapsed >= nextImage {
                attach("during-\(request.condition)-\(Int(elapsed))")
                nextImage += 60
            }
        }
        if issues.isEmpty { waitUntil(start + request.seconds) }
        sample()
        let elapsed = samples.last?["elapsedSeconds"] as? Double ?? 0
        attach("after-" + request.condition)
        let report: [String: Any] = ["runID": request.runID, "condition": request.condition,
            "mode": request.mode, "durationSeconds": request.seconds, "elapsedSeconds": elapsed,
            "delta": request.delta, "velocity": request.velocity, "period": request.period,
            "batteryReader": "WKInterfaceDevice-in-UI-test-runner", "systemVersion": watch.systemVersion,
            "screenValidation": request.screenValidation ?? "legacy-foreground-only",
            "samples": samples, "gestures": gestures, "issues": issues]
        let result = try JSONSerialization.data(withJSONObject: report, options: [.sortedKeys])
        print("SYSTEM_SCROLL_REPORT " + result.base64EncodedString())
        let attachment = XCTAttachment(data: result, uniformTypeIdentifier: "public.json")
        attachment.name = "system-scroll-report"
        attachment.lifetime = .keepAlways
        add(attachment)
        app.activate()
        XCTAssertTrue(issues.isEmpty, issues.joined(separator: "; "))
    }

    @MainActor
    func testRestoreGrid() throws {
        continueAfterFailure = false
        executionTimeAllowance = 180
        let app = XCUIApplication()
        app.launchEnvironment = [:]
        app.launch()
        let system = try openAllApps(from: app)
        // No change is needed when the launcher already uses Grid View.
        if system.buttons["List View"].exists { app.activate(); return }
        let grid = system.buttons["Grid View"]
        for _ in 0..<12 {
            if grid.exists && grid.isHittable { break }
            XCUIDevice.shared.rotateDigitalCrown(delta: -5, velocity: XCUIGestureVelocity(rawValue: 2.5))
        }
        XCTAssertTrue(grid.exists && grid.isHittable, "Could not reach Grid View restore control")
        tapRotated(grid, in: system)
        XCTAssertTrue(system.buttons["List View"].waitForExistence(timeout: 8),
                      "Launcher did not confirm Grid View after the restoration tap")
        attach("restored-grid")
        app.activate()
    }

    @MainActor
    private func openAllApps(from app: XCUIApplication) throws -> XCUIApplication {
        let system = XCUIApplication(bundleIdentifier: "com.apple.Carousel")
        for _ in 0..<4 {
            XCUIDevice.shared.press(.home)
            Thread.sleep(forTimeInterval: 1)
            let all = system.otherElements["All Apps"]
            if all.waitForExistence(timeout: 2) && all.isHittable {
                if all.frame.width < system.frame.width * 0.5 { tapRotated(all, in: system) }
                return system
            }
        }
        XCTFail("Could not open the native All Apps launcher")
        return system
    }

    @MainActor
    private func comparisonScreenPresent(_ app: XCUIApplication, condition: String) -> Bool {
        // A notification can cover the measured screen while its underlying rows still exist.
        let system = XCUIApplication(bundleIdentifier: "com.apple.Carousel")
        if system.alerts.firstMatch.exists || system.buttons["Dismiss"].exists { return false }
        if condition == "app-list" {
            let bounds = app.frame
            for row in app.icons.allElementsBoundByIndex {
                let frame = row.frame
                if frame.width > bounds.width * 0.65,
                   bounds.contains(CGPoint(x: frame.midX, y: frame.midY)), row.isHittable {
                    return true
                }
            }
            return false
        }
        // The effect label fades out while the Crown is moving. Keep checking
        // the ordinary main screen without requiring that idle-only control.
        let marker = app.descendants(matching: .any).matching(identifier: "Numbers").firstMatch
        return marker.exists && marker.isHittable && !app.images["Six-Sided Die Showing One Pip"].exists
    }

    @MainActor
    private func selectClicks(in app: XCUIApplication) throws {
        for _ in 0..<16 {
            // Verify the fixed effect before warm-up, while the idle label is visible.
            let marker = app.staticTexts["Clicks"]
            if marker.exists && marker.isHittable && !app.images["Six-Sided Die Showing One Pip"].exists { return }
            // Normal app behavior: a single tap on the number advances the effect.
            app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
            Thread.sleep(forTimeInterval: 0.6)
        }
        XCTFail("Could not select the fixed Clicks effect through the ordinary app UI")
    }

    @MainActor
    private func enterList(from app: XCUIApplication) throws -> XCUIApplication {
        let system = try openAllApps(from: app)
        let list = system.buttons["List View"]
        if list.exists {
            for _ in 0..<8 {
                if list.isHittable { break }
                XCUIDevice.shared.rotateDigitalCrown(delta: -2, velocity: XCUIGestureVelocity(rawValue: 1))
            }
            XCTAssertTrue(list.isHittable, "Could not reach List View control")
            tapRotated(list, in: system)
        }
        let row = system.icons.firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 5) && row.frame.width > system.frame.width * 0.65,
                      "Native alphabetical list did not open")
        return system
    }

    @MainActor
    private func tapRotated(_ element: XCUIElement, in app: XCUIApplication) {
        let frame = element.frame, bounds = app.frame
        var x = (frame.midX - bounds.minX) / bounds.width
        var y = (frame.midY - bounds.minY) / bounds.height
        // Physical probe confirmed the tap-coordinate inversion on this left-Crown Ultra 2.
        if WKInterfaceDevice.current().crownOrientation == .left { x = 1 - x; y = 1 - y }
        app.coordinate(withNormalizedOffset: CGVector(dx: x, dy: y)).tap()
    }

    private func waitUntil(_ deadline: Double) {
        let remaining = deadline - ProcessInfo.processInfo.systemUptime
        if remaining > 0 { Thread.sleep(forTimeInterval: remaining) }
    }

    @MainActor
    private func attach(_ name: String) {
        let attachment = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }
}
