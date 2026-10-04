import SwiftUI
import WatchKit
#if canImport(WidgetKit)
import WidgetKit
#endif

struct ContentView: View {
    // MARK: - Constants
    private enum Constants {
        static let patternKey = "selectedHapticPattern"
        static let baseOffsetKey = "baseOffset"
        static let guideSeenKey = "hasSeenInteractionGuide"
        static let menuButtonHiddenKey = "menuButtonHidden"
        static let numberSystemKey = "numberSystem"
        static let windowSize = 1000
        static let windowCenter = 500
        static let rebalanceThreshold = 100
        static let idleDelay: TimeInterval = 1.5
        static let menuAutoHideDelay: TimeInterval = 3.0
    }

    // MARK: - State
    @State private var currentPattern: HapticPattern = .clicks
    @State private var scrollPosition: Int? = Constants.windowCenter
    @State private var lastPosition: Int = Constants.windowCenter
    @State private var isScrolling: Bool = false
    @State private var scrollTimer: Timer?
    @State private var hasInitialized: Bool = false

    // Random mode state
    @State private var randomChangeCounter: Int = 0
    @State private var randomChangeThreshold: Int = Int.random(in: 3...5)
    @State private var currentRandomPattern: HapticPattern = .clicks

    // Infinite scroll state
    @State private var baseOffset: Int = 0

    // UI state
    @State private var showPatternPicker: Bool = false
    @State private var showStats: Bool = false
    @State private var showResetConfirmation: Bool = false
    @State private var showMenu: Bool = false
    @State private var showGuide: Bool = false
    @State private var showNumberSystemPicker: Bool = false
    @State private var showGestureHint: Bool = false
    @State private var showMenuButton: Bool = true
    @State private var isMenuButtonHidden: Bool = false
    @State private var menuButtonTimer: Timer?
    @State private var displayModeState = DisplayModeState()
    @State private var numberSystem: NumberSystem = .decimal
    @Environment(\.scenePhase) private var scenePhase

    // Stats
    @StateObject private var stats = HapticStats.shared

    private var isAmbientMode: Bool { displayModeState.mode.usesDimmedAppearance }
    private var isBlackDisplay: Bool { displayModeState.showsBlackDisplay }

    private var modeSelection: Binding<DisplayMode> {
        Binding(get: { displayModeState.mode }, set: { selectDisplayMode($0) })
    }

