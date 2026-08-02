# Security policy

## Supported versions

| Version | Supported |
|---|---|
| 2.0.x | ✅ |
| 1.x | ❌ — superseded by 2.0; please upgrade |

## Reporting a vulnerability

Please report privately rather than in a public issue.

Use GitHub's private reporting:
**[Report a vulnerability](https://github.com/IACBI/teleprompter/security/advisories/new)**

You can expect an acknowledgement within a few days, an assessment of severity
and scope, a fix released as a patch version, and credit in the changelog unless
you would rather not be named.

## What this application does with your system

TelePrompter has no network code. It never contacts a server, sends telemetry or
checks for updates. Two optional features reach outside the application window,
and both are **off until you turn them on**:

- **Global shortcuts** install a system-wide keyboard hook through the optional
  `keyboard` package. The hook observes the keyboard stream in order to act on
  two keys; nothing is stored, logged or transmitted. Antivirus tools sometimes
  flag keyboard hooks, because the mechanism is the same one a keylogger uses.
- **Voice-activated scrolling** opens the default microphone through the optional
  `sounddevice` package and reduces each audio block to a single loudness value.
  No audio is buffered, written to disk or sent anywhere.

Full detail, including exactly what is written to disk and how to remove it, is
in [docs/privacy.md](docs/privacy.md).

## Scope

In scope:

- reading or writing files outside the application's own config and log
  directories
- a script's contents causing code, markup or resource loading to be executed or
  fetched — for example through the presenter notes window
- the persistence layer losing or corrupting user data in a way that is not
  reported to the user
- privilege escalation through the optional keyboard hook or audio capture
- a crafted `.txt` or `.pdf` import causing memory exhaustion beyond the
  documented limits, or arbitrary code execution

Out of scope:

- vulnerabilities in PySide6, PyMuPDF, `keyboard` or `sounddevice` themselves —
  please report those upstream; do tell us if TelePrompter uses them in a way
  that makes an upstream issue exploitable
- the documented behaviour of the global keyboard hook when a user has
  deliberately enabled it
- an attacker who already has write access to your config directory or your
  Python environment

## Hardening already in place

- State is written atomically (temp file, flush, `os.replace`) with a backup
  generation, and an unreadable file is reported rather than silently discarded.
- Script imports are bounded: 25 MB of text, 2000 PDF pages, with binary
  detection before decoding.
- User-authored text is rendered as plain text everywhere it is displayed, so
  markup in a script cannot be interpreted or used to load local resources.
- Callbacks from the keyboard hook and the audio thread are marshalled to the GUI
  thread through Qt signals; they never touch a widget directly.
- `pip-audit` runs on every push in CI.
