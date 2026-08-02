"""Persistence and file exchange.

Like :mod:`teleprompter.core`, nothing here imports Qt — the application layer
resolves paths and passes them in, which keeps every code path in this package
directly testable against a ``tmp_path``.
"""
