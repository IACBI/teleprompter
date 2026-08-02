"""Interface smoke tests.

These do not check pixels. They check the wiring — that changing a setting
reaches the prompter, that the transport bar reflects playback state, that a
theme switch repaints every window, and that shutdown releases what it owns.
Those are the things that used to break silently when the two windows were
coupled by hand-patched callbacks.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6", reason="the GUI layer needs PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from teleprompter import app as bootstrap
from teleprompter.core.script import BlockKind
from teleprompter.core.transport import PlayState
from teleprompter.state import AppState, PlaybackController
from teleprompter.storage.store import AppData
from teleprompter.theme import DARK, LIGHT, build_stylesheet
from teleprompter.ui.main_window import MainWindow

pytestmark = pytest.mark.gui

SAMPLE = """[CHAPTER One]
The first line of the script goes here.
[[a private note]]

[PAUSE]
[CHAPTER Two]
And the second half continues after the pause.
"""


@pytest.fixture(scope="session")
def qapp():
    application = QApplication.instance() or QApplication([])
    application.setStyle("Fusion")
    yield application


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    """A fully wired control panel that never touches the real config folder."""
    monkeypatch.setattr("teleprompter.storage.paths.config_dir", lambda: tmp_path / "config")
    data = AppData()
    data.last_text = SAMPLE
    state = AppState(data)
    playback = PlaybackController(state)

    panel = MainWindow(state, playback)
    qapp.setStyleSheet(build_stylesheet(DARK, "Arial", "Courier New"))
    panel.apply_palette(DARK, "Arial", "Courier New")
    panel.prompter.resize(800, 500)
    panel.resize(1000, 700)

    yield panel

    panel.shutdown()
    panel.deleteLater()


# ── Wiring ────────────────────────────────────────────────────────────────────
def test_the_panel_and_prompter_both_build(window):
    assert window.prompter is not None
    assert window.notes is not None
    assert len(window.pages) == 6


def test_the_script_reaches_the_prompter_layout(window):
    window.prompter._rebuild_layout()
    assert len(window.prompter._layout.lines) > 0
    assert window.prompter._layout.pause_lines


def test_a_setting_change_reaches_every_page(window):
    window._state.update_settings(font_size=96)
    assert window.display_page.font_size.value() == pytest.approx(96)
    window.prompter._rebuild_layout()
    assert window.prompter._ensure_font().key[1] == 96


def test_changing_the_speed_updates_the_transport_bar(window):
    window._state.update_settings(speed=7.5)
    assert window.transport.speed.value() == pytest.approx(7.5, abs=0.05)


def test_the_transport_bar_follows_playback_state(window):
    window._state.update_settings(countdown_secs=0)
    window._playback.play()
    assert window._playback.state is PlayState.PLAYING
    assert window.transport.play_button.text() == "Pause"
    window._playback.pause()
    assert window.transport.play_button.text() == "Resume"


def test_reset_returns_the_prompter_to_the_top(window):
    window._state.update_settings(countdown_secs=0)
    window._playback.play()
    window._playback.transport.scroll_y = 400.0
    window._playback.reset()
    assert window._playback.scroll_y == 0.0


# ── Chapters ──────────────────────────────────────────────────────────────────
def test_the_outline_lists_the_chapters(window):
    assert window.script_page.outline._list.count() == 2


def test_jumping_to_the_next_chapter_moves_the_prompter(window):
    window.prompter._rebuild_layout()
    window._jump_chapter(1)
    assert window._playback.scroll_y > 0


def test_the_seek_bar_gets_a_tick_per_chapter(window):
    window.transport._refresh_marks()
    assert len(window.transport.seek._marks) == 2


# ── Notes ─────────────────────────────────────────────────────────────────────
def test_notes_are_shown_as_plain_text_not_markup(window):
    """A script must never be able to make QLabel load a local file."""
    window._state.set_script_text('[[<img src="file:///etc/passwd">]]')
    window.prompter._rebuild_layout()
    assert window.notes._current.textFormat() == Qt.TextFormat.PlainText
    assert "<img" in window.notes._all.toPlainText()


def test_notes_reach_the_notes_window(window):
    window.prompter._rebuild_layout()
    assert any("private note" in text for text in window.notes._notes.values())


# ── Theming ───────────────────────────────────────────────────────────────────
def test_switching_to_the_light_theme_repaints_every_window(window, qapp):
    qapp.setStyleSheet(build_stylesheet(LIGHT, "Arial", "Courier New"))
    window.apply_palette(LIGHT, "Arial", "Courier New")
    assert window.prompter._palette is LIGHT
    assert window.notes._palette is LIGHT
    assert window.transport._palette is LIGHT


def test_every_page_survives_being_shown(window):
    for index in range(len(window.pages)):
        window._select_page(index)
        assert window._stack.currentIndex() == index


# ── Accessibility ─────────────────────────────────────────────────────────────
def test_navigation_buttons_carry_accessible_names(window):
    for button in window._nav_buttons:
        assert button.accessibleName()
        assert button.toolTip()


def test_icon_only_buttons_are_named(window):
    for button in window.script_page._buttons.values():
        assert button.accessibleName(), "an icon button with no name is invisible to a reader"
        assert button.toolTip()


def test_transport_controls_are_named(window):
    assert window.transport.play_button.accessibleName()
    assert window.transport.seek.accessibleName()
    assert window.transport.speed.slider.accessibleName()


# ── Privacy defaults ──────────────────────────────────────────────────────────
def test_the_global_keyboard_hook_is_not_installed_by_default(window):
    assert window.hotkeys.active is False


def test_the_microphone_is_not_opened_by_default(window):
    assert window.audio.running is False


# ── Lifecycle ─────────────────────────────────────────────────────────────────
def test_shutdown_stops_the_timers_and_saves(window, tmp_path):
    window.shutdown()
    assert not window._playback._timer.isActive()
    assert not window._autosave.isActive()
    assert (tmp_path / "config" / "state.json").exists()


def test_parsing_survives_a_script_that_is_only_tags(window):
    window._state.set_script_text("[PAUSE]\n[CHAPTER]\n[[note]]")
    kinds = [b.kind for b in window._state.script.blocks]
    assert kinds == [BlockKind.PAUSE, BlockKind.CHAPTER, BlockKind.BLANK]
    window.prompter._rebuild_layout()


def test_the_prompter_paints_an_empty_script_without_crashing(window):
    window._state.set_script_text("")
    window.prompter._rebuild_layout()
    window.prompter.grab()


def test_the_prompter_paints_a_long_script_without_crashing(window):
    window._state.set_script_text("Some words on a line.\n" * 2000)
    window.prompter._rebuild_layout()
    window.prompter.grab()


def test_high_dpi_configuration_is_idempotent(qapp):
    bootstrap._configure_high_dpi()
    bootstrap._configure_high_dpi()


# ── First run ─────────────────────────────────────────────────────────────────
def test_the_welcome_is_skipped_when_a_script_is_already_loaded(window):
    """Never interrupt somebody who restored a session and wants to work."""
    assert not window._state.settings.onboarding_done
    window.maybe_show_welcome()
    assert window._state.settings.onboarding_done


def test_the_welcome_is_not_shown_twice(window):
    window._state.update_settings(onboarding_done=True)
    window.maybe_show_welcome()  # must not block waiting for a dialog
    assert window._state.settings.onboarding_done


def test_the_sample_script_parses_into_every_tag_kind():
    from teleprompter.core.script import parse_script
    from teleprompter.ui.onboarding import SAMPLE_SCRIPT

    script = parse_script(SAMPLE_SCRIPT)
    kinds = {block.kind for block in script.blocks}
    assert BlockKind.PAUSE in kinds
    assert BlockKind.CHAPTER in kinds
    assert script.notes_by_block()
