// Concatenate after SystemScrollBatteryUITests.swift in an isolated diagnostic build.
#if ENERGY_TESTING
extension SystemScrollBatteryUITests {
    @MainActor
    func testMatchedRangeProbe() throws {
        continueAfterFailure = false
        executionTimeAllowance = 600
        let app = XCUIApplication()
        app.launchEnvironment = [:]
        app.launch()
        let candidates: [(delta: Double, velocity: Double)] = [(2, 0.5), (4, 0.25), (4, 0.2)]
        var native: [[String: Any]] = []
        let encoded = ProcessInfo.processInfo.environment["CROWN_SYSTEM_SCROLL_REQUEST"] ?? ""
        let requestData = Data(base64Encoded: encoded) ?? Data()
        let options = (try? JSONSerialization.jsonObject(with: requestData)) as? [String: Any]
        let nativeCandidates = options?["appOnly"] as? Bool == true ? [] : candidates
        for (index, candidate) in nativeCandidates.enumerated() {
            app.activate()
            let system = try enterList(from: app)
            // Earlier calibration showed that overscrolling the top enters Favorites.
            // Return there deliberately, then explicitly reopen All Apps instead of measuring there.
            XCUIDevice.shared.rotateDigitalCrown(delta: 12, velocity: XCUIGestureVelocity(rawValue: 3))
            let all = system.otherElements["All Apps"]
            XCTAssertTrue(all.exists && all.isHittable && all.frame.width < system.frame.width * 0.5)
            tapRotated(all, in: system)
            XCTAssertTrue(comparisonScreenPresent(system, condition: "app-list"))
            XCUIDevice.shared.rotateDigitalCrown(delta: CGFloat(-candidate.delta - 0.5),
                velocity: XCUIGestureVelocity(rawValue: 0.5))
            attach("range-\(index)-before")
            var commands: [[String: Any]] = []
            for delta in [candidate.delta, -candidate.delta] {
                let start = ProcessInfo.processInfo.systemUptime
                XCUIDevice.shared.rotateDigitalCrown(delta: CGFloat(delta),
                    velocity: XCUIGestureVelocity(rawValue: CGFloat(candidate.velocity)))
                let end = ProcessInfo.processInfo.systemUptime
                let present = comparisonScreenPresent(system, condition: "app-list")
                commands.append(["delta": delta, "startUptime": start, "endUptime": end,
                                 "callSeconds": end - start, "listPresent": present])
                attach("range-\(index)-\(delta)")
                let snapshot = XCTAttachment(string: system.debugDescription)
                snapshot.name = "range-\(index)-\(delta)-accessibility"
                snapshot.lifetime = .keepAlways
                add(snapshot)
            }
            native.append(["index": index, "delta": candidate.delta, "velocity": candidate.velocity,
                           "nominalSeconds": candidate.delta / candidate.velocity, "commands": commands])
            print("SYSTEM_SCROLL_PROBE native range=\(index) nominal=\(candidate.delta / candidate.velocity) verified=\(commands.map { $0["listPresent"]! })")
        }
        app.terminate()
        var configuration = EnergyTestConfiguration()
        configuration.scenario = .crown
        configuration.durationSeconds = 150
        configuration.pattern = "clicks"
        configuration.captureHapticTiming = true
        configuration.label = "matched-range-calibration"
        configuration.conditions = "Ultra 2; diagnostic range/speed calibration; not battery evidence"
        let runID = UUID().uuidString
        let request = EnergyAutomationRequest(runID: runID, configuration: configuration,
                                             crownDelta: 2, crownVelocity: 0.5, pauseSeconds: 0)
        app.launchEnvironment[EnergyAutomationRequest.environmentKey] = try JSONEncoder().encode(request).base64EncodedString()
        app.launch()
        let status = app.staticTexts["energy-automation-status"]
        XCTAssertTrue(status.waitForExistence(timeout: 20))
        let running = XCTNSPredicateExpectation(predicate: NSPredicate(format: "label == 'running'"), object: status)
        XCTAssertEqual(XCTWaiter.wait(for: [running], timeout: 20), .completed)
        var application: [[String: Any]] = []
        for (index, candidate) in candidates.enumerated() {
            var commands: [[String: Any]] = []
            for delta in [candidate.delta, -candidate.delta] {
                let start = ProcessInfo.processInfo.systemUptime
                XCUIDevice.shared.rotateDigitalCrown(delta: CGFloat(delta),
                    velocity: XCUIGestureVelocity(rawValue: CGFloat(candidate.velocity)))
                let end = ProcessInfo.processInfo.systemUptime
                commands.append(["delta": delta, "startUptime": start, "endUptime": end,
                                 "callSeconds": end - start])
            }
            application.append(["index": index, "delta": candidate.delta, "velocity": candidate.velocity,
                                "nominalSeconds": candidate.delta / candidate.velocity, "commands": commands])
            print("SYSTEM_SCROLL_PROBE app range=\(index) nominal=\(candidate.delta / candidate.velocity) seconds=\(commands.map { $0["callSeconds"]! })")
        }
        let data = try JSONSerialization.data(withJSONObject: ["runID": runID, "purpose": "calibration-only",
                 "native": native, "app": application], options: [.sortedKeys])
        print("SYSTEM_SCROLL_REPORT " + data.base64EncodedString())
        let attachment = XCTAttachment(data: data, uniformTypeIdentifier: "public.json")
        attachment.name = "matched-range-calibration"; attachment.lifetime = .keepAlways; add(attachment)
        let finished = XCTNSPredicateExpectation(predicate: NSPredicate(format: "label != 'running'"), object: status)
        XCTAssertEqual(XCTWaiter.wait(for: [finished], timeout: 180), .completed)
        XCTAssertEqual(status.label, "completed")
    }

