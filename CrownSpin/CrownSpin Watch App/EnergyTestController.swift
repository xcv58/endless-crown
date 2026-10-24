#if ENERGY_TESTING
import SwiftUI
import WatchKit
import Darwin

/// Low-frequency battery logging, with an optional synthetic workload. No keep-awake session.
@MainActor
final class EnergyTestController: ObservableObject {
    @Published private(set) var isRunning = false
    @Published private(set) var lastReport: EnergyTestReport?
    @Published private(set) var message = ""
    @Published private(set) var automationWakeTaps = 0

    var automationStatus: String {
        if isRunning { return "running" }
        if let report = lastReport {
            return report.issues.isEmpty && message == "Saved battery report." ? "completed" :
                "failed: " + report.issues.joined(separator: " ") + " " + message
        }
        return message.isEmpty ? "waiting" : "failed: " + message
    }

    private var configuration = EnergyTestConfiguration()
    private var metadata: [String: String] = [:]
    private var samples: [EnergyTestSample] = []
    private var issues: [String] = []
    private var startUptime: TimeInterval = 0
    private var startedAt = Date()
    private var runID = ""
    private var scrollEvents = 0
    private var hapticRequests = 0
    private var replaySteps = 0
    private var phase: ScenePhase = .active
    private var luminanceReduced = false
    private var sampleTimer: Timer?
    private var replayTimer: Timer?
    private var finishTimer: Timer?
    private var previousBatteryMonitoring = false
    private var monitoringPrepared = false
    // Unpublished buffers: collecting a request must not invalidate the view being measured.
    private var hapticTimings: [HapticRequestTiming] = []
    private var pendingScrollCallback: (elapsed: TimeInterval, oldPosition: Int?, newPosition: Int)?
    private var runtimeSamples: [EnergyRuntimeSample] = []
    private var runtimeCPUStart: (user: Double, system: Double)?
    private var bodyUpdates = 0
    private var workTimings: [String: EnergyWorkTiming] = [:]

    func recordBodyUpdate() {
        if isRunning, configuration.captureRuntimeProfile == true { bodyUpdates += 1 }
    }

    func beginWork() -> TimeInterval? {
        isRunning && configuration.captureRuntimeProfile == true ? ProcessInfo.processInfo.systemUptime : nil
    }

    func endWork(_ name: String, since start: TimeInterval?) {
        guard let start else { return }
        let duration = ProcessInfo.processInfo.systemUptime - start
        var timing = workTimings[name] ?? EnergyWorkTiming()
        timing.calls += 1
        timing.totalWallSeconds += duration
        timing.maximumWallSeconds = max(timing.maximumWallSeconds, duration)
        workTimings[name] = timing
    }

    private static func cpuUsage() -> (user: Double, system: Double)? {
        var usage = rusage()
        guard getrusage(RUSAGE_SELF, &usage) == 0 else { return nil }
        return (Double(usage.ru_utime.tv_sec) + Double(usage.ru_utime.tv_usec) / 1_000_000,
                Double(usage.ru_stime.tv_sec) + Double(usage.ru_stime.tv_usec) / 1_000_000)
    }

    func prepareBatteryMonitoring() {
        guard !monitoringPrepared else { return }
        let device = WKInterfaceDevice.current()
        previousBatteryMonitoring = device.isBatteryMonitoringEnabled
        device.isBatteryMonitoringEnabled = true
        monitoringPrepared = true
    }

    func cancelPreparation() {
        guard !isRunning, monitoringPrepared else { return }
        WKInterfaceDevice.current().isBatteryMonitoringEnabled = previousBatteryMonitoring
        monitoringPrepared = false
    }

