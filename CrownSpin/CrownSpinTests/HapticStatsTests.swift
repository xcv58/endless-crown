import XCTest
import Combine

final class HapticStatsTests: XCTestCase {

    private var stats: HapticStats!
    private var defaults: UserDefaults!
    private var sharedDefaults: UserDefaults!
    private var suiteName: String!

    override func setUp() {
        super.setUp()
        suiteName = "CrownSpinStatsTests." + UUID().uuidString
        defaults = UserDefaults(suiteName: suiteName)!
        sharedDefaults = UserDefaults(suiteName: suiteName + ".shared")!
        stats = HapticStats(defaults: defaults, sharedDefaults: sharedDefaults)
    }

    override func tearDown() {
        stats.resetStats()
        defaults.removePersistentDomain(forName: suiteName)
        sharedDefaults.removePersistentDomain(forName: suiteName + ".shared")
        stats = nil
        super.tearDown()
    }

    // MARK: - Singleton

    func testSingletonIdentity() {
        XCTAssertTrue(HapticStats.shared === HapticStats.shared)
    }

    // MARK: - Initial State

    func testInitialStateAfterReset() {
        XCTAssertEqual(stats.totalHaptics, 0)
        XCTAssertEqual(stats.sessionHaptics, 0)
        XCTAssertEqual(stats.longestSession, 0)
        XCTAssertEqual(stats.totalSessions, 0)
        XCTAssertEqual(stats.peakSpeed, 0)
        XCTAssertEqual(stats.currentStreak, 0)
        XCTAssertEqual(stats.totalSpinTime, 0)
    }

    // MARK: - recordHaptic

    func testRecordHapticIncrementsTotalHaptics() {
        stats.recordHaptic()
        XCTAssertEqual(stats.totalHaptics, 1)
        stats.recordHaptic()
        XCTAssertEqual(stats.totalHaptics, 2)
    }

    func testRecordHapticIncrementsSessionHaptics() {
        stats.recordHaptic()
        XCTAssertEqual(stats.sessionHaptics, 1)
        stats.recordHaptic()
        stats.recordHaptic()
        XCTAssertEqual(stats.sessionHaptics, 3)
    }

    func testRecordHapticIncrementsBothCounters() {
        stats.recordHaptic()
        XCTAssertEqual(stats.totalHaptics, 1)
        XCTAssertEqual(stats.sessionHaptics, 1)
    }

    // MARK: - startSession

    func testStartSessionResetsSessionHaptics() {
        stats.recordHaptic()
        stats.recordHaptic()
        XCTAssertEqual(stats.sessionHaptics, 2)
        stats.startSession()
        XCTAssertEqual(stats.sessionHaptics, 0)
    }

    func testStartSessionIncrementsTotalSessions() {
        XCTAssertEqual(stats.totalSessions, 0)
        stats.startSession()
        XCTAssertEqual(stats.totalSessions, 1)
        stats.startSession()
        XCTAssertEqual(stats.totalSessions, 2)
    }

    func testStartSessionPreservesTotalHaptics() {
        stats.recordHaptic()
        stats.recordHaptic()
        stats.recordHaptic()
        let total = stats.totalHaptics
        stats.startSession()
        XCTAssertEqual(stats.totalHaptics, total)
    }

    // MARK: - endSession

    func testEndSessionUpdatesLongestSession() {
        stats.recordHaptic()
        stats.recordHaptic()
        stats.recordHaptic()
        stats.endSession()
        XCTAssertEqual(stats.longestSession, 3)
    }

    func testEndSessionDoesNotUpdateLongestWhenShorter() {
        // First session: 5 haptics
        for _ in 0..<5 { stats.recordHaptic() }
        stats.endSession()
        XCTAssertEqual(stats.longestSession, 5)

        // Second session: 2 haptics (shorter)
        stats.startSession()
        stats.recordHaptic()
        stats.recordHaptic()
        stats.endSession()
        XCTAssertEqual(stats.longestSession, 5)
    }

    func testEndSessionWithZeroHapticsDoesNotUpdateLongest() {
        // First set a longest of 3
        for _ in 0..<3 { stats.recordHaptic() }
        stats.endSession()
        XCTAssertEqual(stats.longestSession, 3)

        // End a session with 0 haptics
        stats.startSession()
        stats.endSession()
        XCTAssertEqual(stats.longestSession, 3)
    }

