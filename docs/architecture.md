# Architecture

For contributors. The short version: the engine knows nothing about Qt, and the
windows know nothing about each other.

```
src/teleprompter/
├── core/          pure Python — no Qt import anywhere
│   ├── script.py      tag parsing → an immutable Script
│   ├── layout.py      word wrapping, with measurement injected
│   ├── timing.py      speed, WPM, pace and duration mathematics
│   ├── transport.py   the playback state machine
│   └── settings.py    the settings model, and every bound in the app
├── storage/       persistence and file exchange — also Qt-free
│   ├── paths.py       platform config and log directories
│   ├── store.py       atomic JSON with a backup generation
│   └── importers.py   .txt and .pdf loading, with limits
├── theme/         design tokens → one generated stylesheet
├── services/      OS bridges: keyboard hook, microphone, logging
├── state.py       AppState and PlaybackController — the only shared state
├── resources/     icons, drawn at runtime
└── ui/            windows, pages and widgets
```

## Why the core is Qt-free

Every rule that matters — when a pause marker fires, how far a script moves in
16 milliseconds, what counts as a word — is in `core/`, exercised by the test
suite with a fake clock and a fake text measurer. No `QApplication` is needed to
prove the engine correct, so those tests run in milliseconds and never flake.

`layout.build_layout` takes a `measure` callable. The prompter passes
`QFontMetricsF.horizontalAdvance`; the PDF exporter passes its own
printer-resolution metric; the tests pass "every character is ten wide". One
wrapping algorithm, three callers.

## How things communicate

Everything goes through Qt signals from `state.py`:

- **`AppState`** owns the settings, the parsed script and everything that
  persists. Widgets call `state.update_settings(...)` and react to
  `settingsChanged`. Validation happens once, inside `core/settings.py`.
- **`PlaybackController`** drives the pure `Transport` from a `QTimer`, measuring
  real elapsed milliseconds so scrolling is frame-rate independent. It emits
  position, progress, WPM and pace.

No window holds a reference to another window's widgets. That is what makes it
possible to add a page, or a second prompter output, without touching the rest.

## Threads

Two things arrive from foreign threads, and both are converted to signals before
they touch a widget:

- `services/hotkeys.py` — the `keyboard` listener thread emits `triggered`, which
  Qt delivers to the GUI thread through a queued connection.
- `services/audio.py` — PortAudio's realtime callback writes one float. A
  `QTimer` on the GUI thread reads it and emits.

Calling a widget method from either of those threads directly would be a Qt
thread-affinity violation. Nothing here does.

## Rendering

The prompter paints itself rather than hosting a text widget, because the focus
band, the distance fade, the per-word sweep and the mirror transform are all one
pass over the visible lines.

Cost per frame is proportional to the number of visible lines, never to the
length of the script:

- wrapping runs only when the text, width or font changes, and is coalesced by a
  45 ms timer so dragging a slider does not re-wrap on every tick
- visible line indices are computed arithmetically, never by scanning
- each line's glyph layout is cached in a `QStaticText`
- the rounded window chrome is rendered once into a pixmap

On a 10,000-word script that is roughly 11 ms for a full re-wrap and 3.3 ms per
frame, measured on the software raster backend.

## Adding a settings page

1. Subclass `ui/pages/base.Page`, set `TITLE` and `ICON`.
2. Build `Card`s in `__init__`, call `self.finish()`.
3. Implement `sync(settings)` to push values into widgets, wrapped in
   `with self.guard():` so change handlers do not fire.
4. Implement `on_palette(...)` for anything that paints itself.
5. Register it in `MainWindow._build_pages`.

## Adding a script tag

1. Add the pattern and a `BlockKind` in `core/script.py`.
2. Handle the new kind in `core/layout.build_layout`.
3. Draw it in `PrompterWindow._paint_script` and in `ui/export.py`.
4. Colour it in `ui/widgets/editor.TagHighlighter`.
5. Write the tests first — `tests/test_script.py` is the cheapest place to work.
