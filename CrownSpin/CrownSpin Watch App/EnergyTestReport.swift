#if ENERGY_TESTING
import Foundation

enum EnergyTestScenario: String, Codable, CaseIterable, Identifiable {
    case idle
    case manual
    case crown
    case crownWithoutHaptics = "crown-no-haptics"
    case replay
    case replayWithoutHaptics = "replay-no-haptics"

    var id: String { rawValue }
    var title: String {
        switch self {
        case .idle: return "App idle"
        case .manual: return "Real Crown capture"
        case .crown: return "Automated Crown + haptics"
        case .crownWithoutHaptics: return "Automated Crown, no haptics"
        case .replay: return "Scroll replay + haptics"
        case .replayWithoutHaptics: return "Scroll replay, no haptics"
        }
    }
    var usesReplay: Bool { self == .replay || self == .replayWithoutHaptics }
    var usesAutomatedCrown: Bool { self == .crown || self == .crownWithoutHaptics }
    static var menuCases: [Self] { [.idle, .manual, .replay, .replayWithoutHaptics] }
}

/// Shared contract between the app and its UI test runner. No transport runs during measurement.
struct EnergyAutomationRequest: Codable {
    let runID: String
    let configuration: EnergyTestConfiguration
    let crownDelta: Double
    let crownVelocity: Double
    let pauseSeconds: Double

    var validationIssues: [String] {
        var issues = configuration.validationIssues
        if UUID(uuidString: runID) == nil { issues.append("Invalid automation run ID.") }
        if configuration.scenario != .idle && !configuration.scenario.usesAutomatedCrown && !configuration.scenario.usesReplay {
            issues.append("Automation requires a Crown, replay, or idle scenario.")
        }
        if !crownDelta.isFinite || abs(crownDelta) < 0.05 || abs(crownDelta) > 5 ||
            !crownVelocity.isFinite || !(0.1...5).contains(crownVelocity) ||
            !pauseSeconds.isFinite || !(0...10).contains(pauseSeconds) {
            issues.append("Invalid automated Crown workload.")
        }
        return issues
    }

    static let environmentKey = "CROWN_ENERGY_REQUEST"
    var usesNeutralWake: Bool { configuration.scenario == .idle || configuration.scenario.usesReplay }
    static func fromEnvironment() throws -> Self? {
        guard let encoded = ProcessInfo.processInfo.environment[environmentKey] else { return nil }
        guard let data = Data(base64Encoded: encoded) else {
            throw NSError(domain: "EnergyAutomation", code: 1)
        }
        let request = try JSONDecoder().decode(Self.self, from: data)
        guard request.validationIssues.isEmpty else {
            throw NSError(domain: "EnergyAutomation", code: 2,
                          userInfo: [NSLocalizedDescriptionKey: request.validationIssues.joined(separator: " ")])
        }
        return request
    }

    var metadata: [String: String] {
        if usesNeutralWake {
            return ["inputDriver": configuration.scenario == .idle ? "app-idle-v1" : "app-scroll-replay-v1",
                    "displayPolicy": "UI-testing-neutral-wake-taps",
                    "wakeTapIntervalSeconds": "20", "statusPollIntervalSeconds": "5"]
        }
        return ["inputDriver": "xcuitest-crown-v1",
                "crownInputProfile": "delta=\(crownDelta);velocity=\(crownVelocity);pause=\(pauseSeconds)",
                "displayPolicy": "watchOS-under-UI-testing"]
    }
}

struct EnergyTestConfiguration: Codable {
    var scenario: EnergyTestScenario = .manual
    var durationSeconds: Double = 600
    var stepsPerSecond: Double = 5
    var pattern: String = "clicks"
    var label: String = "baseline"
    // Record battery health, display settings, connectivity, and the particular Watch here.
    var conditions: String = ""
    // Optional for compatibility with reports made before request timing was recorded.
    var captureHapticTiming: Bool? = nil
    // Profiling-only CPU and wall-time counters; excluded from battery comparisons.
    var captureRuntimeProfile: Bool? = nil

    var validationIssues: [String] {
        var result: [String] = []
        if !durationSeconds.isFinite || !(15...3600).contains(durationSeconds) {
            result.append("Duration must be between 15 and 3600 seconds.")
        }
        if !stepsPerSecond.isFinite || !(1...10).contains(stepsPerSecond) {
            result.append("Replay rate must be between 1 and 10 steps per second.")
        }
        if label.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            result.append("A build label is required.")
        }
        if conditions.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            result.append("Record the Watch and test conditions before starting.")
        }
        return result
    }
}

/// A request timestamp is not a measurement of haptic motor activation or delivery.
struct HapticRequestTiming: Codable {
    let callbackElapsedSeconds: Double
    let requestElapsedSeconds: Double
    let oldPosition: Int?
    let newPosition: Int
    let pattern: String
    let requestsHaptic: Bool
}

