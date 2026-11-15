import WidgetKit
import SwiftUI

/// Timeline entry for the complication
struct CrownSpinEntry: TimelineEntry {
    let date: Date
    let totalHaptics: Int
    let currentPattern: String
    let patternIcon: String
    let currentItemNumber: Int
    let numberSystem: NumberSystem
}

/// Provider for complication timeline
struct CrownSpinProvider: TimelineProvider {
    private static let sharedDefaults = UserDefaults(suiteName: appGroupSuiteName)

    func placeholder(in context: Context) -> CrownSpinEntry {
        CrownSpinEntry(date: Date(), totalHaptics: 0, currentPattern: "Clicks", patternIcon: "hand.tap", currentItemNumber: 0, numberSystem: .decimal)
    }

    func getSnapshot(in context: Context, completion: @escaping (CrownSpinEntry) -> Void) {
        let entry = createEntry()
        completion(entry)
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<CrownSpinEntry>) -> Void) {
        let entry = createEntry()
        let nextUpdate = Calendar.current.date(byAdding: .minute, value: 15, to: Date()) ?? Date()
        let timeline = Timeline(entries: [entry], policy: .after(nextUpdate))
        completion(timeline)
    }

    func createEntry() -> CrownSpinEntry {
        let defaults = Self.sharedDefaults
        let totalHaptics = defaults?.integer(forKey: "stats.totalHaptics") ?? 0
        let patternRaw = defaults?.string(forKey: "selectedHapticPattern") ?? "clicks"
        let pattern = HapticPattern(rawValue: patternRaw) ?? .clicks
        // Only the app can migrate its local offset; keep displaying the mirror until then.
        let currentItemNumber = (defaults?.object(forKey: CrownPositionKeys.saved) as? Int)
            ?? defaults?.integer(forKey: CrownPositionKeys.legacyComplication)
            ?? 0
        let numberSystemRaw = defaults?.string(forKey: "numberSystem") ?? NumberSystem.decimal.rawValue
        let numberSystem = NumberSystem(rawValue: numberSystemRaw) ?? .decimal

        return CrownSpinEntry(
            date: Date(),
            totalHaptics: totalHaptics,
            currentPattern: pattern.displayName,
            patternIcon: pattern.icon,
            currentItemNumber: currentItemNumber,
            numberSystem: numberSystem
        )
    }
}

/// Complication views
struct CrownSpinComplicationEntryView: View {
    var entry: CrownSpinEntry
    @Environment(\.widgetFamily) var family

    var body: some View {
        switch family {
        case .accessoryCircular:
            circularView
        case .accessoryRectangular:
            rectangularView
        case .accessoryCorner:
            cornerView
        case .accessoryInline:
            inlineView
        default:
            circularView
        }
    }

    private var circularView: some View {
        ZStack {
            AccessoryWidgetBackground()
            VStack(spacing: 1) {
                Image(systemName: entry.patternIcon)
                    .font(.system(size: 12))
                Text(formatItemNumber(entry.currentItemNumber, system: entry.numberSystem))
                    .font(.system(size: 12, weight: .bold, design: .monospaced))
                    .minimumScaleFactor(0.6)
                Text(formatHapticNumber(entry.totalHaptics))
                    .font(.system(size: 9, design: .rounded))
                    .minimumScaleFactor(0.6)
            }
        }
    }

    private var rectangularView: some View {
        HStack {
            Image(systemName: entry.patternIcon)
                .font(.system(size: 24))
            VStack(alignment: .leading, spacing: 2) {
                Text("Endless Crown")
                    .font(.system(size: 12, weight: .semibold))
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
                Text("Item \(formatItemNumber(entry.currentItemNumber, system: entry.numberSystem))")
                    .font(.system(size: 11, weight: .medium, design: .monospaced))
                    .minimumScaleFactor(0.7)
                Text("\(formatHapticNumber(entry.totalHaptics)) haptics")
                    .font(.system(size: 11))
                    .foregroundColor(.secondary)
            }
            Spacer()
        }
    }

    private var cornerView: some View {
        ZStack {
            Image(systemName: entry.patternIcon)
                .font(.system(size: 20))
        }
        .widgetLabel {
            Text("#\(formatItemNumber(entry.currentItemNumber, system: entry.numberSystem)) · \(formatHapticNumber(entry.totalHaptics))")
        }
    }

    private var inlineView: some View {
        HStack(spacing: 4) {
            Image(systemName: entry.patternIcon)
            Text("#\(formatItemNumber(entry.currentItemNumber, system: entry.numberSystem)) · \(formatHapticNumber(entry.totalHaptics)) haptics")
        }
    }

}

/// The complication widget
struct CrownSpinComplication: Widget {
    let kind: String = "CrownSpinComplication"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: CrownSpinProvider()) { entry in
            CrownSpinComplicationEntryView(entry: entry)
                .containerBackground(.fill.tertiary, for: .widget)
        }
        .configurationDisplayName("Endless Crown")
        .description("Quick access to Endless Crown and view your haptic stats.")
        .supportedFamilies([
            .accessoryCircular,
            .accessoryRectangular,
            .accessoryCorner,
            .accessoryInline
        ])
    }
}

#Preview(as: .accessoryCircular) {
    CrownSpinComplication()
} timeline: {
    CrownSpinEntry(date: Date(), totalHaptics: 1234, currentPattern: "Clicks", patternIcon: "hand.tap", currentItemNumber: 42, numberSystem: .decimal)
}