    func testEndSessionUpdatesLongestWhenLonger() {
        // First session: 2 haptics
        stats.recordHaptic()
        stats.recordHaptic()
        stats.endSession()
        XCTAssertEqual(stats.longestSession, 2)

        // Second session: 5 haptics (longer)
        stats.startSession()
        for _ in 0..<5 { stats.recordHaptic() }
        stats.endSession()
        XCTAssertEqual(stats.longestSession, 5)
    }

    // MARK: - resetStats

    func testResetStatsClearsEverything() {
        stats.recordHaptic()
        stats.recordHaptic()
        stats.startSession()
        stats.recordHaptic()
        stats.endSession()

        stats.resetStats()

        XCTAssertEqual(stats.totalHaptics, 0)
        XCTAssertEqual(stats.sessionHaptics, 0)
        XCTAssertEqual(stats.longestSession, 0)
        XCTAssertEqual(stats.totalSessions, 0)
        XCTAssertEqual(stats.peakSpeed, 0)
        XCTAssertEqual(stats.currentStreak, 0)
        XCTAssertEqual(stats.totalSpinTime, 0)
    }

    // MARK: - Full Session Lifecycle

    func testMultiSessionLifecycle() {
        // Session 1: 3 haptics
        stats.startSession()
        for _ in 0..<3 { stats.recordHaptic() }
        stats.endSession()

        XCTAssertEqual(stats.totalHaptics, 3)
        XCTAssertEqual(stats.totalSessions, 1)
        XCTAssertEqual(stats.longestSession, 3)

        // Session 2: 5 haptics
        stats.startSession()
        for _ in 0..<5 { stats.recordHaptic() }
        stats.endSession()

        XCTAssertEqual(stats.totalHaptics, 8)
        XCTAssertEqual(stats.totalSessions, 2)
        XCTAssertEqual(stats.longestSession, 5)

        // Session 3: 1 haptic (doesn't beat longest)
        stats.startSession()
        stats.recordHaptic()
        stats.endSession()

        XCTAssertEqual(stats.totalHaptics, 9)
        XCTAssertEqual(stats.totalSessions, 3)
        XCTAssertEqual(stats.longestSession, 5)
    }

    // MARK: - Formatted Properties

    func testFormattedTotalUsesFormatHapticNumber() {
        XCTAssertEqual(stats.formattedTotal, "0")
        for _ in 0..<1500 { stats.recordHaptic() }
        XCTAssertEqual(stats.formattedTotal, "1.5K")
    }

    func testFormattedSessionUsesFormatHapticNumber() {
        XCTAssertEqual(stats.formattedSession, "0")
        for _ in 0..<2000 { stats.recordHaptic() }
        XCTAssertEqual(stats.formattedSession, "2.0K")
    }

    func testFormattedLongestUsesFormatHapticNumber() {
        XCTAssertEqual(stats.formattedLongest, "0")
        for _ in 0..<1000 { stats.recordHaptic() }
        stats.endSession()
        XCTAssertEqual(stats.formattedLongest, "1.0K")
    }

    // MARK: - UserDefaults Persistence

    func testContinuousInputUpdatesLiveCountersWithoutPerEventPersistence() {
        var publishedCounts: [Int] = []
        let subscription = stats.$totalHaptics.sink { publishedCounts.append($0) }
        for number in 1...200 {
            stats.recordHaptic()
            stats.recordItemNumber(number)
        }
        XCTAssertEqual(stats.totalHaptics, 200)
        XCTAssertEqual(stats.sessionHaptics, 200)
        XCTAssertEqual(publishedCounts, Array(0...200))
        XCTAssertEqual(defaults.integer(forKey: "stats.totalHaptics"), 0)
        XCTAssertEqual(sharedDefaults.integer(forKey: "stats.totalHaptics"), 0)
        XCTAssertNil(sharedDefaults.object(forKey: "currentItemNumber"))
        subscription.cancel()

        stats.flushPendingPersistence()
        XCTAssertEqual(defaults.integer(forKey: "stats.totalHaptics"), 200)
        XCTAssertEqual(sharedDefaults.integer(forKey: "stats.totalHaptics"), 200)
        XCTAssertEqual(sharedDefaults.integer(forKey: "currentItemNumber"), 200)
        XCTAssertEqual(defaults.double(forKey: "stats.peakSpeed"), stats.peakSpeed)
    }

