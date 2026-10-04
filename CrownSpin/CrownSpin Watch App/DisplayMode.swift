import Foundation

/// Visual presentation only; Crown input and haptic delivery use the same path in every mode.
enum DisplayMode: String, CaseIterable, Identifiable {
    case highContrast
    case ambient
    case hapticsOnly

    static let preferenceKey = "displayMode"
    static let legacyAmbientKey = "ambientModeEnabled"

    var id: String { rawValue }
    var usesDimmedAppearance: Bool { self != .highContrast }

    var displayName: String {
        switch self {
        case .highContrast: return "Standard"
        case .ambient: return "Ambient"
        case .hapticsOnly: return "Haptics Only"
        }
    }

    var icon: String {
        switch self {
        case .highContrast: return "sun.max"
        case .ambient: return "moon"
        case .hapticsOnly: return "eye.slash"
        }
    }

    var detail: String {
        switch self {
        case .highContrast: return "Normal display"
        case .ambient: return "Dim display"
        case .hapticsOnly: return "Black display"
        }
    }

    static func load(from defaults: UserDefaults = .standard) -> DisplayMode {
        if let saved = defaults.string(forKey: preferenceKey), let mode = DisplayMode(rawValue: saved) {
            return mode
        }
        // Carry over existing users' visual preference, including an explicit false value.
        let mode: DisplayMode = defaults.object(forKey: legacyAmbientKey) == nil
            || defaults.bool(forKey: legacyAmbientKey) ? .ambient : .highContrast
        mode.save(to: defaults)
        return mode
    }

    func save(to defaults: UserDefaults = .standard) {
        defaults.set(rawValue, forKey: Self.preferenceKey)
        // Older builds fall back to the dim interface when Haptics Only is selected.
        defaults.set(usesDimmedAppearance, forKey: Self.legacyAmbientKey)
    }
}

/// Revealing controls doesn't change the saved mode. The next scroll returns to black.
struct DisplayModeState {
    private(set) var mode: DisplayMode
    private var controlsRevealed = false

    init(mode: DisplayMode = .ambient) {
        self.mode = mode
    }

    var showsBlackDisplay: Bool { mode == .hapticsOnly && !controlsRevealed }

    mutating func select(_ mode: DisplayMode) {
        self.mode = mode
        controlsRevealed = false
    }

    mutating func revealControls() {
        guard mode == .hapticsOnly else { return }
        controlsRevealed = true
    }

    mutating func didScroll() {
        controlsRevealed = false
    }
}