/// Launch configuration for a user-operated Crown comparison; no synthetic input or UI test runner.
struct HapticComparisonRequest: Codable {
    let trialLabel: String
    let pattern: String
    let durationSeconds: Double

    static let environmentKey = "CROWN_HAPTIC_COMPARISON"

    static func fromEnvironment() throws -> Self? {
        guard let value = ProcessInfo.processInfo.environment[environmentKey] else { return nil }
        guard let data = Data(base64Encoded: value) else {
            throw NSError(domain: "HapticComparison", code: 1)
        }
        let request = try JSONDecoder().decode(Self.self, from: data)
        guard !request.trialLabel.isEmpty, request.trialLabel.count <= 40,
              request.pattern != "random", request.durationSeconds.isFinite,
              (15...60).contains(request.durationSeconds) else {
            throw NSError(domain: "HapticComparison", code: 2)
        }
        return request
    }
}

struct EnergyTestSample: Codable {
    let elapsedSeconds: Double
    let batteryLevel: Double?
    let powerState: String
    let scenePhase: String
    let luminanceReduced: Bool
    let thermalState: Int
    let scrollEvents: Int
    // Counts calls requested by the app, not haptics physically delivered by watchOS.
    let hapticRequests: Int
    let replaySteps: Int
}

struct EnergyWorkTiming: Codable {
    var calls = 0
    var totalWallSeconds: Double = 0
    var maximumWallSeconds: Double = 0
}

struct EnergyRuntimeSample: Codable {
    let elapsedSeconds: Double
    let userCPUSeconds: Double
    let systemCPUSeconds: Double
    let contentViewBodyUpdates: Int
    let work: [String: EnergyWorkTiming]
}

struct EnergyRuntimeProfile: Codable {
    let samples: [EnergyRuntimeSample]

    var validationIssues: [String] {
        guard samples.count >= 2 else { return ["Missing runtime profile endpoints."] }
        if samples.contains(where: {
            !$0.elapsedSeconds.isFinite || $0.elapsedSeconds < 0 ||
            !$0.userCPUSeconds.isFinite || $0.userCPUSeconds < 0 ||
            !$0.systemCPUSeconds.isFinite || $0.systemCPUSeconds < 0 ||
            $0.contentViewBodyUpdates < 0 || $0.work.values.contains(where: {
                $0.calls < 0 || !$0.totalWallSeconds.isFinite || $0.totalWallSeconds < 0 ||
                !$0.maximumWallSeconds.isFinite || $0.maximumWallSeconds < 0 ||
                $0.maximumWallSeconds > $0.totalWallSeconds + 0.000001
            })
        }) { return ["Invalid runtime profile counters."] }
        if zip(samples, samples.dropFirst()).contains(where: { previous, next in
            next.elapsedSeconds <= previous.elapsedSeconds ||
            next.userCPUSeconds < previous.userCPUSeconds ||
            next.systemCPUSeconds < previous.systemCPUSeconds ||
            next.contentViewBodyUpdates < previous.contentViewBodyUpdates ||
            previous.work.contains(where: { key, timing in
                guard let updated = next.work[key] else { return true }
                return updated.calls < timing.calls || updated.totalWallSeconds < timing.totalWallSeconds
            })
        }) { return ["Non-monotonic runtime profile counters."] }
        return []
    }
}

struct EnergyTestReport: Codable {
    let schemaVersion: Int
    let runID: String
    let startedAt: Date
    let finishedAt: Date
    let configuration: EnergyTestConfiguration
    let metadata: [String: String]
    let status: String
    var issues: [String]
    let samples: [EnergyTestSample]
    var hapticTimings: [HapticRequestTiming]? = nil
    var runtimeProfile: EnergyRuntimeProfile? = nil

    var elapsedSeconds: Double { samples.last?.elapsedSeconds ?? 0 }

    var batteryDropPercentagePoints: Double? {
        guard let first = samples.first?.batteryLevel,
              let last = samples.last?.batteryLevel,
              first.isFinite, last.isFinite,
              (0...1).contains(first), (0...1).contains(last) else { return nil }
        return (first - last) * 100
    }