    func start(_ configuration: EnergyTestConfiguration, context: [String: String], runID requestedRunID: String? = nil,
               replayStep: @escaping () -> Void) {
        defer { recordStartDiagnostic(event: "start-attempt") }
        guard !isRunning else { return }
        guard configuration.validationIssues.isEmpty else {
            message = configuration.validationIssues.joined(separator: "\n")
            return
        }
        guard phase == .active, !luminanceReduced else {
            message = "Raise your wrist and keep the app active before starting."
            return
        }
        let device = WKInterfaceDevice.current()
        prepareBatteryMonitoring()
        if !Self.isSimulator && (device.batteryState != .unplugged || !(0...1).contains(device.batteryLevel)) {
            message = "Unplug the Watch and wait for a battery reading, then retry."
            return
        }
        if context["inputDriver"] != nil && (device.batteryLevel < 0.2 || ProcessInfo.processInfo.thermalState.rawValue >= 2) {
            message = "Automation stopped: charge must be at least 20% and the Watch must be cool."
            return
        }
        // The first reading may still be unknown; preserve it as unknown rather than inventing a value.
        self.configuration = configuration
        self.metadata = context.merging([
            "watchOS": device.systemVersion,
            "hardwareModel": Self.hardwareModel,
            "appVersion": Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "unknown",
            "appBuild": Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "unknown",
            "sourceRevision": Bundle.main.infoDictionary?["EnergySourceRevision"] as? String ?? "unknown",
            "sourceFingerprint": Bundle.main.infoDictionary?["EnergySourceFingerprint"] as? String ?? "unknown",
            "builtSDK": Bundle.main.infoDictionary?["DTSDKName"] as? String ?? "unknown",
            "xcodeBuild": Bundle.main.infoDictionary?["DTXcodeBuild"] as? String ?? "unknown",
            "diagnosticVersion": "1",
            "simulator": Self.isSimulator ? "true" : "false"
        ]) { _, new in new }
        samples = []
        issues = []
        scrollEvents = 0
        hapticRequests = 0
        replaySteps = 0
        hapticTimings = []
        if configuration.captureHapticTiming == true { hapticTimings.reserveCapacity(4096) }
        pendingScrollCallback = nil
        runtimeSamples = []
        workTimings = [:]
        bodyUpdates = 0
        runtimeCPUStart = configuration.captureRuntimeProfile == true ? Self.cpuUsage() : nil
        if configuration.captureRuntimeProfile == true {
            metadata["diagnosticPurpose"] = "runtime-profile-v1"
            if runtimeCPUStart == nil { issues.append("CPU accounting unavailable.") }
        }
        automationWakeTaps = 0
        startedAt = Date()
        startUptime = ProcessInfo.processInfo.systemUptime
        runID = requestedRunID ?? UUID().uuidString
        lastReport = nil
        message = "Running \(configuration.scenario.title)."
        isRunning = true
        captureSample()

        sampleTimer = timer(interval: 30, repeats: true) { [weak self] in
            self?.captureSample()
        }
        finishTimer = timer(interval: configuration.durationSeconds, repeats: false) { [weak self] in
            self?.finish(status: "completed")
        }
        if configuration.scenario.usesReplay {
            replayTimer = timer(interval: 1 / configuration.stepsPerSecond, repeats: true) { [weak self] in
                guard let self, self.isRunning else { return }
                if self.elapsed >= self.configuration.durationSeconds {
                    self.finish(status: "completed")
                    return
                }
                guard self.phase == .active, !self.luminanceReduced else {
                    self.finish(status: "interrupted")
                    return
                }
                self.replaySteps += 1
                replayStep()
            }
        }
    }

    /// Explicit troubleshooting only; these writes never run in comparison captures.
    func recordStartDiagnostic(event: String) {
        guard ProcessInfo.processInfo.environment["CROWN_START_DIAGNOSTICS"] == "1" else { return }
        let device = WKInterfaceDevice.current()
        let snapshot: [String: String] = [
            "event": event,
            "recordedAt": ISO8601DateFormatter().string(from: Date()),
            "message": message,
            "isRunning": String(isRunning),
            "phase": String(describing: phase),
            "luminanceReduced": String(luminanceReduced),
            "batteryLevel": String(device.batteryLevel),
            "powerState": Self.powerState(device.batteryState),
            "thermalState": String(ProcessInfo.processInfo.thermalState.rawValue),
            "batteryMonitoringEnabled": String(device.isBatteryMonitoringEnabled),
            "sourceFingerprint": Bundle.main.infoDictionary?["EnergySourceFingerprint"] as? String ?? "unknown"
        ]
        do {
            let documents = try FileManager.default.url(for: .documentDirectory, in: .userDomainMask,
                                                        appropriateFor: nil, create: true)
            let directory = documents.appendingPathComponent("EnergyStartDiagnostics", isDirectory: true)
            try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
            let data = try JSONEncoder().encode(snapshot)
            try data.write(to: directory.appendingPathComponent("latest.json"), options: .atomic)
        } catch {
            message = "Could not save start diagnostic: \(error.localizedDescription)"
        }
    }

    func recordScrollCallback(from oldPosition: Int?, to newPosition: Int) {
        guard isRunning, configuration.captureHapticTiming == true else { return }
        pendingScrollCallback = (elapsed, oldPosition, newPosition)
    }

