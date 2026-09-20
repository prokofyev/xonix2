"""A player: marker, trail, lives, score and respawn anchor."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field

from xonix import config


@dataclass
class Player:
    owner: int
    x: int
    y: int
    direction: tuple[int, int] | None = None
    lives: int = config.START_LIVES
    score: int = 0
    trail: list[tuple[int, int]] = dataclass_field(default_factory=list)
    anchor: tuple[int, int] = (0, 0)
    accumulator: int = 0
    alive: bool = True
    landed: bool = False

    @property
    def in_sea(self) -> bool:
        return bool(self.trail)

    def reset(self, x: int, y: int) -> None:
        self.x = x
        self.y = y
        self.direction = None
        self.lives = config.START_LIVES
        self.score = 0
        self.trail = []
        self.anchor = (x, y)
        self.accumulator = 0
        self.alive = True
        self.landed = False

    def respawn(self) -> None:
        self.x, self.y = self.anchor
        self.direction = None
        self.trail = []
        self.accumulator = 0
        self.landed = False
        self.alive = True

    def ready_to_move(self) -> bool:
        """The marker moves one cell every ``PLAYER_TICKS_PER_CELL`` ticks."""
        if self.direction is None:
            return False
        self.accumulator += 1
        if self.accumulator < config.PLAYER_TICKS_PER_CELL:
            return False
        self.accumulator = 0
        return True

    def step_target(self) -> tuple[int, int]:
        if self.direction is None:
            return self.x, self.y
        return self.x + self.direction[0], self.y + self.direction[1]

    def move_to(self, x: int, y: int) -> None:
        self.x = x
        self.y = y