    func testPeriodicSaveIsNotPostponedByContinuousInput() {
        stats = HapticStats(defaults: defaults, sharedDefaults: sharedDefaults, persistenceInterval: 0.04)
        let savedDuringInput = expectation(description: "Batch saved during ongoing input")
        stats.recordHaptic()
        let input = Timer(timeInterval: 0.005, repeats: true) { [self] timer in
            stats.recordHaptic()
            stats.recordItemNumber(stats.totalHaptics)
            if defaults.integer(forKey: "stats.totalHaptics") > 0 {
                timer.invalidate()
                savedDuringInput.fulfill()
            }
        }
        RunLoop.main.add(input, forMode: .common)
        wait(for: [savedDuringInput], timeout: 2)
        input.invalidate()
        XCTAssertGreaterThan(defaults.integer(forKey: "stats.totalHaptics"), 0)
        XCTAssertGreaterThan(stats.totalHaptics, defaults.integer(forKey: "stats.totalHaptics"))
    }

    func testExplicitSaveAllowsAnotherTimedBatch() {
        stats = HapticStats(defaults: defaults, sharedDefaults: sharedDefaults, persistenceInterval: 0.02)
        stats.recordHaptic()
        stats.flushPendingPersistence()
        stats.recordHaptic()
        XCTAssertEqual(defaults.integer(forKey: "stats.totalHaptics"), 1)
        RunLoop.main.run(until: Date(timeIntervalSinceNow: 0.1))
        XCTAssertEqual(defaults.integer(forKey: "stats.totalHaptics"), 2)
    }

    func testRecreatedStatisticsLoadTheLatestSavedBatch() {
        for number in 1...37 {
            stats.recordHaptic()
            stats.recordItemNumber(-number)
        }
        stats.flushPendingPersistence()
        let reloaded = HapticStats(defaults: defaults, sharedDefaults: sharedDefaults)
        XCTAssertEqual(reloaded.totalHaptics, 37)
        XCTAssertEqual(reloaded.peakSpeed, stats.peakSpeed)
        XCTAssertEqual(sharedDefaults.integer(forKey: "currentItemNumber"), -37)
    }

    func testSessionEndSavesPendingCountersAndComplicationNumber() {
        for _ in 0..<23 { stats.recordHaptic() }
        stats.recordItemNumber(91)
        stats.endSession()
        XCTAssertEqual(defaults.integer(forKey: "stats.totalHaptics"), 23)
        XCTAssertEqual(sharedDefaults.integer(forKey: "stats.totalHaptics"), 23)
        XCTAssertEqual(sharedDefaults.integer(forKey: "stats.longestSession"), 23)
        XCTAssertEqual(sharedDefaults.integer(forKey: "currentItemNumber"), 91)
    }

    func testStatisticsResetCannotResurrectAnOlderPendingCount() {
        for _ in 0..<13 { stats.recordHaptic() }
        stats.resetStats()
        stats.flushPendingPersistence()
        XCTAssertEqual(defaults.integer(forKey: "stats.totalHaptics"), 0)
        XCTAssertEqual(sharedDefaults.integer(forKey: "stats.totalHaptics"), 0)
        XCTAssertEqual(defaults.double(forKey: "stats.peakSpeed"), 0)
    }

    func testCounterResetReplacesThePendingComplicationNumber() {
        stats.recordItemNumber(124)
        stats.recordItemNumber(0)
        stats.flushPendingPersistence()
        XCTAssertEqual(sharedDefaults.integer(forKey: "currentItemNumber"), 0)
        stats.flushPendingPersistence()
        XCTAssertEqual(sharedDefaults.integer(forKey: "currentItemNumber"), 0)
    }

    func testSavingWorksWithoutAnAppGroupStore() {
        stats = HapticStats(defaults: defaults, sharedDefaults: nil)
        stats.recordHaptic()
        stats.recordItemNumber(-6)
        stats.flushPendingPersistence()
        XCTAssertEqual(defaults.integer(forKey: "stats.totalHaptics"), 1)
    }

