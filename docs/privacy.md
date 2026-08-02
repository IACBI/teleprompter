# Privacy and system access

TelePrompter has no network code. It never contacts a server, collects
telemetry, or checks for updates. Two optional features do reach outside the
application window, and both are off until you turn them on.

## Global shortcuts

**Off by default. Settings → Global shortcuts.**

When enabled, the optional `keyboard` package installs a low-level operating
system keyboard hook so that <kbd>Space</kbd> and <kbd>R</kbd> reach the
prompter even when another application has focus.

What this means in practice:

- **The hook observes the whole keyboard stream.** That is how any global
  shortcut works. TelePrompter acts on two keys and ignores everything else; it
  does not store, log or transmit keystrokes. The capability is still there,
  which is why the feature is opt-in and says so on the page.
- **Those two keys are claimed everywhere.** Pressing <kbd>Space</kbd> in a
  browser or a document will control the prompter instead. Turn the feature off
  when you are not on air.
- **Antivirus and endpoint-protection tools may flag it.** A keyboard hook is
  the same mechanism a keylogger uses, and scanners cannot tell intent from
  mechanism. This is expected.
- **The hook is released** when you switch the feature off and when the
  application quits.
- **On Linux** it usually needs permission to read input devices, which often
  means running with elevated privileges. Consider whether that trade is worth
  it for your setup.

If the `keyboard` package is not installed, the feature is simply unavailable
and no hook can be created.

## Voice-activated scrolling

**Off by default. Voice page.**

When enabled, the optional `sounddevice` package opens the default microphone
and computes a short-term loudness value roughly twenty times a second. The
script scrolls while you speak and waits while you do not.

- **Audio is never recorded.** No buffer is retained, nothing is written to
  disk, nothing leaves the machine. A single floating-point loudness number is
  kept in memory and overwritten on the next block.
- **The device is released** the moment you switch the feature off, and on quit.
- **macOS will show its own microphone permission prompt** the first time, as it
  does for any application.

## What is stored on disk

| What | Where |
|---|---|
| Settings, saved scripts, last script, rehearsal history | `state.json` in the app config folder |
| A single previous generation of that file | `state.json.bak` beside it |
| Rotating diagnostic log, capped at 3 × 2 MB | the app log folder |

Both folders can be opened from **Settings → Diagnostics**. Nothing is written
anywhere else.

The log records application events and any error traceback. It contains no
script text.

## Removing everything

Delete the two folders shown on the Settings page. There are no registry keys,
no hidden state, and no leftover services.
