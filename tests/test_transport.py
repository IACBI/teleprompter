from __future__ import annotations

import pytest

from teleprompter.core.transport import MAX_DT_MS, PlayState, Transport


def make_transport(total_px=6000.0, line_height=60, pauses=frozenset()) -> Transport:
    transport = Transport()
    transport.set_metrics(total_px, line_height, pauses)
    return transport


def run(transport: Transport, seconds: float, speed: float, *, step_ms: float = 16.0, **kw):
    """Drive the transport with a fake clock."""
    results = []
    for _ in range(int(seconds * 1000 / step_ms)):
        results.append(transport.tick(step_ms, speed, **kw))
    return results


def test_starts_idle():
    transport = make_transport()
    assert transport.state is PlayState.IDLE
    assert transport.countdown_value is None


def test_start_without_countdown_plays_immediately():
    transport = make_transport()
    transport.start(0)
    assert transport.state is PlayState.PLAYING


def test_start_with_countdown_enters_countdown():
    transport = make_transport()
    transport.start(3)
    assert transport.state is PlayState.COUNTDOWN
    assert transport.countdown_value == 3


def test_countdown_counts_down_then_plays():
    transport = make_transport()
    transport.start(2)
    run(transport, 1.0, 2.0, step_ms=100.0)  # exactly one second of ticks
    assert transport.countdown_value == 1
    run(transport, 1.2, 2.0, step_ms=100.0)
    assert transport.state is PlayState.PLAYING


def test_nothing_scrolls_during_the_countdown():
    transport = make_transport()
    transport.start(3)
    run(transport, 1.0, 5.0)
    assert transport.scroll_y == 0.0


def test_scroll_distance_is_frame_rate_independent():
    fast = make_transport()
    fast.start(0)
    run(fast, 1.0, 2.0, step_ms=8.0, ramp_tau=0.0)

    slow = make_transport()
    slow.start(0)
    run(slow, 1.0, 2.0, step_ms=32.0, ramp_tau=0.0)

    assert fast.scroll_y == pytest.approx(slow.scroll_y, rel=0.01)


def test_one_second_at_speed_one_moves_sixty_pixels():
    transport = make_transport()
    transport.start(0)
    run(transport, 1.0, 1.0, ramp_tau=0.0)
    assert transport.scroll_y == pytest.approx(60.0, rel=0.02)


def test_a_stalled_frame_cannot_teleport_the_script():
    transport = make_transport()
    transport.start(0)
    transport.tick(10_000.0, 2.0, ramp_tau=0.0)
    assert transport.scroll_y <= (2.0 / (1000 / 60)) * MAX_DT_MS + 1


def test_pause_stops_movement():
    transport = make_transport()
    transport.start(0)
    run(transport, 0.5, 2.0)
    transport.pause()
    position = transport.scroll_y
    run(transport, 0.5, 2.0)
    assert transport.scroll_y == position


def test_toggle_alternates_play_and_pause():
    transport = make_transport()
    transport.toggle(0)
    assert transport.state is PlayState.PLAYING
    transport.toggle(0)
    assert transport.state is PlayState.PAUSED


def test_toggle_during_countdown_cancels_it():
    transport = make_transport()
    transport.toggle(5)
    assert transport.state is PlayState.COUNTDOWN
    transport.toggle(5)
    assert transport.state is PlayState.PAUSED
    assert transport.countdown_value is None


def test_reset_returns_to_the_top():
    transport = make_transport()
    transport.start(0)
    run(transport, 2.0, 4.0)
    assert transport.reset() is True
    assert transport.scroll_y == 0.0
    assert transport.state is PlayState.IDLE
    assert transport.elapsed_seconds == 0.0


def test_pause_marker_stops_the_scroll_exactly_on_the_line():
    transport = make_transport(line_height=60, pauses=frozenset({5}))
    transport.start(0)
    results = run(transport, 10.0, 4.0, ramp_tau=0.0)
    assert transport.state is PlayState.PAUSED
    assert transport.scroll_y == 300.0
    assert any(r.paused_at_marker for r in results)


def test_playback_can_resume_past_a_pause_marker():
    transport = make_transport(line_height=60, pauses=frozenset({5}))
    transport.start(0)
    run(transport, 10.0, 4.0, ramp_tau=0.0)
    transport.start(0)
    run(transport, 2.0, 4.0, ramp_tau=0.0)
    assert transport.scroll_y > 300.0


def test_reaching_the_end_finishes():
    transport = make_transport(total_px=600.0)
    transport.start(0)
    results = run(transport, 30.0, 4.0, ramp_tau=0.0)
    assert transport.state is PlayState.FINISHED
    assert transport.scroll_y == 600.0
    assert any(r.finished for r in results)


def test_starting_again_after_the_end_rewinds():
    transport = make_transport(total_px=600.0)
    transport.start(0)
    run(transport, 30.0, 4.0, ramp_tau=0.0)
    transport.start(0)
    assert transport.scroll_y == 0.0


def test_progress_tracks_position():
    transport = make_transport(total_px=1000.0)
    transport.seek_to(250.0)
    assert transport.progress == pytest.approx(0.25)


def test_progress_is_zero_without_metrics():
    assert Transport().progress == 0.0


def test_seek_clamps_to_the_script_bounds():
    transport = make_transport(total_px=1000.0)
    transport.seek_to(-500)
    assert transport.scroll_y == 0.0
    transport.seek_to(99999)
    assert transport.scroll_y == 1000.0


def test_seek_to_line_uses_line_height():
    transport = make_transport(line_height=40)
    transport.seek_to_line(7)
    assert transport.scroll_y == 280.0


def test_reflow_preserves_relative_position():
    transport = make_transport(total_px=1000.0, line_height=50)
    transport.seek_to(400.0)  # 40% in
    transport.set_metrics(2000.0, 50, frozenset())
    assert transport.progress == pytest.approx(0.4)


def test_gate_of_zero_holds_the_script_still():
    transport = make_transport()
    transport.start(0)
    run(transport, 2.0, 4.0, ramp_tau=0.0, gate=0.0)
    assert transport.scroll_y == 0.0


def test_ramp_makes_the_start_gradual():
    eased = make_transport()
    eased.start(0)
    run(eased, 0.2, 4.0, ramp_tau=0.5)

    instant = make_transport()
    instant.start(0)
    run(instant, 0.2, 4.0, ramp_tau=0.0)

    assert eased.scroll_y < instant.scroll_y


def test_elapsed_time_only_accumulates_while_playing():
    transport = make_transport()
    transport.start(0)
    run(transport, 1.0, 2.0)
    transport.pause()
    elapsed = transport.elapsed_seconds
    run(transport, 1.0, 2.0)
    assert transport.elapsed_seconds == elapsed
    assert elapsed == pytest.approx(1.0, rel=0.05)
