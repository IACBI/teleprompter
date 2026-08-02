from __future__ import annotations

import json

import pytest

from teleprompter.core.settings import RehearsalRun, Settings
from teleprompter.storage.store import (
    MAX_SLOT_CHARS,
    MAX_SLOTS,
    SCHEMA_VERSION,
    AppData,
    LoadProblem,
    import_legacy,
    load,
    save,
)


@pytest.fixture
def state_path(tmp_path):
    return tmp_path / "state.json"


def test_loading_a_missing_file_returns_defaults(state_path):
    result = load(state_path)
    assert result.problem is LoadProblem.MISSING
    assert result.ok
    assert result.data.settings == Settings()


def test_save_then_load_round_trips(state_path):
    data = AppData(settings=Settings(speed=6.5, mirror_y=True), last_text="hello")
    data.save_slot("Opening", "Good evening.")
    save(data, state_path)

    loaded = load(state_path).data
    assert loaded.settings.speed == pytest.approx(6.5)
    assert loaded.settings.mirror_y is True
    assert loaded.last_text == "hello"
    assert loaded.slots["Opening"].text == "Good evening."


def test_save_writes_a_versioned_payload(state_path):
    save(AppData(), state_path)
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert payload["version"] == SCHEMA_VERSION


def test_save_leaves_no_temporary_files_behind(state_path):
    save(AppData(last_text="x"), state_path)
    save(AppData(last_text="y"), state_path)
    assert not list(state_path.parent.glob("*.tmp"))


def test_the_previous_generation_is_kept_as_a_backup(state_path):
    save(AppData(last_text="first"), state_path)
    save(AppData(last_text="second"), state_path)
    backup = state_path.with_suffix(state_path.suffix + ".bak")
    assert json.loads(backup.read_text(encoding="utf-8"))["last_text"] == "first"


def test_a_truncated_file_recovers_from_the_backup(state_path):
    save(AppData(last_text="good"), state_path)
    save(AppData(last_text="newer"), state_path)
    state_path.write_text('{"version": 2, "last_te', encoding="utf-8")  # killed mid-write

    result = load(state_path)
    assert result.problem is LoadProblem.RECOVERED_FROM_BACKUP
    assert result.data.last_text == "good"


def test_both_copies_corrupt_reports_loudly_instead_of_losing_data_silently(state_path):
    backup = state_path.with_suffix(state_path.suffix + ".bak")
    state_path.write_text("{{{", encoding="utf-8")
    backup.write_text("}}}", encoding="utf-8")

    result = load(state_path)
    assert result.problem is LoadProblem.CORRUPT
    assert not result.ok
    assert result.detail


def test_legacy_v1_payload_migrates(tmp_path):
    legacy = tmp_path / ".teleprompter.json"
    legacy.write_text(
        json.dumps({"slots": {"Intro": "Hello there"}, "last_text": "draft"}),
        encoding="utf-8",
    )
    data = import_legacy(legacy)
    assert data is not None
    assert data.slots["Intro"].text == "Hello there"
    assert data.last_text == "draft"
    assert data.settings == Settings()


def test_legacy_import_returns_none_when_absent(tmp_path):
    assert import_legacy(tmp_path / "nothing.json") is None


def test_legacy_import_survives_a_corrupt_file(tmp_path):
    legacy = tmp_path / ".teleprompter.json"
    legacy.write_text("not json", encoding="utf-8")
    assert import_legacy(legacy) is None


def test_from_dict_tolerates_junk():
    assert AppData.from_dict("nonsense").last_text == ""
    assert AppData.from_dict({"slots": "nope"}).slots == {}
    assert AppData.from_dict({"recent_files": [1, "ok", None]}).recent_files == ["ok"]


def test_slot_names_are_trimmed_and_blank_names_rejected():
    data = AppData()
    assert data.save_slot("  Intro  ", "text") is True
    assert "Intro" in data.slots
    assert data.save_slot("   ", "text") is False


def test_oversized_slot_text_is_rejected():
    data = AppData()
    assert data.save_slot("huge", "x" * (MAX_SLOT_CHARS + 1)) is False


def test_slot_count_is_capped():
    data = AppData()
    for i in range(MAX_SLOTS):
        data.save_slot(f"slot{i}", "x")
    assert data.save_slot("one too many", "x") is False
    assert data.save_slot("slot0", "overwrite still works") is True


def test_deleting_a_slot():
    data = AppData()
    data.save_slot("gone", "text")
    assert data.delete_slot("gone") is True
    assert data.delete_slot("gone") is False


def test_recent_files_deduplicate_and_cap():
    data = AppData()
    for i in range(30):
        data.remember_file(f"/scripts/{i}.txt")
    data.remember_file("/scripts/0.txt")
    assert data.recent_files[0] == "/scripts/0.txt"
    assert len(data.recent_files) <= 12
    assert len(set(data.recent_files)) == len(data.recent_files)


def test_rehearsals_are_newest_first_and_capped():
    data = AppData()
    for i in range(40):
        data.add_rehearsal(RehearsalRun(finished_at=str(i), duration_seconds=60, word_count=100))
    assert data.rehearsals[0].finished_at == "39"
    assert len(data.rehearsals) <= 20


def test_rehearsal_average_wpm():
    run = RehearsalRun(finished_at="", duration_seconds=120, word_count=300)
    assert run.average_wpm == 150


def test_rehearsal_average_wpm_without_duration():
    assert RehearsalRun(finished_at="", duration_seconds=0, word_count=10).average_wpm == 0
