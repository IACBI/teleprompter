## What this changes

<!-- One or two sentences. What is different after this is merged? -->

## Why

<!-- The problem, or the issue number. "Fixes #12" closes it automatically. -->

## How it was verified

<!-- Tick what applies, and say what you actually did by hand. -->

- [ ] `ruff check . && ruff format --check .`
- [ ] `mypy src/teleprompter/core src/teleprompter/storage`
- [ ] `pytest -q`
- [ ] Ran the application and exercised the change

Manual check:

<!-- e.g. "Loaded a 10k-word script, dragged the font slider, no stutter." -->

## Notes for the reviewer

<!-- Anything surprising, a trade-off you made, or a part you are unsure about.
     Screenshots are welcome for anything visual — before and after if you
     changed something that already existed. -->

---

- [ ] A test covers the behaviour this changes, or the change has no behaviour
- [ ] No new hard-coded colour, size or spacing (they live in `theme/tokens.py`)
- [ ] `core/` and `storage/` still import no Qt
- [ ] New interactive controls have a tooltip and an accessible name
