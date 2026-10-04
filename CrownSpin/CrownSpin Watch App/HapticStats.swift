import Foundation
import Combine
#if canImport(WidgetKit)
import WidgetKit
#endif

/// Tracks haptic usage statistics
class HapticStats: ObservableObject {
    static let shared = HapticStats()
    private let defaults: UserDefaults
    private let sharedDefaults: UserDefaults?
    private let persistenceInterval: TimeInterval

    private enum Keys {
        static let totalHaptics = "stats.totalHaptics"
        static let sessionHaptics = "stats.sessionHaptics"
        static let longestSession = "stats.longestSession"
        static let totalSessions = "stats.totalSessions"
        static let lastSessionDate = "stats.lastSessionDate"
        static let peakSpeed = "stats.peakSpeed"
        static let currentStreak = "stats.currentStreak"
        static let totalSpinTime = "stats.totalSpinTime"
    }

    @Published private(set) var totalHaptics: Int {
        didSet {
            totalHapticsNeedsSave = true
            schedulePersistence()
        }
    }

    @Published private(set) var sessionHaptics: Int = 0

    @Published private(set) var longestSession: Int {
        didSet {
            defaults.set(longestSession, forKey: Keys.longestSession)
            sharedDefaults?.set(longestSession, forKey: Keys.longestSession)
        }
    }

    @Published private(set) var totalSessions: Int {
        didSet {
            defaults.set(totalSessions, forKey: Keys.totalSessions)
            sharedDefaults?.set(totalSessions, forKey: Keys.totalSessions)
        }
    }

    @Published private(set) var peakSpeed: Double {
        didSet {
            peakSpeedNeedsSave = true
            schedulePersistence()
        }
    }

    @Published private(set) var currentStreak: Int {
        didSet {
            defaults.set(currentStreak, forKey: Keys.currentStreak)
        }
    }

    @Published private(set) var totalSpinTime: TimeInterval {
        didSet {
            defaults.set(totalSpinTime, forKey: Keys.totalSpinTime)
        }
    }

    // Speed measurement: rolling window of haptic timestamps
    private var recentHapticTimes: [TimeInterval] = []
    private static let speedWindow: TimeInterval = 0.5

    // Spin time tracking
    private var spinStartTime: TimeInterval?

    // Main-run-loop batching; these fields never publish changes to the scrolling view.
    private var persistenceTimer: Timer?
    private var totalHapticsNeedsSave = false
    private var peakSpeedNeedsSave = false
    private var pendingItemNumber: Int?

    init(defaults: UserDefaults = .standard,
         sharedDefaults: UserDefaults? = UserDefaults(suiteName: appGroupSuiteName),
         persistenceInterval: TimeInterval = 2) {
        self.defaults = defaults
        self.sharedDefaults = sharedDefaults
        self.persistenceInterval = persistenceInterval
        self.totalHaptics = defaults.integer(forKey: Keys.totalHaptics)
        self.longestSession = defaults.integer(forKey: Keys.longestSession)
        self.totalSessions = defaults.integer(forKey: Keys.totalSessions)
        self.peakSpeed = defaults.double(forKey: Keys.peakSpeed)
        self.currentStreak = defaults.integer(forKey: Keys.currentStreak)
        self.totalSpinTime = defaults.double(forKey: Keys.totalSpinTime)
        // Sync existing stats to shared defaults for the complication
        sharedDefaults?.set(totalHaptics, forKey: Keys.totalHaptics)
        sharedDefaults?.set(longestSession, forKey: Keys.longestSession)
        sharedDefaults?.set(totalSessions, forKey: Keys.totalSessions)
    }

    deinit {
        persistenceTimer?.invalidate()
    }

    func recordItemNumber(_ number: Int) {
        pendingItemNumber = number
        schedulePersistence()
    }

    /// Submit the latest batch to UserDefaults before idle, suspension, or a widget refresh.
    /// UserDefaults itself writes asynchronously; this is not a synchronous disk flush.
    func flushPendingPersistence() {
        persistenceTimer?.invalidate()
        persistenceTimer = nil
        if totalHapticsNeedsSave {
            defaults.set(totalHaptics, forKey: Keys.totalHaptics)
            sharedDefaults?.set(totalHaptics, forKey: Keys.totalHaptics)
            totalHapticsNeedsSave = false
        }
        if peakSpeedNeedsSave {
            defaults.set(peakSpeed, forKey: Keys.peakSpeed)
            peakSpeedNeedsSave = false
        }
        if let number = pendingItemNumber {
            sharedDefaults?.set(number, forKey: "currentItemNumber")
            pendingItemNumber = nil
        }
    }

