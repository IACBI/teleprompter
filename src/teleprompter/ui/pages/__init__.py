"""Settings pages shown in the control panel's content area."""

from .audio_page import AudioPage
from .base import Page
from .display_page import DisplayPage
from .prompter_page import PrompterPage
from .script_page import ScriptPage
from .settings_page import SettingsPage
from .timing_page import TimingPage

__all__ = [
    "AudioPage",
    "DisplayPage",
    "Page",
    "PrompterPage",
    "ScriptPage",
    "SettingsPage",
    "TimingPage",
]
