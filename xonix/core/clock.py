"""Fixed-step clock: the simulation advances 60 ticks per second."""

from __future__ import annotations

from xonix import config

MAX_TICKS_PER_FRAME = 10
_EPSILON = 1e-9


class TickClock:
    """Turns real elapsed seconds into a whole number of simulation ticks.

    Logic never depends on the frame rate: whatever dt the loop reports, the
    simulation runs the same number of ticks per second. A long stall is capped
    so that a suspended window does not replay hundreds of ticks at once.
    """

    def __init__(self, tick_rate: int = config.TICKS_PER_SECOND) -> None:
        self.tick_rate = tick_rate
        self.seconds_per_tick = 1.0 / tick_rate
        self._accumulated = 0.0

    def advance(self, dt: float) -> int:
        self._accumulated += dt
        ticks = 0
        while (
            self._accumulated + _EPSILON >= self.seconds_per_tick
            and ticks < MAX_TICKS_PER_FRAME
        ):
            self._accumulated -= self.seconds_per_tick
            ticks += 1
        if ticks == MAX_TICKS_PER_FRAME:
            self._accumulated = 0.0
        return ticks

    def reset(self) -> None:
        self._accumulated = 0.0
