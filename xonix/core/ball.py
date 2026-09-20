"""Balls: they bounce off land and kill whoever owns the trail they touch."""

from __future__ import annotations

from dataclasses import dataclass

from xonix.core.field import Field


@dataclass
class Ball:
    x: int
    y: int
    dx: int
    dy: int
    ticks_per_cell: int
    accumulator: int = 0
    last_hit_cell: tuple[int, int] | None = None

    def step(self, field: Field) -> bool:
        """Advance one cell per ``ticks_per_cell`` ticks, bouncing off land.

        Returns whether the ball entered a new cell this tick. The two axes are
        resolved independently, so a ball hugging a wall slides along it instead
        of jittering against it. A blocked axis reverses its direction and does
        not move this tick, which keeps the ball next to the wall it bounced off.
        """
        self.accumulator += 1
        if self.accumulator < self.ticks_per_cell:
            return False
        self.accumulator = 0

        px, py = self.dx, self.dy
        next_x = self.x + px
        next_y = self.y + py
        blocked_x = not field.in_bounds(next_x, self.y) or field.is_land(next_x, self.y)
        blocked_y = not field.in_bounds(self.x, next_y) or field.is_land(self.x, next_y)
        hits_corner = not field.in_bounds(next_x, next_y) or field.is_land(next_x, next_y)
        if not blocked_x and not blocked_y and hits_corner:
            blocked_x = blocked_y = True

        if blocked_x:
            self.dx = -px
        if blocked_y:
            self.dy = -py
        new_x = self.x if blocked_x else self.x + px
        new_y = self.y if blocked_y else self.y + py
        moved = (new_x, new_y) != (self.x, self.y)
        self.x, self.y = new_x, new_y
        return moved

    def cell(self) -> tuple[int, int]:
        return self.x, self.y
