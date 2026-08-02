"""Pure-Python engine for TelePrompter.

Nothing in this package imports Qt. Every module here is exercised directly by
the test suite, which is why measurement-dependent code (word wrapping) takes an
injected ``measure`` callable rather than reaching for ``QFontMetrics``.
"""