    // MARK: - Body
    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            // Main scroll view
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(spacing: 2) {
                        ForEach(0..<Constants.windowSize, id: \.self) { index in
                            Group {
                                if isBlackDisplay {
                                    // Keep row geometry and scroll targets without constructing hidden artwork.
                                    Color.clear.accessibilityHidden(true)
                                } else {
                                    ItemRow(
                                        isSelected: scrollPosition == index,
                                        displayText: formatItemNumber(index - Constants.windowCenter + baseOffset, system: numberSystem),
                                        isAmbientMode: isAmbientMode,
                                        isScrolling: isScrolling
                                    )
                                    .contentShape(Rectangle())
                                    .onTapGesture(count: 2) { openMenu() }
                                    .onTapGesture(count: 1) {
                                        revealMenuButton()
                                        nextPattern()
                                    }
                                    .simultaneousGesture(
                                        LongPressGesture(minimumDuration: 0.5)
                                            .onEnded { _ in openEffectsPicker() }
                                    )
                                }
                            }
                            .frame(maxWidth: .infinity)
                            .frame(height: 40)
                            .id(index)
                        }
                    }
                    .scrollTargetLayout()
                    .padding(.horizontal, 4)
                    .padding(.bottom, 60)
                }
                .scrollPosition(id: $scrollPosition, anchor: .center)
                .scrollIndicators(isBlackDisplay ? .hidden : .automatic)
                .contentShape(Rectangle())
                .simultaneousGesture(
                    TapGesture().onEnded { revealHapticsOnlyControls() },
                    including: isBlackDisplay ? .all : .subviews
                )
                .accessibilityLabel(isBlackDisplay ? "Haptics Only" : "Numbers")
                .accessibilityActions {
                    if isBlackDisplay {
                        Button("Show controls") { revealHapticsOnlyControls() }
                    }
                }
                .scrollTargetBehavior(.viewAligned)
                .onChange(of: scrollPosition) { oldValue, newValue in
                    handleScrollChange(from: oldValue, to: newValue)
                }
                .animation(.easeInOut(duration: 0.3), value: isScrolling)
                .onAppear {
                    // Scroll to center on initial load
                    proxy.scrollTo(Constants.windowCenter, anchor: .center)
                }
            }

            if !isBlackDisplay {
                VStack {
                    HStack {
                        if showMenuButton && !isMenuButtonHidden {
                            menuButton
                                .transition(.opacity)
                        }
                        Spacer()
                    }
                    Spacer()
                }
                .animation(.easeInOut(duration: 0.25), value: showMenuButton)

                // Bottom controls
                VStack(spacing: 6) {
                    Spacer()
                    if showGestureHint && !isAmbientMode {
                        interactionHint
                            .transition(.opacity.combined(with: .move(edge: .bottom)))
                    }
                    controlLabel
                }
            }
        }
        .persistentSystemOverlays(isBlackDisplay ? .hidden : .automatic)
        .sheet(isPresented: $showPatternPicker) {
            PatternPicker(selectedPattern: $currentPattern)
                .onChange(of: currentPattern) { _, newPattern in
                    onPatternChanged(to: newPattern)
                }
        }
        .sheet(isPresented: $showStats) {
            StatsView(stats: stats)
        }
        .sheet(isPresented: $showGuide) {
            InteractionGuideView()
        }
        .sheet(isPresented: $showNumberSystemPicker) {
            NumberSystemPicker(selectedSystem: $numberSystem)
                .onChange(of: numberSystem) { _, newSystem in
                    onNumberSystemChanged(to: newSystem)
                }
        }
        .sheet(isPresented: $showMenu) {
            List {
                Button {
                    dismissMenuThen {
                        showPatternPicker = true
                    }
                } label: {
                    Label("Effects", systemImage: "waveform")
                }
                Button {
                    dismissMenuThen {
                        showNumberSystemPicker = true
                    }
                } label: {
                    HStack {
                        Label("Numbers", systemImage: numberSystem.icon)
                        Spacer()
                        Text(numberSystem.displayName)
                            .font(.system(size: 12))
                            .foregroundColor(.secondary)
                    }
                }
                Button {
                    dismissMenuThen {
                        showStats = true
                    }
                } label: {
                    Label("Statistics", systemImage: "chart.bar")
                }
                Button {
                    dismissMenuThen {
                        showGuide = true
                    }
                } label: {
                    Label("Guide", systemImage: "questionmark.circle")
                }
                Button {
                    toggleMenuIconVisibility()
                    showMenu = false
                } label: {
                    Label(isMenuButtonHidden ? "Show Menu Icon" : "Hide Menu Icon", systemImage: isMenuButtonHidden ? "ellipsis.circle" : "eye.slash")
                }
                Button(role: .destructive) {
                    dismissMenuThen {
                        showResetConfirmation = true
                    }
                } label: {
                    Label("Reset Counter", systemImage: "arrow.counterclockwise")
                }
                Picker(selection: modeSelection) {
                    ForEach(DisplayMode.allCases) { mode in
                        VStack(alignment: .leading, spacing: 2) {
                            HStack(spacing: 6) {
                                Image(systemName: mode.icon)
                                    .frame(width: 20)
                                    .accessibilityHidden(true)
                                Text(mode.displayName)
                                    .lineLimit(1)
                            }
                            Text(mode.detail)
                                .lineLimit(1)
                                .foregroundStyle(.secondary)
                        }
                        .font(.body)
                        .tag(mode)
                    }
                } label: {
                    Text("Mode")
                }
                .accessibilityIdentifier("displayModePicker")
            }
        }
        .onChange(of: showMenu) { _, isPresented in
            if isPresented {
                menuButtonTimer?.invalidate()
            } else {
                revealMenuButton()
            }
        }
        .confirmationDialog("Reset count?", isPresented: $showResetConfirmation) {
            Button(resetButtonTitle, role: .destructive) {
                resetCounter()
            }
            Button("Cancel", role: .cancel) {}
        }
        .onChange(of: isScrolling) { _, spinning in
            if spinning {
                stats.startSpinning()
            } else {
                stats.stopSpinning()
            }
        }
        .onAppear {
            loadSettings()
            revealMenuButton()
            showFirstRunGuideHint()
            stats.startSession()
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                hasInitialized = true
            }
        }
        .onDisappear {
            scrollTimer?.invalidate()
            menuButtonTimer?.invalidate()
            stats.endSession()
        }
        .onChange(of: scenePhase) { _, phase in
            if phase != .active {
                stats.flushPendingPersistence()
            }
        }
    }

    // MARK: - Subviews

    private var interactionHint: some View {
        HStack(spacing: 6) {
            GuideHintItem(icon: "hand.tap", text: "Tap effect")
            GuideHintItem(icon: "hand.point.up.left.fill", text: "Hold effects")
            GuideHintItem(icon: "2.circle", text: "Menu")
        }
        .foregroundColor(.white.opacity(0.86))
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(Color.black.opacity(0.68))
        .overlay(
            Capsule()
                .stroke(Color.white.opacity(0.16), lineWidth: 1)
        )
        .clipShape(Capsule())
        .padding(.horizontal, 6)
    }

    private var controlLabel: some View {
        HStack(spacing: 6) {
            if currentPattern == .random {
                Image(systemName: "dice")
                    .font(.system(size: 14))
                    .foregroundColor(.gray)
                Image(systemName: currentRandomPattern.icon)
                    .font(.system(size: 18))
                Text(currentRandomPattern.displayName)
                    .font(.system(size: 16, weight: .semibold))
            } else {
                Image(systemName: currentPattern.icon)
                    .font(.system(size: 18))
                Text(currentPattern.displayName)
                    .font(.system(size: 16, weight: .semibold))
            }
        }
        .foregroundColor(.white)
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(Color.gray.opacity(isAmbientMode ? 0.2 : 0.4))
        .cornerRadius(20)
        .padding(.bottom, 4)
        .opacity(currentPattern == .random ? 1.0 : (isScrolling ? 0.0 : 1.0))
        .animation(.easeInOut(duration: 0.3), value: isScrolling)
        .onTapGesture(count: 2) {
            openMenu()
        }
        .onLongPressGesture(minimumDuration: 0.5) {
            openEffectsPicker()
        }
        .onTapGesture {
            revealMenuButton()
            nextPattern()
        }
    }

    private var menuButton: some View {
        Button {
            openMenu()
        } label: {
            Image(systemName: "ellipsis.circle")
                .font(.system(size: 21, weight: .semibold))
                .frame(width: 38, height: 38)
                .background(Color.black.opacity(isAmbientMode ? 0.25 : 0.55))
                .clipShape(Circle())
        }
        .buttonStyle(.plain)
        .foregroundColor(.white.opacity(isAmbientMode ? 0.45 : 0.88))
        .accessibilityLabel("Menu")
        .padding(.leading, 6)
    }

    private var resetButtonTitle: String {
        "Reset to \(formatResetTarget(system: numberSystem))"
    }

    // MARK: - Actions

    private func showFirstRunGuideHint() {
        guard !isAmbientMode else { return }
        guard !UserDefaults.standard.bool(forKey: Constants.guideSeenKey) else { return }

        withAnimation(.easeInOut(duration: 0.25)) {
            showGestureHint = true
        }
        UserDefaults.standard.set(true, forKey: Constants.guideSeenKey)

        DispatchQueue.main.asyncAfter(deadline: .now() + 5) {
            withAnimation(.easeInOut(duration: 0.3)) {
                showGestureHint = false
            }
        }
    }

    private func handleScrollChange(from oldValue: Int?, to newValue: Int?) {
        guard let newPos = newValue, newPos != lastPosition else { return }
        lastPosition = newPos

        if hasInitialized {
            if displayModeState.mode == .hapticsOnly && !isBlackDisplay {
                displayModeState.didScroll()
            }
            revealMenuButton()
            triggerHaptic()
            startScrolling()
            checkAndRebalance(newPos)
            let displayNumber = (scrollPosition ?? Constants.windowCenter) - Constants.windowCenter + baseOffset
            stats.recordItemNumber(displayNumber)
        }
    }

    private func startScrolling() {
        isScrolling = true
        if let timer = scrollTimer, timer.isValid {
            // Keep one timer throughout a scrolling burst, with the same idle deadline.
            timer.fireDate = Date(timeIntervalSinceNow: Constants.idleDelay)
            return
        }
        scrollTimer = Timer.scheduledTimer(withTimeInterval: Constants.idleDelay, repeats: false) { _ in
            DispatchQueue.main.async {
                isScrolling = false
                stats.flushPendingPersistence()
                #if canImport(WidgetKit)
                WidgetCenter.shared.reloadAllTimelines()
                #endif
            }
        }
    }

    private func checkAndRebalance(_ position: Int) {
        if position < Constants.rebalanceThreshold || position > Constants.windowSize - Constants.rebalanceThreshold {
            let offsetFromCenter = position - Constants.windowCenter
            baseOffset += offsetFromCenter
            UserDefaults.standard.set(baseOffset, forKey: Constants.baseOffsetKey)
            lastPosition = Constants.windowCenter
            scrollPosition = Constants.windowCenter
        }
    }

    private func nextPattern() {
        let allPatterns = HapticPattern.selectionOrder
        if let currentIndex = allPatterns.firstIndex(of: currentPattern) {
            let nextIndex = (currentIndex + 1) % allPatterns.count
            currentPattern = allPatterns[nextIndex]
        }
        onPatternChanged(to: currentPattern)
    }

    private func onPatternChanged(to pattern: HapticPattern) {
        resetRandomState()
        // Play preview haptic
        if pattern == .random {
            WKInterfaceDevice.current().play(currentRandomPattern.primaryHaptic)
        } else {
            WKInterfaceDevice.current().play(pattern.primaryHaptic)
        }
        saveSettings()
    }

    private func resetRandomState() {
        randomChangeCounter = 0
        randomChangeThreshold = Int.random(in: 3...5)
        currentRandomPattern = HapticPattern.nonRandomPatterns.randomElement() ?? .clicks
    }

    private func triggerHaptic() {
        stats.recordHaptic()

        if currentPattern == .random {
            randomChangeCounter += 1
            if randomChangeCounter >= randomChangeThreshold {
                currentRandomPattern = HapticPattern.nonRandomPatterns.randomElement() ?? .clicks
                randomChangeCounter = 0
                randomChangeThreshold = Int.random(in: 3...5)
            }
            WKInterfaceDevice.current().play(currentRandomPattern.primaryHaptic)
        } else {
            WKInterfaceDevice.current().play(currentPattern.primaryHaptic)
        }
    }

    private func selectDisplayMode(_ mode: DisplayMode) {
        guard mode != displayModeState.mode else { return }
        displayModeState.select(mode)
        mode.save()
        WKInterfaceDevice.current().play(.click)
        showMenu = false
        revealMenuButton()
    }

    private func revealHapticsOnlyControls() {
        guard isBlackDisplay else { return }
        displayModeState.revealControls()
        revealMenuButton()
    }

    private func toggleMenuIconVisibility() {
        isMenuButtonHidden.toggle()
        WKInterfaceDevice.current().play(.click)
        UserDefaults.standard.set(isMenuButtonHidden, forKey: Constants.menuButtonHiddenKey)

        if isMenuButtonHidden {
            menuButtonTimer?.invalidate()
            withAnimation(.easeInOut(duration: 0.2)) {
                showMenuButton = false
            }
        } else {
            revealMenuButton()
        }
    }

    private func openEffectsPicker() {
        revealMenuButton()
        WKInterfaceDevice.current().play(.click)
        showPatternPicker = true
    }

    private func openMenu() {
        menuButtonTimer?.invalidate()
        if !isMenuButtonHidden {
            withAnimation(.easeInOut(duration: 0.2)) {
                showMenuButton = true
            }
        }
        WKInterfaceDevice.current().play(.click)
        showMenu = true
    }

    private func dismissMenuThen(_ action: @escaping () -> Void) {
        showMenu = false
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) {
            action()
        }
    }

    private func resetCounter() {
        baseOffset = 0
        UserDefaults.standard.set(0, forKey: Constants.baseOffsetKey)
        lastPosition = Constants.windowCenter
        scrollPosition = Constants.windowCenter
        // Replace any staged pre-reset number before the next batch is saved.
        stats.recordItemNumber(0)
        stats.flushPendingPersistence()
        revealMenuButton()
    }

    private func onNumberSystemChanged(to system: NumberSystem) {
        WKInterfaceDevice.current().play(.click)
        UserDefaults.standard.set(system.rawValue, forKey: Constants.numberSystemKey)
        Self.sharedDefaults?.set(system.rawValue, forKey: Constants.numberSystemKey)
        stats.flushPendingPersistence()
        #if canImport(WidgetKit)
        WidgetCenter.shared.reloadAllTimelines()
        #endif
        revealMenuButton()
    }

    private func revealMenuButton() {
        guard !isBlackDisplay else {
            menuButtonTimer?.invalidate()
            return
        }
        guard !isMenuButtonHidden else {
            menuButtonTimer?.invalidate()
            withAnimation(.easeInOut(duration: 0.2)) {
                showMenuButton = false
            }
            return
        }

        withAnimation(.easeInOut(duration: 0.2)) {
            showMenuButton = true
        }

        guard !showMenu else {
            menuButtonTimer?.invalidate()
            return
        }
        if let timer = menuButtonTimer, timer.isValid {
            timer.fireDate = Date(timeIntervalSinceNow: Constants.menuAutoHideDelay)
            return
        }
        menuButtonTimer = Timer.scheduledTimer(withTimeInterval: Constants.menuAutoHideDelay, repeats: false) { _ in
            DispatchQueue.main.async {
                guard !showMenu else { return }
                withAnimation(.easeInOut(duration: 0.3)) {
                    showMenuButton = false
                }
            }
        }
    }

    // MARK: - Persistence

    private func loadSettings() {
        if let saved = UserDefaults.standard.string(forKey: Constants.patternKey),
           let pattern = HapticPattern(rawValue: saved) {
            currentPattern = pattern
        }
        displayModeState = DisplayModeState(mode: DisplayMode.load())
        isMenuButtonHidden = UserDefaults.standard.bool(forKey: Constants.menuButtonHiddenKey)
        if isMenuButtonHidden {
            showMenuButton = false
        }
        if let savedSystem = UserDefaults.standard.string(forKey: Constants.numberSystemKey),
           let system = NumberSystem(rawValue: savedSystem) {
            numberSystem = system
        }
        baseOffset = UserDefaults.standard.integer(forKey: Constants.baseOffsetKey)
        // Sync current pattern to shared defaults for the complication
        Self.sharedDefaults?.set(currentPattern.rawValue, forKey: Constants.patternKey)
        Self.sharedDefaults?.set(numberSystem.rawValue, forKey: Constants.numberSystemKey)
    }

    private static let sharedDefaults = UserDefaults(suiteName: appGroupSuiteName)

    private func saveSettings() {
        UserDefaults.standard.set(currentPattern.rawValue, forKey: Constants.patternKey)
        Self.sharedDefaults?.set(currentPattern.rawValue, forKey: Constants.patternKey)
    }
}

