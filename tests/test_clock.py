import pytest

from xonix.core.clock import MAX_TICKS_PER_FRAME, TickClock


@pytest.mark.parametrize("frame_rate", [10, 30, 60, 144])
def test_one_second_is_always_sixty_ticks(frame_rate):
    clock = TickClock()
    ticks = sum(clock.advance(1.0 / frame_rate) for _ in range(frame_rate))
    assert ticks == 60


def test_fractional_frames_do_not_drift():
    clock = TickClock()
    ticks = sum(clock.advance(0.007) for _ in range(1000))
    assert ticks == 420


def test_long_stall_is_capped():
    clock = TickClock()
    assert clock.advance(10.0) == MAX_TICKS_PER_FRAME
    assert clock.advance(0.0001) == 0


def test_reset_drops_pending_time():
    clock = TickClock()
    clock.advance(0.01)
    clock.reset()
    assert clock.advance(0.01) == 0
