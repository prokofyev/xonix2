"""Round simulation: fixed tick order, deaths, escalation and the round clock."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field as dataclass_field

from xonix import config
from xonix.core.ball import Ball
from xonix.core.field import Field, State
from xonix.core.player import Player


@dataclass
class RoundResult:
    kind: str
    winner: int | None
    scores: tuple[int, int]
    percents: tuple[float, float]
    lives: tuple[int, int]


@dataclass
class Game:
    player_count: int = 1
    seed: int | None = None
    field: Field = dataclass_field(default_factory=Field)
    players: list[Player] = dataclass_field(default_factory=list)
    balls: list[Ball] = dataclass_field(default_factory=list)
    target_cells: int | None = None
    stage: int = 0
    state: str = "playing"
    result: RoundResult | None = None
    captures: list[tuple[int, int, int]] = dataclass_field(default_factory=list)  # owner, x, y
    _pending: dict[int, tuple[int, int] | None] = dataclass_field(default_factory=dict)
    _rng: random.Random = dataclass_field(default_factory=random.Random, repr=False)

    def __post_init__(self) -> None:
        if self.target_cells is None:
            self.target_cells = round(self.field.playable_cells * config.ROUND_TARGET_RATIO)
        if not self.players:
            self.players = [
                Player(owner=0, x=0, y=self.field.height // 2),
                Player(owner=1, x=self.field.width - 1, y=self.field.height // 2),
            ][: self.player_count]
        for player in self.players:
            # A round started directly (not through reset) still needs a valid
            # respawn anchor: the cell the player is standing on at the start.
            player.anchor = (player.x, player.y)
        if self.seed is not None:
            self._rng.seed(self.seed)
        if not self.balls:
            self.balls = [self._new_ball() for _ in range(config.BALLS_AT_START)]

    def reset(self) -> None:
        self.field.reset()
        starts = [(0, self.field.height // 2), (self.field.width - 1, self.field.height // 2)]
        for player, (x, y) in zip(self.players, starts[: self.player_count], strict=False):
            player.reset(x, y)
        self.stage = 0
        self.state = "playing"
        self.result = None
        self.captures = []
        self._pending.clear()
        self._rng.seed(self.seed)
        self.balls = [self._new_ball() for _ in range(config.BALLS_AT_START)]

    def set_direction(self, player_index: int, direction: tuple[int, int] | None) -> None:
        """Queue a direction; it takes effect on the next tick's input phase."""
        self._pending[player_index] = direction

    def tick(self) -> None:
        if self.state != "playing":
            return
        self.captures = []
        self._apply_input()
        landed = self._move_markers()
        self._move_balls()
        dead = self._resolve_deaths(landed)
        self._fill(landed, dead)
        self._advance_stage()
        self._check_round_end()

    def _apply_input(self) -> None:
        for index, direction in self._pending.items():
            self.players[index].direction = direction
        self._pending.clear()

    def _move_markers(self) -> list[Player]:
        # Decide every marker against the tick's starting state. Applying moves
        # as we go would let the first marker paint a trail the second steps onto
        # in the same tick; judging markers by the cell they commit to also
        # survives the one-tick phase offset between move intervals, so a
        # head-on meeting kills both however the intervals line up.
        collided = self._collided_markers()

        landed: list[Player] = []
        for index, player in enumerate(self.players):
            if index in collided:
                player.alive = False
                continue
            if not player.ready_to_move():
                continue
            target = player.step_target()
            if target == (player.x, player.y):
                if self.field.is_land(player.x, player.y):
                    player.anchor = (player.x, player.y)
                continue
            if not self.field.in_bounds(*target):
                continue
            x, y = target
            cell = self.field.state(x, y)
            if cell == State.TRAIL:
                # A marker that steps onto a trail dies unless that step is a
                # collision: its own trail means a 180 degree turn, a rival's is
                # a mine. The owner is not credited and keeps it.
                player.alive = False
                continue
            player.move_to(x, y)
            if cell == State.SEA:
                self.field.set_trail(x, y, player.owner)
                player.trail.append((x, y))
            else:
                player.landed = True
                player.anchor = (x, y)
                landed.append(player)
        return landed

    def _collided_markers(self) -> set[int]:
        """Indices of markers meeting on a non-land cell this tick.

        Only steered markers take part, so a stopped marker is never killed by
        someone walking into it; that step costs only the mover, exactly as the
        trail rule says. Two steered markers collide when the cells they commit
        to coincide (a head-on meeting, together or one tick apart) or when they
        trade cells (a pass-through). Land is exempt, so markers may share it.
        """
        collided: set[int] = set()
        steered = [
            index
            for index, player in enumerate(self.players)
            if player.direction is not None
            and self.field.in_bounds(*player.step_target())
        ]
        for position, first_index in enumerate(steered):
            first = self.players[first_index]
            first_end = first.step_target()
            for second_index in steered[position + 1 :]:
                second = self.players[second_index]
                second_end = second.step_target()
                if first_end == second_end:
                    if not self.field.is_land(*first_end):
                        collided.add(first_index)
                        collided.add(second_index)
                    continue
                if (
                    first_end == (second.x, second.y)
                    and second_end == (first.x, first.y)
                    and not self.field.is_land(*first_end)
                    and not self.field.is_land(*second_end)
                ):
                    collided.add(first_index)
                    collided.add(second_index)
        return collided

    def _move_balls(self) -> None:
        for ball in self.balls:
            ball.step(self.field)

    def _resolve_deaths(self, landed: list[Player]) -> set[int]:
        """Trail deaths are already flagged; ball contacts are collected here.

        A ball hurt whoever owns the trail it is sitting on. The cell is
        remembered so that a ball idling on a line hurts its owner once, not on
        every tick, and the memory is dropped as soon as the ball leaves the cell.
        """
        dead = {player.owner for player in self.players if not player.alive}
        for ball in self.balls:
            cell = ball.cell()
            on_trail = self.field.state(*cell) == State.TRAIL
            if not on_trail:
                ball.last_hit_cell = None
                continue
            if ball.last_hit_cell == cell:
                continue
            ball.last_hit_cell = cell
            owner = self.field.owner_at(*cell)
            if owner != 0xFF and owner not in dead:
                dead.add(owner)
        for owner in dead:
            player = self.players[owner]
            player.lives -= 1
            self.field.clear_trail(player.trail)
            player.trail = []
            if player.lives > 0:
                player.respawn()
            else:
                player.alive = False
        for player in landed:
            if player.owner in dead:
                player.landed = False
        return dead

    def _fill(self, landed: list[Player], dead: set[int]) -> None:
        ball_cells = [ball.cell() for ball in self.balls]
        for player in landed:
            if player.owner in dead or not player.landed:
                continue
            if self.field.state(player.x, player.y) != State.LAND:
                continue
            captured = self.field.fill(player.trail, ball_cells)
            player.score += len(captured)
            width = self.field.width
            self.captures.extend(
                (player.owner, index % width, index // width) for index in captured
            )
            player.trail = []
            player.landed = False
            player.anchor = (player.x, player.y)

    def _advance_stage(self) -> None:
        while self.stage < len(config.STAGE_THRESHOLDS):
            if self.field.land_ratio() < config.STAGE_THRESHOLDS[self.stage]:
                break
            self.stage += 1
            self.balls.append(self._new_ball())
            speed = config.STAGE_SPEEDS[self.stage]
            for ball in self.balls:
                ball.ticks_per_cell = speed
                ball.accumulator = 0

    def _check_round_end(self) -> None:
        lives = [player.lives for player in self.players]
        exhausted = any(player.lives <= 0 for player in self.players)
        target_reached = self.field.land_count >= self.target_cells
        if not exhausted and not target_reached:
            return
        scores = tuple(player.score for player in self.players)
        percents = self._percents()
        if self.player_count < 2:
            self.state = "finished"
            self.result = RoundResult(
                "defeat" if exhausted else "target",
                None if exhausted else 0,
                scores,
                percents,
                tuple(lives),
            )
            return
        if exhausted:
            alive = [player for player in self.players if player.lives > 0]
            winner = self.players.index(alive[0]) if len(alive) == 1 else None
            kind = "lives"
        elif scores[0] == scores[1]:
            winner = None
            kind = "target"
        else:
            winner = 0 if scores[0] > scores[1] else 1
            kind = "target"
        self.state = "finished"
        self.result = RoundResult(kind, winner, scores, percents, tuple(lives))

    def _percents(self) -> tuple[float, float]:
        percents = []
        for player in self.players:
            percents.append(100.0 * player.score / self.field.playable_cells)
        while len(percents) < 2:
            percents.append(0.0)
        return (percents[0], percents[1])

    def _new_ball(self) -> Ball:
        cells = self.field.sea_components()
        dx, dy = self._new_ball_direction()
        speed = config.STAGE_SPEEDS[self.stage]
        if not cells:
            return Ball(x=0, y=0, dx=dx, dy=dy, ticks_per_cell=speed)
        main = cells[0]
        markers = [(player.x, player.y) for player in self.players]
        far = [
            cell
            for cell in main
            if self._min_distance(cell, markers) >= config.SPAWN_MIN_DISTANCE
        ]
        if far:
            x, y = self._rng.choice(far)
        else:
            x, y = max(main, key=lambda cell: self._min_distance(cell, markers))
        return Ball(x=x, y=y, dx=dx, dy=dy, ticks_per_cell=speed)

    def _new_ball_direction(self) -> tuple[int, int]:
        """One of the four diagonals, so no side starts with an edge.

        Every ball used to be born heading right, which meant three of them
        converged on the second player before the first one saw any pressure.
        The choice comes from the round's seeded RNG, so a seeded round stays
        reproducible while the four directions remain equally likely.
        """
        return self._rng.choice(config.BALL_DIRECTIONS)

    @staticmethod
    def _min_distance(cell: tuple[int, int], markers: list[tuple[int, int]]) -> float:
        return min(math.dist(cell, marker) for marker in markers)
