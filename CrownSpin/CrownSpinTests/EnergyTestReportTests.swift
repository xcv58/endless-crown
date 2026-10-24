#if ENERGY_TESTING
import XCTest

final class EnergyTestReportTests: XCTestCase {
    func testRuntimeProfilesRejectMissingAndDecreasingCounters() {
        let first = EnergyRuntimeSample(elapsedSeconds: 0, userCPUSeconds: 0, systemCPUSeconds: 0,
                                        contentViewBodyUpdates: 0, work: [:])
        let last = EnergyRuntimeSample(elapsedSeconds: 600, userCPUSeconds: 1, systemCPUSeconds: 0.2,
                                       contentViewBodyUpdates: 1200,
                                       work: ["scrollHandler": EnergyWorkTiming(calls: 1199, totalWallSeconds: 0.5,
                                                                              maximumWallSeconds: 0.01)])
        XCTAssertTrue(EnergyRuntimeProfile(samples: [first, last]).validationIssues.isEmpty)
        XCTAssertFalse(EnergyRuntimeProfile(samples: [last, first]).validationIssues.isEmpty)
        let invalid = EnergyRuntimeSample(elapsedSeconds: 600, userCPUSeconds: -1, systemCPUSeconds: 0,
                                          contentViewBodyUpdates: 0, work: [:])
        XCTAssertFalse(EnergyRuntimeProfile(samples: [first, invalid]).validationIssues.isEmpty)
        let base = report([sample(0), sample(600)])
        var config = base.configuration
        config.captureRuntimeProfile = true
        var result = EnergyTestReport(schemaVersion: 1, runID: base.runID, startedAt: base.startedAt,
                                     finishedAt: base.finishedAt, configuration: config, metadata: base.metadata,
                                     status: "completed", issues: [], samples: base.samples)
        XCTAssertTrue(result.validationIssues.contains("Missing runtime profile."))
        result.runtimeProfile = EnergyRuntimeProfile(samples: [first, last])
        XCTAssertTrue(result.validationIssues.isEmpty)
        result.runtimeProfile = EnergyRuntimeProfile(samples: [first])
        XCTAssertFalse(result.validationIssues.isEmpty)
    }

    func testHapticTimingRequiresCompleteOrderedRequestRecords() {
        let base = report([sample(0), sample(30, scrolls: 2, haptics: 2)], scenario: .manual)
        var configuration = base.configuration
        configuration.durationSeconds = 30
        configuration.captureHapticTiming = true
        var result = EnergyTestReport(schemaVersion: base.schemaVersion, runID: base.runID,
                                     startedAt: base.startedAt, finishedAt: base.finishedAt,
                                     configuration: configuration, metadata: base.metadata,
                                     status: base.status, issues: [], samples: base.samples)
        XCTAssertTrue(result.validationIssues.contains("Missing haptic request timing records."))
        let first = HapticRequestTiming(callbackElapsedSeconds: 2, requestElapsedSeconds: 2.001,
                                       oldPosition: 500, newPosition: 501, pattern: "clicks", requestsHaptic: true)
        let second = HapticRequestTiming(callbackElapsedSeconds: 2.05, requestElapsedSeconds: 2.052,
                                        oldPosition: 501, newPosition: 503, pattern: "clicks", requestsHaptic: true)
        result.hapticTimings = [first, second]
        XCTAssertTrue(result.validationIssues.isEmpty)
        result.hapticTimings = [first]
        XCTAssertTrue(result.validationIssues.contains("Haptic timing records do not match activity counters."))
        result.hapticTimings = [second, first]
        XCTAssertTrue(result.validationIssues.contains("Invalid haptic request timestamps or effects."))
    }

    func testReportsWithoutTimingFieldsRemainDecodable() throws {
        let original = report([sample(0), sample(600)])
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        var object = try XCTUnwrap(JSONSerialization.jsonObject(with: encoder.encode(original)) as? [String: Any])
        object.removeValue(forKey: "hapticTimings")
        var configuration = try XCTUnwrap(object["configuration"] as? [String: Any])
        configuration.removeValue(forKey: "captureHapticTiming")
        object["configuration"] = configuration
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let decoded = try decoder.decode(EnergyTestReport.self, from: JSONSerialization.data(withJSONObject: object))
        XCTAssertNil(decoded.hapticTimings)
        XCTAssertNil(decoded.configuration.captureHapticTiming)
        XCTAssertTrue(decoded.validationIssues.isEmpty)
    }

    private func sample(_ elapsed: Double, level: Double? = 0.8, power: String = "unplugged",
                        phase: String = "active", reduced: Bool = false, scrolls: Int = 0,
                        haptics: Int = 0, replay: Int = 0) -> EnergyTestSample {
        EnergyTestSample(elapsedSeconds: elapsed, batteryLevel: level, powerState: power,
                         scenePhase: phase, luminanceReduced: reduced, thermalState: 0,
                         scrollEvents: scrolls, hapticRequests: haptics, replaySteps: replay)
    }

