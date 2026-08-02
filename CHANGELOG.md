# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] — 2026-08-02

A full rebuild. The application does everything the 1.x single file did, and the
parts that used to be fragile are no longer fragile.

### Added

- **Multi-screen output.** Send the prompter to any connected display and put it
  full screen, from the Prompter page or with <kbd>F11</kbd>. The chosen screen
  is remembered, and unplugging it falls back safely.
- **Chapters.** `[CHAPTER Title]` markers build an outline beside the editor,
  tick the progress bar, show in the prompter's corner readout and are reachable
  with <kbd>Ctrl</kbd>+<kbd>←</kbd> / <kbd>Ctrl</kbd>+<kbd>→</kbd>.
- **Timing and rehearsal.** Enter the length of your slot to see the required
  words-per-minute, watch a live ahead / on-track / behind badge, and keep a
  history of completed run-throughs broken down by chapter.
- **Vertical mirroring** alongside horizontal, for rigs that reflect off an
  overhead mirror.
- **Speed ramping.** Playback eases into the target speed instead of snapping to
  it; switchable back to instant on the Prompter page.
- **A persistent transport bar** — play, rewind, chapter skip, speed, progress,
  elapsed, remaining, WPM and pace are visible on every page.
- **A click-to-seek progress bar** with chapter ticks, operable from the
  keyboard.
- **Script editor** with line numbers, tag syntax highlighting and a marker that
  follows the line being read.
- **Recent files, named script slots with timestamps, and periodic autosave.**
- **A light interface theme**, and a real crash dialog that points at the log.

### Changed

- **Migrated from PyQt5 to PySide6.** Automatic high-DPI handling with
  pass-through scale-factor rounding, so a 150% display is no longer rendered at
  200%. LGPL licensing also fits this project's MIT terms better.
- **Rebuilt as a package** (`src/teleprompter/`) with a Qt-free engine in
  `core/` and `storage/`. Installs with `pip install .` and runs as
  `teleprompter`.
- **Replaced the tab layout** with a navigation rail, cards and pages. The
  Display tab's eleven ungrouped rows are now three grouped cards.
- **The Advanced tab is gone.** It listed the application's own performance
  features; the Settings page in its place holds real settings — global shortcut
  consent, interface theme, diagnostics, reset and about.
- **Themes now restyle the whole application**, not just the prompter canvas. A
  light prompter preset no longer sits beside a permanently dark control panel.
- **Every colour, spacing step, radius and font size** comes from one token file
  and one generated stylesheet.
- **Emoji button labels replaced with vector icons** that scale cleanly and are
  paired with real accessible names.
- **The prompter render was rewritten**: rounded chrome with a soft edge, a
  smoothstep distance fade, a gradient focus band, a word highlight that sweeps
  rather than jumps, a designed pause chip, an animated countdown ring, and a
  quiet corner readout.
- **Alignment no longer forces a re-wrap** — word offsets are stored relative to
  the line, so switching alignment only moves the line origin.
- **WPM is now dimensionally correct.** The previous formula was off by a factor
  of about 16.7, which put every reading in the lowest colour band.
- **The prompter is dragged by a handle strip** at the top instead of by its
  whole surface, so a mis-click during a read cannot move the window.
- **Notifications are non-blocking toasts**; only genuinely blocking questions
  stay modal.
- **State moved** from `~/.teleprompter.json` to the platform config directory,
  with automatic one-time migration of 1.x scripts and slots.

### Fixed

- **Saving is atomic.** State is written to a temp file, flushed, and moved into
  place, with the previous copy kept as `.bak`. A crash mid-write no longer
  silently erases every saved script — and if both copies are unreadable, the
  app says so instead of starting empty.
- **Global hotkey callbacks no longer touch Qt objects from a foreign thread.**
  The `keyboard` listener emits a signal that Qt delivers to the GUI thread.
- **Global hotkeys are opt-in.** Previously the system-wide keyboard hook was
  installed automatically, so pressing Space in any other application controlled
  the prompter.
- **Presenter notes are rendered as plain text.** A note containing markup could
  previously be interpreted as rich text by `QLabel`, which allows local
  resource loading through `<img src="file://…">`.
- **File import is bounded.** A 25 MB text limit, a 2000-page PDF limit, binary
  detection (a renamed video no longer loads as mojibake) and BOM-aware UTF-16
  decoding, with a warning when an encoding had to be guessed.
- **Long unbreakable words wrap.** A token wider than the column is split with a
  binary search instead of producing one infinitely wide line.
- **Every window cleans up after itself.** Timers, the microphone stream and the
  keyboard hook are released on quit, and only this application's hotkeys are
  removed rather than every hotkey in the process.
- **Failures are visible.** Six silent `except: pass` blocks became logged
  warnings; there is a rotating log file, a `sys.excepthook`, a
  `threading.excepthook` and a crash dialog. The hotkey page reports the real
  registration result instead of a hard-coded "Active".
- **Word count no longer drops words containing `[`.**

### Performance

Measured on a 10,000-word script at 1200×800, software raster backend:

- Full re-wrap: ~11 ms, coalesced so a slider drag re-wraps once instead of on
  every tick.
- Frame paint: 3.3 ms median, 3.7 ms at the 95th percentile.
- Word x-positions are computed during layout, glyph layout is cached per line
  in a `QStaticText`, the window chrome is cached as a pixmap, and the word count
  behind the WPM readout is computed once per script rather than several times a
  second.

### Security

- No network code anywhere in the application.
- Microphone audio is reduced to a loudness value and never retained.
- Both privileged features are documented in `docs/privacy.md`, including why
  antivirus software may flag the keyboard hook.
- `pip-audit` runs in CI.

## [1.0.0]

The original single-file PyQt5 application, kept for reference in `legacy/`.