// MARK: - Interaction Guide

private struct GuideHintItem: View {
    let icon: String
    let text: String

    var body: some View {
        HStack(spacing: 3) {
            Image(systemName: icon)
                .font(.system(size: 10, weight: .semibold))
            Text(text)
                .font(.system(size: 10, weight: .medium))
                .lineLimit(1)
                .minimumScaleFactor(0.75)
        }
    }
}

private struct InteractionGuideView: View {
    var body: some View {
        List {
            GuideRow(
                icon: "hand.tap",
                title: "Tap effect",
                detail: "Switch to the next haptic."
            )
            GuideRow(
                icon: "hand.point.up.left.fill",
                title: "Long-press",
                detail: "Open the Effects picker."
            )
            GuideRow(
                icon: "2.circle",
                title: "Double-tap",
                detail: "Open the menu."
            )
            GuideRow(
                icon: "ellipsis.circle",
                title: "Menu",
                detail: "Effects, numbers, stats, reset, display mode, and icon visibility."
            )
        }
        .navigationTitle("Guide")
        .navigationBarTitleDisplayMode(.inline)
    }
}

private struct GuideRow: View {
    let icon: String
    let title: String
    let detail: String

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: icon)
                .font(.system(size: 17, weight: .medium))
                .frame(width: 24)
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.system(size: 13, weight: .semibold))
                Text(detail)
                    .font(.system(size: 11))
                    .foregroundColor(.secondary)
                    .lineLimit(2)
            }
        }
        .padding(.vertical, 2)
    }
}