    private func report(_ samples: [EnergyTestSample], scenario: EnergyTestScenario = .idle,
                        simulator: String = "false", status: String = "completed") -> EnergyTestReport {
        var configuration = EnergyTestConfiguration()
        configuration.scenario = scenario
        configuration.durationSeconds = 600
        configuration.conditions = "My Ultra 2; health 90%; AOD on; brightness medium; WiFi/BT on"
        return EnergyTestReport(schemaVersion: 1, runID: "test", startedAt: Date(), finishedAt: Date(),
                                configuration: configuration, metadata: ["simulator": simulator],
                                status: status, issues: [], samples: samples)
    }

    func testPhysicalBatteryDropUsesPercentagePoints() {
        let result = report([sample(0), sample(600, level: 0.77)])
        XCTAssertEqual(result.batteryDropPercentagePoints ?? -1, 3, accuracy: 0.0001)
        XCTAssertTrue(result.validationIssues.isEmpty)
    }

    func testSimulatorIsNeverBatteryEvidence() {
        let result = report([sample(0), sample(600, level: 0.77)], simulator: "true")
        XCTAssertTrue(result.validationIssues.contains("Not a physical Watch battery measurement."))
    }

    func testChargingAndUnknownEndpointsAreFlagged() {
        let result = report([sample(0, level: nil, power: "unknown"), sample(600, power: "charging")])
        XCTAssertNil(result.batteryDropPercentagePoints)
        XCTAssertTrue(result.validationIssues.contains("Battery level unavailable."))
        XCTAssertTrue(result.validationIssues.contains("Charging or unknown battery state observed."))
    }

    func testInterruptedReplayAndAlwaysOnAreFlagged() {
        let result = report([sample(0), sample(20, phase: "inactive", reduced: true)],
                            scenario: .replay, status: "interrupted")
        XCTAssertTrue(result.validationIssues.contains("Run did not complete."))
        XCTAssertTrue(result.validationIssues.contains("Active-use run lost the foreground or entered Always On."))
    }

    func testNoHapticsControlPreservesWorkloadCounts() {
        let samples = [sample(0)] + stride(from: 30, through: 600, by: 30).map {
            sample(Double($0), level: 0.78, scrolls: $0 * 5, replay: $0 * 5)
        }
        XCTAssertTrue(report(samples, scenario: .replayWithoutHaptics).validationIssues.isEmpty)
        let bad = report([sample(0), sample(600, scrolls: 3000, haptics: 1, replay: 3000)],
                         scenario: .replayWithoutHaptics)
        XCTAssertTrue(bad.validationIssues.contains("Haptics occurred in the haptics-disabled control."))
    }

    func testMissedReplayAndExtraScrollEventsAreFlagged() {
        let result = report([sample(0), sample(600, scrolls: 1000, haptics: 1000, replay: 500)], scenario: .replay)
        XCTAssertTrue(result.validationIssues.contains("Replay did not maintain the requested rate."))
        XCTAssertTrue(result.validationIssues.contains("Scroll events did not match replay steps."))
    }

    func testIdleAllowsWristDownButRejectsInputAndDurationOverrun() {
        let result = report([sample(0), sample(600, phase: "inactive", reduced: true)])
        XCTAssertTrue(result.validationIssues.isEmpty)
        let bad = report([sample(0), sample(1000, scrolls: 1)])
        XCTAssertTrue(bad.validationIssues.contains("Input or haptics occurred during the idle control."))
        XCTAssertTrue(bad.validationIssues.contains("Measured duration differs from requested duration."))
    }

    func testReportsRoundTripWithoutInventingMissingBatteryData() throws {
        let original = report([sample(0, level: nil), sample(600)])
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let decoded = try decoder.decode(EnergyTestReport.self, from: encoder.encode(original))
        XCTAssertNil(decoded.samples.first?.batteryLevel)
        XCTAssertEqual(decoded.configuration.conditions, original.configuration.conditions)
    }

    func testAutomationRejectsInvalidWorkloadAndRunIDs() {
        var configuration = EnergyTestConfiguration()
        configuration.scenario = .crown
        configuration.conditions = "fixture only"
        let valid = EnergyAutomationRequest(runID: UUID().uuidString, configuration: configuration,
                                             crownDelta: -0.5, crownVelocity: 1, pauseSeconds: 0.25)
        XCTAssertTrue(valid.validationIssues.isEmpty)
        let invalid = EnergyAutomationRequest(runID: "not-a-uuid", configuration: configuration,
                                               crownDelta: 0, crownVelocity: .nan, pauseSeconds: -1)
        XCTAssertEqual(invalid.validationIssues.count, 2)
    }

    func testAutomatedCrownRequiresDriverAndActualInput() {
        let samples = [sample(0)] + stride(from: 30, through: 600, by: 30).map {
            sample(Double($0), scrolls: $0, haptics: $0)
        }
        var result = report(samples, scenario: .crown)
        result = EnergyTestReport(schemaVersion: result.schemaVersion, runID: result.runID,
            startedAt: result.startedAt, finishedAt: result.finishedAt, configuration: result.configuration,
            metadata: ["simulator": "false", "inputDriver": "xcuitest-crown-v1"],
            status: result.status, issues: [], samples: result.samples)
        XCTAssertTrue(result.validationIssues.isEmpty)
        XCTAssertTrue(report(samples, scenario: .crown).validationIssues.contains(
            "Automated Crown run has an invalid input driver."))
    }

