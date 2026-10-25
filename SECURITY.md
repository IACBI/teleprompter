# Security policy

## Supported versions

| Version | Supported |
|---|---|
| 2.0.x | Yes |
| 1.x | No. Superseded by 2.0; please upgrade. |

## Reporting a vulnerability

Please report security issues privately, not in a public issue. Private
vulnerability reporting is enabled for this repository:

**[Report a vulnerability](https://github.com/IACBI/teleprompter/security/advisories/new)**

You can expect an acknowledgement within a few days, an assessment of severity
and scope, and a fix released as a patch version. You will be credited in the
changelog unless you ask not to be named.

## What the application does with your system

TelePrompter has no network code. It never contacts a server, sends telemetry or
checks for updates. Two optional features reach outside the application window,
and both are **off until you turn them on**:

- **Global shortcuts** install a system-wide keyboard hook through the optional
  `keyboard` package. The hook observes the keyboard stream in order to act on
  two keys; nothing is stored, logged or transmitted. Antivirus tools sometimes
  flag keyboard hooks, because the mechanism is the same one a keylogger uses.
- **Voice detection** opens the default microphone through the optional
  `sounddevice` package and reduces each audio block to a single loudness value.
  No audio is buffered, written to disk or sent anywhere.

The full details, including what is written to disk and how to remove it, are in
[docs/privacy.md](docs/privacy.md).

## Scope

In scope:

- reading or writing files outside the application's own config and log
  directories
- a script's contents causing code, markup or resource loading to be executed or
  fetched, for example through the presenter notes window
- the persistence layer losing or corrupting user data without telling the user
- privilege escalation through the optional keyboard hook or audio capture
- a crafted `.txt` or `.pdf` import causing memory exhaustion beyond the
  documented limits, or arbitrary code execution

Out of scope:

- vulnerabilities in PySide6, PyMuPDF, `keyboard` or `sounddevice` themselves.
  Please report those upstream, and tell us if TelePrompter uses them in a way
  that makes the upstream issue exploitable.
- the documented behaviour of the global keyboard hook when you have turned it on
- an attacker who already has write access to your config directory or your
  Python environment

## Hardening already in place

- State is written atomically (temp file, flush, `os.replace`) with a backup
  copy. An unreadable file is reported rather than silently discarded.
- Script imports are bounded: 25 MB of text, and PDFs of up to 100 MB and 2,000
  pages. Files are checked for binary content before they are decoded.
- A PDF over 100 MB is refused before it is opened, and extraction stops once the
  text passes the 25 MB limit.
- Note parsing runs in linear time, so a crafted line cannot make the editor's
  repaint take quadratic time.
- User-authored text is rendered as plain text everywhere it is displayed, so
  markup in a script cannot be interpreted or used to load local resources.
- Callbacks from the keyboard hook and the audio thread are passed to the GUI
  thread through Qt signals. They never touch a widget directly.
- `pip-audit` runs on every push in CI, against both runtime and development
  dependencies.