    var validationIssues: [String] {
        var result = issues + configuration.validationIssues
        if configuration.captureRuntimeProfile == true {
            if let profile = runtimeProfile {
                result += profile.validationIssues
                if profile.samples.count != samples.count ||
                    abs((profile.samples.last?.elapsedSeconds ?? 0) - elapsedSeconds) > 0.1 {
                    result.append("Runtime profile did not cover the measured workload.")
                }
            } else { result.append("Missing runtime profile.") }
        }
        let requiresActiveDisplay = configuration.scenario != .idle || metadata["inputDriver"] == "app-idle-v1"
        if schemaVersion != 1 { result.append("Unsupported report version.") }
        if metadata["simulator"] != "false" { result.append("Not a physical Watch battery measurement.") }
        if status != "completed" { result.append("Run did not complete.") }
        guard samples.count >= 2 else { return result + ["Missing battery endpoints."] }
        if samples.contains(where: {
            guard let level = $0.batteryLevel else { return true }
            return !level.isFinite || !(0...1).contains(level)
        }) { result.append("Battery level unavailable.") }
        if samples.contains(where: { $0.powerState != "unplugged" }) {
            result.append("Charging or unknown battery state observed.")
        }
        if samples.contains(where: { $0.thermalState >= 2 }) {
            result.append("Serious or critical thermal state observed.")
        }
        let tolerance = max(2, configuration.durationSeconds * 0.02)
        if abs(elapsedSeconds - configuration.durationSeconds) > tolerance {
            result.append("Measured duration differs from requested duration.")
        }
        for (previous, sample) in zip(samples, samples.dropFirst()) {
            if !sample.elapsedSeconds.isFinite || sample.elapsedSeconds <= previous.elapsedSeconds {
                result.append("Non-monotonic samples.")
                break
            }
            if requiresActiveDisplay && sample.elapsedSeconds - previous.elapsedSeconds > 60 {
                result.append("Sampling was interrupted.")
                break
            }
        }
        if requiresActiveDisplay && samples.contains(where: {
            $0.scenePhase != "active" || $0.luminanceReduced
        }) { result.append("Active-use run lost the foreground or entered Always On.") }
        if let drop = batteryDropPercentagePoints, drop < -0.001 {
            result.append("Battery level increased during the run.")
        }
        if let last = samples.last {
            switch configuration.scenario {
            case .idle:
                if last.scrollEvents != 0 || last.hapticRequests != 0 || last.replaySteps != 0 {
                    result.append("Input or haptics occurred during the idle control.")
                }
            case .manual:
                if last.scrollEvents == 0 || last.hapticRequests == 0 {
                    result.append("No real Crown activity was captured.")
                }
            case .crown, .crownWithoutHaptics:
                if metadata["inputDriver"] != "xcuitest-crown-v1" || last.replaySteps != 0 {
                    result.append("Automated Crown run has an invalid input driver.")
                }
                if last.scrollEvents == 0 { result.append("No automated Crown activity was captured.") }
                if configuration.scenario == .crownWithoutHaptics && last.hapticRequests != 0 {
                    result.append("Haptics occurred in the haptics-disabled control.")
                }
                if configuration.scenario == .crown && last.hapticRequests != last.scrollEvents {
                    result.append("Haptic requests did not match scroll events.")
                }
            case .replay, .replayWithoutHaptics:
                let expected = configuration.durationSeconds * configuration.stepsPerSecond
                if Double(last.replaySteps) < expected * 0.9 {
                    result.append("Replay did not maintain the requested rate.")
                }
                if metadata["inputDriver"] == "app-scroll-replay-v1" &&
                    (abs(Double(last.replaySteps) - expected) > max(2, expected * 0.02) ||
                     abs(last.scrollEvents - last.replaySteps) > 2) {
                    result.append("Automated replay did not maintain the fixed scroll rate.")
                }
                if last.replaySteps == 0 || abs(Double(last.scrollEvents - last.replaySteps)) > max(2, Double(last.replaySteps) * 0.1) {
                    result.append("Scroll events did not match replay steps.")
                }
                if configuration.scenario == .replayWithoutHaptics && last.hapticRequests != 0 {
                    result.append("Haptics occurred in the haptics-disabled control.")
                }
                if configuration.scenario == .replay && last.hapticRequests != last.scrollEvents {
                    result.append("Haptic requests did not match scroll events.")
                }
            }
            if configuration.captureHapticTiming == true {
                if let timings = hapticTimings {
                    if timings.count != last.scrollEvents ||
                        timings.filter({ $0.requestsHaptic }).count != last.hapticRequests {
                        result.append("Haptic timing records do not match activity counters.")
                    }
                    if timings.contains(where: {
                        !$0.callbackElapsedSeconds.isFinite || !$0.requestElapsedSeconds.isFinite ||
                        $0.callbackElapsedSeconds < 0 ||
                        $0.requestElapsedSeconds < $0.callbackElapsedSeconds ||
                        $0.requestElapsedSeconds > elapsedSeconds ||
                        $0.pattern != configuration.pattern
                    }) || zip(timings, timings.dropFirst()).contains(where: {
                        $0.1.callbackElapsedSeconds < $0.0.requestElapsedSeconds
                    }) {
                        result.append("Invalid haptic request timestamps or effects.")
                    }
                } else {
                    result.append("Missing haptic request timing records.")
                }
            }
        }
        var unique: [String] = []
        for issue in result where !unique.contains(issue) { unique.append(issue) }
        return unique
    }
}
#endif