    /// Called immediately before the existing motor request; no live UI update or file write.
    func recordScroll(pattern: String) -> Bool {
        guard isRunning else { return true }
        scrollEvents += 1
        if pattern != configuration.pattern { addIssue("Effect changed during the run.") }
        let play = configuration.scenario != .replayWithoutHaptics && configuration.scenario != .crownWithoutHaptics
        if play { hapticRequests += 1 }
        if configuration.captureHapticTiming == true {
            if let callback = pendingScrollCallback {
                hapticTimings.append(HapticRequestTiming(
                    callbackElapsedSeconds: callback.elapsed, requestElapsedSeconds: elapsed,
                    oldPosition: callback.oldPosition, newPosition: callback.newPosition,
                    pattern: pattern, requestsHaptic: play))
            } else {
                addIssue("Missing scroll callback for a haptic timing record.")
            }
            pendingScrollCallback = nil
        }
        return play
    }

    func unexpectedInput() {
        if isRunning { addIssue("Settings or controls were changed during the run.") }
    }

    /// The diagnostic wake button consumes a touch without changing app settings or scrolling.
    func recordAutomationWakeTap() {
        if isRunning { automationWakeTaps += 1 }
    }

    func updateVisibility(phase: ScenePhase, luminanceReduced: Bool) {
        self.phase = phase
        self.luminanceReduced = luminanceReduced
        guard isRunning else { return }
        let requiresActiveDisplay = configuration.scenario != .idle || metadata["inputDriver"] == "app-idle-v1"
        if requiresActiveDisplay && (phase != .active || luminanceReduced) {
            finish(status: "interrupted")
        } else if elapsed >= configuration.durationSeconds {
            // Idle runs may be suspended by watchOS; report the real elapsed time on return.
            finish(status: "completed")
        } else {
            captureSample()
        }
    }

    func finish(status: String = "cancelled") {
        guard isRunning else { return }
        replayTimer?.invalidate()
        sampleTimer?.invalidate()
        finishTimer?.invalidate()
        replayTimer = nil
        sampleTimer = nil
        finishTimer = nil
        captureSample()
        if metadata["displayPolicy"] == "UI-testing-neutral-wake-taps" {
            metadata["automationWakeTaps"] = String(automationWakeTaps)
        }
        var report = EnergyTestReport(schemaVersion: 1, runID: runID, startedAt: startedAt,
                                      finishedAt: Date(), configuration: configuration,
                                      metadata: metadata, status: status, issues: issues, samples: samples)
        if configuration.captureHapticTiming == true { report.hapticTimings = hapticTimings }
        if configuration.captureRuntimeProfile == true { report.runtimeProfile = EnergyRuntimeProfile(samples: runtimeSamples) }
        report.issues = report.validationIssues
        WKInterfaceDevice.current().isBatteryMonitoringEnabled = previousBatteryMonitoring
        monitoringPrepared = false
        isRunning = false
        lastReport = report
        do {
            let directory = try Self.reportsDirectory()
            let encoder = JSONEncoder()
            encoder.dateEncodingStrategy = .iso8601
            encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
            try encoder.encode(report).write(to: directory.appendingPathComponent("\(runID).json"), options: .atomic)
            message = report.issues.isEmpty ? "Saved battery report." : "Saved flagged report."
        } catch {
            message = "Could not save report: \(error.localizedDescription)"
        }
    }

    private var elapsed: TimeInterval { ProcessInfo.processInfo.systemUptime - startUptime }

    private func captureSample() {
        let device = WKInterfaceDevice.current()
        let seconds = elapsed
        // Multiple lifecycle callbacks can arrive in the same run-loop turn.
        guard samples.last.map({ seconds > $0.elapsedSeconds }) ?? true else { return }
        let level = Double(device.batteryLevel)
        samples.append(EnergyTestSample(
            elapsedSeconds: seconds,
            batteryLevel: level.isFinite && (0...1).contains(level) ? level : nil,
            powerState: Self.powerState(device.batteryState),
            scenePhase: phase == .active ? "active" : (phase == .inactive ? "inactive" : "background"),
            luminanceReduced: luminanceReduced,
            thermalState: ProcessInfo.processInfo.thermalState.rawValue,
            scrollEvents: scrollEvents, hapticRequests: hapticRequests, replaySteps: replaySteps
        ))
        if configuration.captureRuntimeProfile == true, let start = runtimeCPUStart, let cpu = Self.cpuUsage() {
            runtimeSamples.append(EnergyRuntimeSample(elapsedSeconds: seconds,
                userCPUSeconds: cpu.user - start.user, systemCPUSeconds: cpu.system - start.system,
                contentViewBodyUpdates: bodyUpdates, work: workTimings))
        }
    }

