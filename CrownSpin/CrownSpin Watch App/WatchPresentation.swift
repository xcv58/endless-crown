/// Owns the main screen's mutually exclusive presentations.
struct WatchPresentation {
    enum Sheet: Hashable, Identifiable {
        case menu, effects, numbers, statistics, guide
        #if ENERGY_TESTING
        case energyTests
        #endif

        var id: Self { self }
    }

    enum Destination: Equatable {
        case sheet(Sheet)
        case resetCounter
    }

    private enum Phase {
        case idle
        case sheet(Sheet)
        case dismissingSheet(next: Destination?)
        case confirmingReset
    }

    private var phase = Phase.idle

    var sheet: Sheet? {
        guard case let .sheet(sheet) = phase else { return nil }
        return sheet
    }

    var isConfirmingReset: Bool {
        if case .confirmingReset = phase { return true }
        return false
    }

    @discardableResult
    mutating func present(_ sheet: Sheet) -> Bool {
        guard case .idle = phase else { return false }
        phase = .sheet(sheet)
        return true
    }

    mutating func selectMenuDestination(_ destination: Destination) {
        guard case .sheet(.menu) = phase else { return }
        phase = .dismissingSheet(next: destination)
    }

    mutating func dismissSheet() {
        guard case .sheet = phase else { return }
        phase = .dismissingSheet(next: nil)
    }

    mutating func sheetDidDismiss() {
        switch phase {
        case let .dismissingSheet(.sheet(sheet)):
            phase = .sheet(sheet)
        case .dismissingSheet(.resetCounter):
            phase = .confirmingReset
        case .dismissingSheet(nil), .sheet:
            phase = .idle
        case .idle, .confirmingReset:
            break
        }
    }

    mutating func dismissReset() {
        guard case .confirmingReset = phase else { return }
        phase = .idle
    }
}