// MARK: - Number System Picker

private struct NumberSystemPicker: View {
    @Binding var selectedSystem: NumberSystem
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        List {
            ForEach(NumberSystem.allCases) { system in
                Button {
                    selectedSystem = system
                    dismiss()
                } label: {
                    HStack(spacing: 8) {
                        Image(systemName: system.icon)
                            .font(.system(size: 17, weight: .medium))
                            .frame(width: 24)
                        Text(system.displayName)
                            .font(.system(size: 13, weight: .semibold))
                        Spacer()
                        if selectedSystem == system {
                            Image(systemName: "checkmark")
                                .font(.system(size: 13, weight: .bold))
                                .foregroundColor(.green)
                        }
                    }
                }
                .buttonStyle(.plain)
            }
        }
        .navigationTitle("Numbers")
        .navigationBarTitleDisplayMode(.inline)
    }
}

// MARK: - ItemRow

struct ItemRow: View {
    let isSelected: Bool
    let displayText: String
    let isAmbientMode: Bool
    let isScrolling: Bool

    private var backgroundOpacity: Double {
        if isScrolling && !isSelected {
            return isAmbientMode ? 0.1 : 0.3
        }
        return 1.0
    }

    var body: some View {
        ZStack {
            // Base background
            RoundedRectangle(cornerRadius: 8)
                .fill(
                    LinearGradient(
                        colors: [
                            Color.white.opacity(isAmbientMode ? 0.03 : 0.06),
                            Color.white.opacity(isAmbientMode ? 0.01 : 0.03)
                        ],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                )
                .opacity(backgroundOpacity)

            // Selection highlight
            if isSelected {
                RoundedRectangle(cornerRadius: 8)
                    .fill(Color.white.opacity(isAmbientMode ? 0.08 : 0.15))
            }

            // Subtle top highlight line (non-selected only)
            if !isSelected {
                VStack {
                    RoundedRectangle(cornerRadius: 1)
                        .fill(Color.white.opacity(isAmbientMode ? 0.05 : 0.1))
                        .frame(height: 1)
                        .padding(.horizontal, 8)
                    Spacer()
                }
                .opacity(backgroundOpacity)
            }

            // Number
            Text(displayText)
                .font(.system(size: isSelected ? 20 : 14, weight: isSelected ? .medium : .regular, design: .rounded))
                .foregroundColor(.white.opacity(isSelected ? (isAmbientMode ? 0.6 : 1.0) : (isAmbientMode ? 0.2 : 0.4)))
                .lineLimit(1)
                .minimumScaleFactor(0.45)
                .padding(.horizontal, 4)
        }
        .frame(maxWidth: .infinity)
        .frame(height: 40)
        .animation(.easeInOut(duration: 0.1), value: isSelected)
        .animation(.easeInOut(duration: 0.3), value: isScrolling)
    }
}

#Preview {
    ContentView()
}