    private func addIssue(_ issue: String) {
        if !issues.contains(issue) { issues.append(issue) }
    }

    private func timer(interval: TimeInterval, repeats: Bool, action: @escaping @MainActor () -> Void) -> Timer {
        let timer = Timer(timeInterval: interval, repeats: repeats) { _ in
            // These timers are added only to the main run loop.
            MainActor.assumeIsolated { action() }
        }
        RunLoop.main.add(timer, forMode: .common)
        return timer
    }

    private static func reportsDirectory() throws -> URL {
        let documents = try FileManager.default.url(for: .documentDirectory, in: .userDomainMask,
                                                    appropriateFor: nil, create: true)
        let directory = documents.appendingPathComponent("EnergyTests", isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        return directory
    }

    private static func powerState(_ state: WKInterfaceDeviceBatteryState) -> String {
        switch state {
        case .unplugged: return "unplugged"
        case .charging: return "charging"
        case .full: return "full"
        default: return "unknown"
        }
    }

    private static var hardwareModel: String {
        var system = utsname()
        uname(&system)
        let capacity = MemoryLayout.size(ofValue: system.machine)
        return withUnsafePointer(to: &system.machine) {
            $0.withMemoryRebound(to: CChar.self, capacity: capacity) {
                String(cString: $0)
            }
        }
    }

    private static var isSimulator: Bool {
        #if targetEnvironment(simulator)
        return true
        #else
        return false
        #endif
    }
}

struct EnergyTestSetupView: View {
    @ObservedObject var controller: EnergyTestController
    let start: (EnergyTestConfiguration) -> Void
    @State private var configuration = EnergyTestConfiguration()

    var body: some View {
        List {
            if controller.isRunning {
                Text("Run in progress. Keep the app visible for active-use tests.")
                Button("Stop and save", role: .destructive) { controller.finish() }
            } else {
                Picker("Test", selection: $configuration.scenario) {
                    ForEach(EnergyTestScenario.menuCases) { Text($0.title).tag($0) }
                }
                Picker("Duration", selection: $configuration.durationSeconds) {
                    ForEach([120.0, 300, 600, 900], id: \.self) { seconds in
                        Text("\(Int(seconds / 60)) minutes").tag(seconds)
                    }
                }
                if configuration.scenario.usesReplay {
                    Picker("Steps/sec", selection: $configuration.stepsPerSecond) {
                        ForEach([2.0, 5, 10], id: \.self) { Text("\(Int($0))").tag($0) }
                    }
                }
                Picker("Effect", selection: $configuration.pattern) {
                    ForEach(HapticPattern.nonRandomPatterns) { Text($0.displayName).tag($0.rawValue) }
                }
                TextField("Build label", text: $configuration.label)
                TextField("Watch, health, display, connectivity", text: $configuration.conditions)
                Text("Replay is synthetic. Real Crown capture logs normal use. Runs stop if an active-use test loses the foreground. No keep-awake override.")
                    .font(.footnote)
                Button("Start") {
                    // Setup is saved before measurement so repeated trials need no re-entry.
                    if let data = try? JSONEncoder().encode(configuration) {
                        UserDefaults.standard.set(data, forKey: "energy.test.configuration")
                    }
                    start(configuration)
                }
                    .disabled(!configuration.validationIssues.isEmpty)
            }
            if !controller.message.isEmpty { Text(controller.message).font(.footnote) }
            if let report = controller.lastReport {
                Text("\(report.configuration.label): \(Int(report.elapsedSeconds)) seconds")
                if let drop = report.batteryDropPercentagePoints {
                    Text(String(format: "Battery drop: %.1f percentage points", drop))
                }
                ForEach(report.issues, id: \.self) { Text($0).foregroundStyle(.orange) }
                Text("Report: Documents/EnergyTests/\(report.runID).json").font(.footnote)
            }
        }
        .navigationTitle("Energy tests")
        .onAppear {
            if let data = UserDefaults.standard.data(forKey: "energy.test.configuration"),
               let saved = try? JSONDecoder().decode(EnergyTestConfiguration.self, from: data) {
                configuration = saved
            }
        }
    }
}
#endif