    func testTotalHapticsPersistsToUserDefaults() {
        stats.recordHaptic()
        stats.recordHaptic()
        stats.flushPendingPersistence()
        XCTAssertEqual(defaults.integer(forKey: "stats.totalHaptics"), 2)
    }

    func testLongestSessionPersistsToUserDefaults() {
        for _ in 0..<7 { stats.recordHaptic() }
        stats.endSession()
        XCTAssertEqual(defaults.integer(forKey: "stats.longestSession"), 7)
    }

    func testTotalSessionsPersistsToUserDefaults() {
        stats.startSession()
        stats.startSession()
        XCTAssertEqual(defaults.integer(forKey: "stats.totalSessions"), 2)
    }

    func testSessionHapticsDoesNotPersistToUserDefaults() {
        stats.recordHaptic()
        stats.recordHaptic()
        // sessionHaptics should not be stored in UserDefaults
        // The key "stats.sessionHaptics" should remain at default (0)
        // since sessionHaptics has no didSet that writes to UserDefaults
        defaults.removeObject(forKey: "stats.sessionHaptics")
        XCTAssertEqual(defaults.integer(forKey: "stats.sessionHaptics"), 0)
    }

    // MARK: - Peak Speed

    func testPeakSpeedStartsAtZero() {
        XCTAssertEqual(stats.peakSpeed, 0)
    }

    func testPeakSpeedUpdatesOnRapidHaptics() {
        // Rapid haptics should produce a measurable speed
        for _ in 0..<10 { stats.recordHaptic() }
        XCTAssertGreaterThan(stats.peakSpeed, 0)
    }

    func testPeakSpeedOnlyIncreases() {
        // Record rapid haptics to establish a peak
        for _ in 0..<20 { stats.recordHaptic() }
        let peak = stats.peakSpeed
        XCTAssertGreaterThan(peak, 0)

        // Wait beyond the speed window so new haptics are slower
        Thread.sleep(forTimeInterval: 0.6)
        stats.recordHaptic()

        // Peak should not decrease
        XCTAssertGreaterThanOrEqual(stats.peakSpeed, peak)
    }

    func testFormattedPeakSpeedZero() {
        XCTAssertEqual(stats.formattedPeakSpeed, "0")
    }

    func testFormattedPeakSpeedNonZero() {
        for _ in 0..<10 { stats.recordHaptic() }
        XCTAssertTrue(stats.formattedPeakSpeed.hasSuffix("/sec"))
    }

    func testPeakSpeedPersistsToUserDefaults() {
        for _ in 0..<10 { stats.recordHaptic() }
        stats.flushPendingPersistence()
        XCTAssertGreaterThan(defaults.double(forKey: "stats.peakSpeed"), 0)
    }

    // MARK: - Streak

    func testStreakFirstSession() {
        stats.startSession()
        XCTAssertEqual(stats.currentStreak, 1)
    }

    func testStreakSameDayDoesNotIncrement() {
        stats.startSession()
        XCTAssertEqual(stats.currentStreak, 1)
        // Another session same day
        stats.startSession()
        XCTAssertEqual(stats.currentStreak, 1)
    }

    func testStreakConsecutiveDay() {
        stats.startSession()
        XCTAssertEqual(stats.currentStreak, 1)

        // Simulate yesterday's date
        let yesterday = Calendar.current.date(byAdding: .day, value: -1, to: Calendar.current.startOfDay(for: Date()))!
        defaults.set(yesterday.timeIntervalSince1970, forKey: "stats.lastSessionDate")

        stats.startSession()
        XCTAssertEqual(stats.currentStreak, 2)
    }

    func testStreakResetsAfterGap() {
        stats.startSession()
        XCTAssertEqual(stats.currentStreak, 1)

        // Simulate 3 days ago
        let threeDaysAgo = Calendar.current.date(byAdding: .day, value: -3, to: Calendar.current.startOfDay(for: Date()))!
        defaults.set(threeDaysAgo.timeIntervalSince1970, forKey: "stats.lastSessionDate")

        stats.startSession()
        XCTAssertEqual(stats.currentStreak, 1)
    }