    private func schedulePersistence() {
        // Do not postpone an existing batch as more scroll events arrive.
        guard persistenceTimer == nil else { return }
        let timer = Timer(timeInterval: persistenceInterval, repeats: false) { [weak self] _ in
            self?.flushPendingPersistence()
        }
        persistenceTimer = timer
        RunLoop.main.add(timer, forMode: .common)
    }

    func recordHaptic() {
        totalHaptics += 1
        sessionHaptics += 1

        // Track peak speed with a rolling window
        let now = ProcessInfo.processInfo.systemUptime
        recentHapticTimes.append(now)
        let cutoff = now - Self.speedWindow
        recentHapticTimes.removeAll { $0 < cutoff }
        if let earliest = recentHapticTimes.first {
            let elapsed = now - earliest
            if elapsed > 0 && recentHapticTimes.count > 1 {
                let speed = Double(recentHapticTimes.count) / elapsed
                if speed > peakSpeed {
                    peakSpeed = speed
                }
            }
        }
    }

    func startSession() {
        sessionHaptics = 0
        totalSessions += 1
        recentHapticTimes.removeAll()

        // Streak tracking
        let calendar = Calendar.current
        let today = calendar.startOfDay(for: Date())
        if let lastDateInterval = defaults.object(forKey: Keys.lastSessionDate) as? TimeInterval {
            let lastDate = calendar.startOfDay(for: Date(timeIntervalSince1970: lastDateInterval))
            let daysBetween = calendar.dateComponents([.day], from: lastDate, to: today).day ?? 0
            if daysBetween == 1 {
                currentStreak += 1
            } else if daysBetween > 1 {
                currentStreak = 1
            }
            // daysBetween == 0 means same day — no change
        } else {
            // First ever session
            currentStreak = 1
        }
        defaults.set(today.timeIntervalSince1970, forKey: Keys.lastSessionDate)
        flushPendingPersistence()
    }

    func endSession() {
        if sessionHaptics > longestSession {
            longestSession = sessionHaptics
        }
        stopSpinning()
        flushPendingPersistence()
        // Refresh complications when session ends
        #if canImport(WidgetKit)
        WidgetCenter.shared.reloadAllTimelines()
        #endif
    }

    func startSpinning() {
        if spinStartTime == nil {
            spinStartTime = ProcessInfo.processInfo.systemUptime
        }
    }

    func stopSpinning() {
        if let start = spinStartTime {
            totalSpinTime += ProcessInfo.processInfo.systemUptime - start
            spinStartTime = nil
        }
    }

    func resetStats() {
        totalHaptics = 0
        longestSession = 0
        totalSessions = 0
        sessionHaptics = 0
        peakSpeed = 0
        currentStreak = 0
        totalSpinTime = 0
        recentHapticTimes.removeAll()
        spinStartTime = nil
        defaults.removeObject(forKey: Keys.lastSessionDate)
        flushPendingPersistence()
        #if canImport(WidgetKit)
        WidgetCenter.shared.reloadAllTimelines()
        #endif
    }

    var formattedTotal: String {
        formatHapticNumber(totalHaptics)
    }

    var formattedSession: String {
        formatHapticNumber(sessionHaptics)
    }

    var formattedLongest: String {
        formatHapticNumber(longestSession)
    }

    var formattedPeakSpeed: String {
        if peakSpeed == 0 { return "0" }
        return String(format: "%.1f /sec", peakSpeed)
    }

    var formattedAvgSession: String {
        guard totalSessions > 0 else { return "0" }
        return formatHapticNumber(totalHaptics / totalSessions)
    }

    var formattedStreak: String {
        if currentStreak <= 1 { return "\(currentStreak) day" }
        return "\(currentStreak) days"
    }

    var formattedSpinTime: String {
        formatDuration(totalSpinTime)
    }
}