    @MainActor
    func testLongRotationProbe() throws {
        continueAfterFailure = false
        executionTimeAllowance = 600
        let watch = WKInterfaceDevice.current()
        watch.isBatteryMonitoringEnabled = true
        defer { watch.isBatteryMonitoringEnabled = false }
        let app = XCUIApplication()
        app.launchEnvironment = [:]
        app.launch()
        let system = try enterList(from: app)
        let candidates: [(delta: Double, velocity: Double)] = [
            (0.5, 0.5), (2, 0.5), (5, 0.5), (10, 0.5), (2, 0.1)
        ]
        var native: [[String: Any]] = []
        for (index, candidate) in candidates.enumerated() {
            // Reset to the alphabetical beginning before each independent candidate.
            XCUIDevice.shared.rotateDigitalCrown(delta: 12, velocity: XCUIGestureVelocity(rawValue: 3))
            attach("native-\(index)-before")
            let before = system.debugDescription
            var commands: [[String: Any]] = []
            for delta in [-candidate.delta, candidate.delta] {
                let start = ProcessInfo.processInfo.systemUptime
                XCUIDevice.shared.rotateDigitalCrown(delta: CGFloat(delta),
                    velocity: XCUIGestureVelocity(rawValue: CGFloat(candidate.velocity)))
                let end = ProcessInfo.processInfo.systemUptime
                commands.append(["delta": delta, "startUptime": start, "endUptime": end,
                                 "callSeconds": end - start])
                attach("native-\(index)-\(delta)")
                let snapshot = XCTAttachment(string: system.debugDescription)
                snapshot.name = "native-\(index)-\(delta)-accessibility"
                snapshot.lifetime = .keepAlways
                add(snapshot)
            }
            native.append(["index": index, "delta": candidate.delta, "velocity": candidate.velocity,
                           "nominalSeconds": candidate.delta / candidate.velocity,
                           "commands": commands, "beforeAccessibility": before])
            print("SYSTEM_SCROLL_PROBE native candidate=\(index) nominal=\(candidate.delta / candidate.velocity) seconds=\(commands.map { $0["callSeconds"]! })")
        }
        app.terminate()
        var configuration = EnergyTestConfiguration()
        configuration.scenario = .crown
        configuration.durationSeconds = 240
        configuration.pattern = "clicks"
        configuration.captureHapticTiming = true
        configuration.label = "long-rotation-calibration"
        configuration.conditions = "Ultra 2; diagnostic Crown calibration; not a battery comparison"
        let runID = UUID().uuidString
        let request = EnergyAutomationRequest(runID: runID, configuration: configuration,
                                             crownDelta: 2, crownVelocity: 0.5, pauseSeconds: 0)
        app.launchEnvironment[EnergyAutomationRequest.environmentKey] =
            try JSONEncoder().encode(request).base64EncodedString()
        app.launch()
        let status = app.staticTexts["energy-automation-status"]
        XCTAssertTrue(status.waitForExistence(timeout: 20))
        let running = XCTNSPredicateExpectation(predicate: NSPredicate(format: "label == 'running'"), object: status)
        XCTAssertEqual(XCTWaiter.wait(for: [running], timeout: 20), .completed)
        var application: [[String: Any]] = []
        for (index, candidate) in candidates.enumerated() {
            var commands: [[String: Any]] = []
            // No UI queries or screenshots between these two calls: measure the real reversal gap.
            for delta in [candidate.delta, -candidate.delta] {
                let start = ProcessInfo.processInfo.systemUptime
                let startWall = Date().timeIntervalSince1970
                XCUIDevice.shared.rotateDigitalCrown(delta: CGFloat(delta),
                    velocity: XCUIGestureVelocity(rawValue: CGFloat(candidate.velocity)))
                let end = ProcessInfo.processInfo.systemUptime
                commands.append(["delta": delta, "startUptime": start, "endUptime": end,
                                 "startWallSeconds": startWall, "callSeconds": end - start])
            }
            application.append(["index": index, "delta": candidate.delta, "velocity": candidate.velocity,
                                "nominalSeconds": candidate.delta / candidate.velocity, "commands": commands])
            print("SYSTEM_SCROLL_PROBE app candidate=\(index) nominal=\(candidate.delta / candidate.velocity) seconds=\(commands.map { $0["callSeconds"]! })")
        }
        let result: [String: Any] = ["runID": runID, "purpose": "calibration-only",
                                   "native": native, "app": application,
                                   "batteryLevel": watch.batteryLevel,
                                   "batteryState": watch.batteryState.rawValue,
                                   "thermalState": ProcessInfo.processInfo.thermalState.rawValue]
        let data = try JSONSerialization.data(withJSONObject: result, options: [.sortedKeys])
        print("SYSTEM_SCROLL_REPORT " + data.base64EncodedString())
        let attachment = XCTAttachment(data: data, uniformTypeIdentifier: "public.json")
        attachment.name = "long-rotation-calibration"
        attachment.lifetime = .keepAlways
        add(attachment)
        let finished = XCTNSPredicateExpectation(predicate: NSPredicate(format: "label != 'running'"), object: status)
        XCTAssertEqual(XCTWaiter.wait(for: [finished], timeout: 260), .completed)
        XCTAssertEqual(status.label, "completed")
        attach("calibration-app-completed")
    }
}
#endif
