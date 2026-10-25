# Contributing

Thanks for taking the time. This is a small project with a deliberate shape, and
this page explains it so your first change lands cleanly.

## Getting set up

```bash
git clone https://github.com/IACBI/teleprompter.git
cd teleprompter
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
teleprompter                   # or: python -m teleprompter
```

Python 3.10 or newer.

## Before you open a pull request

```bash
ruff check . && ruff format --check .
mypy src/teleprompter/core src/teleprompter/storage
pytest -q
```

CI runs lint and type checks on every push, and the test suite on Windows, macOS
and Linux across Python 3.10, 3.12 and 3.13. A pull request that is red in CI
will not be reviewed until it is green. The failure is usually the review comment
anyway.

## The one rule worth knowing

**`core/` and `storage/` do not import Qt.** Everything that can be decided
without a window lives there: when a pause marker fires, how far the script moves
in 16 milliseconds, what counts as a word, how a line wraps. It is tested with a
fake clock and a fake text measurer, so those tests are fast and deterministic.

Please keep it that way. If you find yourself reaching for `QFontMetrics` inside
`core/`, pass a `measure` callable in instead.

[docs/architecture.md](docs/architecture.md) explains the layout, how the windows
communicate, how threads are marshalled, and how to add a page or a script tag.

## What makes a good pull request

- **One thing at a time.** A bug fix and a refactor in the same diff take three
  times as long to review.
- **A test alongside a behaviour change.** `tests/test_script.py` is usually the
  cheapest place to start. UI wiring goes in `tests/test_ui.py`.
- **Comments that explain *why*.** The code already says what it does. A comment
  earns its place by recording a constraint, a workaround, or something
  surprising.
- **No new colours, sizes or spacings in the UI code.** They come from
  `src/teleprompter/theme/tokens.py`. If a value you need is not there, add it to
  the tokens rather than writing it inline.
- **Accessible controls.** Anything clickable needs a tooltip and an accessible
  name. Colour is never the only way something is communicated.

## Reporting a bug

Please include:

- what you expected and what happened instead
- the script that triggers it, if it depends on the script. A two-line reduction
  is worth more than a whole bulletin.
- your operating system and Python version
- the log file, from **Settings → Diagnostics → Open log folder**

If the application crashed, the error dialog has a **Show Details** button. The
text there is exactly what is useful.

Security issues do not belong in a public issue. Follow the private route in
[SECURITY.md](SECURITY.md).

## Suggesting a feature

Say what you were trying to do, not only what you would like added. A studio
workflow described in two sentences leads to a better feature than a
specification does.

Two things are deliberately out of scope: network features of any kind (the
application has no network code, and that is a property worth keeping), and
teleprompter hardware control protocols.

## Documentation and translations

The README has an English section and a Turkish section in one file. When you
change one, update the other in the same commit. Keep code, commands, paths and
interface strings in English, and translate only the surrounding prose.

The guides in `docs/` are English only.

## Licence

By contributing you agree that your work is licensed under the MIT License, the
same terms as the rest of the project.