    func testReplayAutomationHasItsOwnDriverAndWakePolicy() {
        var configuration = EnergyTestConfiguration()
        configuration.scenario = .replay
        configuration.stepsPerSecond = 2
        configuration.conditions = "fixture only"
        let request = EnergyAutomationRequest(runID: UUID().uuidString, configuration: configuration,
                                              crownDelta: -0.5, crownVelocity: 1, pauseSeconds: 0.25)
        XCTAssertTrue(request.validationIssues.isEmpty)
        XCTAssertEqual(request.metadata["inputDriver"], "app-scroll-replay-v1")
        XCTAssertEqual(request.metadata["displayPolicy"], "UI-testing-neutral-wake-taps")
        XCTAssertNil(request.metadata["crownInputProfile"])
        configuration.scenario = .manual
        XCTAssertFalse(EnergyAutomationRequest(runID: UUID().uuidString, configuration: configuration,
            crownDelta: -0.5, crownVelocity: 1, pauseSeconds: 0.25).validationIssues.isEmpty)
    }

    func testFixedReplayRejectsWrongCadenceAndUnexpectedScrolls() {
        func automatedReport(rate: Double, extraScrolls: Int = 0) -> EnergyTestReport {
            var configuration = EnergyTestConfiguration()
            configuration.scenario = .replay
            configuration.stepsPerSecond = 2
            configuration.conditions = "fixture only"
            let samples = stride(from: 0, through: 600, by: 30).map { seconds in
                let steps = Int(Double(seconds) * rate)
                let scrolls = steps + (seconds == 600 ? extraScrolls : 0)
                return sample(Double(seconds), scrolls: scrolls, haptics: scrolls, replay: steps)
            }
            return EnergyTestReport(schemaVersion: 1, runID: "fixture", startedAt: Date(), finishedAt: Date(),
                configuration: configuration, metadata: ["simulator": "false", "inputDriver": "app-scroll-replay-v1"],
                status: "completed", issues: [], samples: samples)
        }
        XCTAssertTrue(automatedReport(rate: 2).validationIssues.isEmpty)
        for invalid in [automatedReport(rate: 1.9), automatedReport(rate: 2.1),
                        automatedReport(rate: 2, extraScrolls: 3)] {
            XCTAssertTrue(invalid.validationIssues.contains("Automated replay did not maintain the fixed scroll rate."))
        }
    }

    func testAutomatedIdleMatchesReplayWakeAndPollingPolicy() {
        var configuration = EnergyTestConfiguration()
        configuration.conditions = "fixture only"
        configuration.scenario = .replayWithoutHaptics
        let replay = EnergyAutomationRequest(runID: UUID().uuidString, configuration: configuration,
            crownDelta: -0.5, crownVelocity: 1, pauseSeconds: 0.25)
        configuration.scenario = .idle
        let idle = EnergyAutomationRequest(runID: UUID().uuidString, configuration: configuration,
            crownDelta: -0.5, crownVelocity: 1, pauseSeconds: 0.25)
        XCTAssertTrue(idle.validationIssues.isEmpty)
        XCTAssertTrue(idle.usesNeutralWake)
        XCTAssertTrue(replay.usesNeutralWake)
        XCTAssertEqual(idle.metadata["inputDriver"], "app-idle-v1")
        XCTAssertNil(idle.metadata["crownInputProfile"])
        for key in ["displayPolicy", "wakeTapIntervalSeconds", "statusPollIntervalSeconds"] {
            XCTAssertEqual(idle.metadata[key], replay.metadata[key])
        }
    }

    func testAutomatedIdleRequiresActiveSamplesAndZeroWork() {
        func automatedIdle(_ samples: [EnergyTestSample]) -> EnergyTestReport {
            let result = report(samples)
            return EnergyTestReport(schemaVersion: 1, runID: result.runID,
                startedAt: result.startedAt, finishedAt: result.finishedAt, configuration: result.configuration,
                metadata: ["simulator": "false", "inputDriver": "app-idle-v1"],
                status: "completed", issues: [], samples: samples)
        }
        let samples = stride(from: 0, through: 600, by: 30).map { sample(Double($0)) }
        XCTAssertTrue(automatedIdle(samples).validationIssues.isEmpty)
        var inactive = samples
        inactive[5] = sample(150, phase: "inactive", reduced: true)
        XCTAssertTrue(automatedIdle(inactive).validationIssues.contains(
            "Active-use run lost the foreground or entered Always On."))
        XCTAssertTrue(automatedIdle([sample(0), sample(600)]).validationIssues.contains("Sampling was interrupted."))
        var unexpected = samples
        unexpected[unexpected.count - 1] = sample(600, replay: 1)
        XCTAssertTrue(automatedIdle(unexpected).validationIssues.contains("Input or haptics occurred during the idle control."))
    }
}
#endif