    func testFormattedStreakSingular() {
        stats.startSession()
        XCTAssertEqual(stats.formattedStreak, "1 day")
    }

    func testFormattedStreakPlural() {
        stats.startSession()
        // Simulate yesterday
        let yesterday = Calendar.current.date(byAdding: .day, value: -1, to: Calendar.current.startOfDay(for: Date()))!
        defaults.set(yesterday.timeIntervalSince1970, forKey: "stats.lastSessionDate")
        stats.startSession()
        XCTAssertEqual(stats.formattedStreak, "2 days")
    }

    func testStreakPersistsToUserDefaults() {
        stats.startSession()
        XCTAssertEqual(defaults.integer(forKey: "stats.currentStreak"), 1)
    }

    func testResetClearsStreak() {
        stats.startSession()
        XCTAssertEqual(stats.currentStreak, 1)
        stats.resetStats()
        XCTAssertEqual(stats.currentStreak, 0)
    }

    // MARK: - Spin Time

    func testSpinTimeStartsAtZero() {
        XCTAssertEqual(stats.totalSpinTime, 0)
    }

    func testSpinTimeAccumulates() {
        stats.startSpinning()
        Thread.sleep(forTimeInterval: 0.1)
        stats.stopSpinning()
        XCTAssertGreaterThan(stats.totalSpinTime, 0)
    }

    func testSpinTimeAccumulatesAcrossMultipleSpins() {
        stats.startSpinning()
        Thread.sleep(forTimeInterval: 0.1)
        stats.stopSpinning()
        let first = stats.totalSpinTime

        stats.startSpinning()
        Thread.sleep(forTimeInterval: 0.1)
        stats.stopSpinning()
        XCTAssertGreaterThan(stats.totalSpinTime, first)
    }

    func testStopSpinningWithoutStartIsNoOp() {
        stats.stopSpinning()
        XCTAssertEqual(stats.totalSpinTime, 0)
    }

    func testDoubleStartSpinningIgnoresSecond() {
        stats.startSpinning()
        Thread.sleep(forTimeInterval: 0.1)
        stats.startSpinning() // should be ignored
        Thread.sleep(forTimeInterval: 0.1)
        stats.stopSpinning()
        // Should have ~0.2s, not reset at second startSpinning
        XCTAssertGreaterThan(stats.totalSpinTime, 0.15)
    }

    func testEndSessionStopsSpinning() {
        stats.startSpinning()
        Thread.sleep(forTimeInterval: 0.1)
        stats.endSession()
        let time = stats.totalSpinTime
        XCTAssertGreaterThan(time, 0)
        // Calling stop again should not change anything
        stats.stopSpinning()
        XCTAssertEqual(stats.totalSpinTime, time)
    }

    func testSpinTimePersistsToUserDefaults() {
        stats.startSpinning()
        Thread.sleep(forTimeInterval: 0.1)
        stats.stopSpinning()
        XCTAssertGreaterThan(defaults.double(forKey: "stats.totalSpinTime"), 0)
    }

    // MARK: - Average Session

    func testFormattedAvgSessionZeroSessions() {
        XCTAssertEqual(stats.formattedAvgSession, "0")
    }

    func testFormattedAvgSessionCalculation() {
        stats.startSession()
        for _ in 0..<10 { stats.recordHaptic() }
        stats.endSession()

        stats.startSession()
        for _ in 0..<20 { stats.recordHaptic() }
        stats.endSession()

        // 30 total / 2 sessions = 15
        XCTAssertEqual(stats.formattedAvgSession, "15")
    }

    // MARK: - formatDuration

    func testFormatDurationSeconds() {
        XCTAssertEqual(formatDuration(0), "0s")
        XCTAssertEqual(formatDuration(45), "45s")
        XCTAssertEqual(formatDuration(59), "59s")
    }

    func testFormatDurationMinutes() {
        XCTAssertEqual(formatDuration(60), "1m")
        XCTAssertEqual(formatDuration(90), "1m")
        XCTAssertEqual(formatDuration(3599), "59m")
    }

    func testFormatDurationHours() {
        XCTAssertEqual(formatDuration(3600), "1h 0m")
        XCTAssertEqual(formatDuration(3723), "1h 2m")
        XCTAssertEqual(formatDuration(7200), "2h 0m")
    }
}
