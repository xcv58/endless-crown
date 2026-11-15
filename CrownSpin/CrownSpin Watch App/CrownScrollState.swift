/// Owns scroll input gating and the current burst. The view owns the timer.
struct CrownScrollState: Equatable {
    enum Phase {
        case positioning, idle, scrolling
    }

    private(set) var phase = Phase.positioning
    private var lastPosition: Int

    init(center: Int) {
        lastPosition = center
    }

    var acceptsInput: Bool { phase != .positioning }
    var isScrolling: Bool { phase == .scrolling }

    mutating func receivedPosition(_ position: Int?) -> Int? {
        guard let position, position != lastPosition else { return nil }
        lastPosition = position
        return acceptsInput ? position : nil
    }

    mutating func recentered(at center: Int) {
        lastPosition = center
    }

    mutating func initialPositionDidSettle() {
        guard phase == .positioning else { return }
        phase = .idle
    }

    mutating func beganScrolling() {
        guard phase == .idle else { return }
        phase = .scrolling
    }

    mutating func becameIdle() {
        guard phase == .scrolling else { return }
        phase = .idle
    }

    mutating func leftScreen() {
        phase = .positioning
    }
}
