"""Utilities shared by the simulation tests."""

from __future__ import annotations

from xonix.core.ball import Ball
from xonix.core.field import Field, State
from xonix.core.game import Game


def make_field(width: int = 20, height: int = 12) -> Field:
    """A small field that mirrors the real start layout: land rim, sea inside."""
    return Field(width=width, height=height)


def carve_land(field: Field, cells) -> None:
    for x, y in cells:
        field.cells[field.index(x, y)] = State.LAND


def make_game(width: int = 20, height: int = 12, player_count: int = 1, seed: int = 7) -> Game:
    field = Field(width=width, height=height)
    return Game(player_count=player_count, seed=seed, field=field)


def park_ball(game: Game, x: int, y: int) -> Ball:
    """A ball that never moves; it only keeps the sea reachable for the fill rule."""
    ball = Ball(x=x, y=y, dx=1, dy=1, ticks_per_cell=10**6)
    game.balls = [ball]
    return ball


def run(game: Game, ticks: int) -> None:
    for _ in range(ticks):
        game.tick()


def land_area(game: Game, count: int) -> None:
    """Make ``count`` sea cells land, the way captured territory would be."""
    field = game.field
    added = 0
    for y in range(1, field.height - 1):
        for x in range(1, field.width - 1):
            if added >= count:
                return
            if field.is_sea(x, y):
                field.cells[field.index(x, y)] = State.LAND
                field.land_count += 1
                added += 1


def stage_for(game: Game, stage: int) -> None:
    """Push the field past the given stage threshold without moving any marker."""
    from xonix import config

    needed = int(-(-game.field.playable_cells * config.STAGE_THRESHOLDS[stage] // 1))
    land_area(game, needed)
