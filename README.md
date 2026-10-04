# Endless Crown

A discrete Apple Watch fidget app that provides satisfying haptic feedback when rotating the Digital Crown.

## Features

- **Digital Crown Haptics**: Infinite rotation with customizable haptic feedback
- **15 Haptic Effects**: From subtle clicks to complex rhythms
- **Display Modes**: Choose Standard, Ambient, or a black Haptics Only display
- **Quick Launch**: Complication support for one-tap access
- **Eyes-Free Operation**: Switch effects with simple taps

## Haptic Patterns

### Basic Patterns
| Pattern | Description |
|---------|-------------|
| Clicks | Classic clicky feel, high sensitivity |
| Soft | Gentle bumps, medium sensitivity |
| Heavy | Strong thuds, low sensitivity |

### Texture Patterns
| Pattern | Description |
|---------|-------------|
| Buzz | Persistent buzz-like feedback |
| Ping | Bright confirmation-style taps |
| Thud | Dense failure-style feedback |
| Drift | Downward directional feel |
| Pulse | Stopping pulse feedback |

### Rhythm Patterns
| Pattern | Description |
|---------|-------------|
| Heartbeat | Lub-dub pulse pattern |
| Double Tap | Two quick taps per rotation |
| Gallop | Long-short-short rhythm |
| Waltz | 1-2-3 rhythm with emphasis |
| Staccato | Rapid sharp bursts |
| Wave | Intensity builds and fades |
| Random | Unpredictable timing and intensity |

## Usage

1. Rotate the Digital Crown to feel haptic feedback
2. Tap a number or the effect chip to cycle effects
3. Long-press a number or the effect chip to open the Effects picker
4. Double-tap a number or the effect chip to open the menu, which includes Statistics and Reset Counter
5. Choose **Mode** in the menu to select Standard, Ambient, or Haptics Only

Haptics Only hides the app's numbers and controls while preserving scrolling and haptic feedback. Tap the black view to reveal dim controls; the next scroll returns to black. The selected mode is saved, and existing Ambient or Standard (formerly High Contrast) preferences carry over. watchOS may still display its system clock. Battery savings have not been measured.

## Requirements

- watchOS 10.0+
- Apple Watch with Digital Crown

## Building

1. Open `CrownSpin.xcodeproj` in Xcode 15+
2. Select the `CrownSpin Watch App` scheme for simulator/device testing, or the `CrownSpin` scheme for App Store archives
3. Build and run

The public app name is Endless Crown. The Xcode project, schemes, bundle IDs, and targets still use CrownSpin internally so existing signing and App Store provisioning profiles remain valid.

## Project Structure

```
CrownSpin/
├── CrownSpin Watch App/
│   ├── CrownSpinApp.swift      # App entry point
│   ├── ContentView.swift       # Main fidget view
│   ├── DisplayMode.swift       # Display modes and preference migration
│   ├── HapticPattern.swift     # Pattern definitions
│   ├── HapticStats.swift       # Local usage statistics
│   ├── CrownSpinComplication.swift # Complication widget
│   └── Assets.xcassets/        # App assets
├── CrownSpin Complication/    # WidgetKit extension entry point
├── CrownSpinTests/            # Unit tests
└── README.md
```

## Agentic Orchestration

This repository ships with a lightweight agent orchestrator inspired by the agent swarm workflow you outlined. Zoe lives in `.clawdbot/` and handles:

- Prompt synthesis from `README.md` and `AppStoreMetadata.md`.
- Tmux-based agent runs (Codex or Claude).
- Task tracking in `.clawdbot/active-tasks.json`.
- Monitoring (`check-agents.sh`) and cleanup (`cleanup-orphans.sh`).
- OpenClaw notifications when a task reaches your definition of done.

See `docs/agent-swarm.md` for documentation and command examples.

## License

MIT License
