"""The tick's phase order: markers, balls, deaths, fill, stages, round end."""

import math

from tests.helpers import carve_land, land_area, make_game, park_ball, run
from xonix import config
from xonix.core.ball import Ball
from xonix.core.field import State


def test_deaths_are_resolved_before_the_fill():
    """A player killed while landing must not bank the capture of that tick."""
    game = make_game(width=40, height=24, player_count=1)
    player = game.players[0]
    carve_land(game.field, [(x, 12) for x in range(1, 4)])
    carve_land(game.field, [(6, 12)])
    player.x, player.y = 3, 12
    player.anchor = (3, 12)

    # On the same tick the marker lands on (6, 12), a ball drops into the
    # marker's own trail at (4, 12). The death is resolved first, so the landing
    # never banks a capture.
    row = [game.field.index(x, 12) for x in (4, 5)]
    game.balls = [Ball(x=4, y=11, dx=0, dy=1, ticks_per_cell=3 * config.PLAYER_TICKS_PER_CELL)]
    game.set_direction(0, (1, 0))
    run(game, 3 * config.PLAYER_TICKS_PER_CELL)

    assert (player.x, player.y) == (6, 12)
    assert player.lives == config.START_LIVES - 1
    assert player.score == 0
    assert all(game.field.cells[index] == State.SEA for index in row)


def test_the_first_player_takes_a_contested_area():
    """Both players close the same basin in one tick; the first player takes it."""
    game = make_game(width=40, height=24, player_count=2)
    game.balls = []
    field = game.field
    carve_land(field, [(x, 6) for x in range(10, 26)])
    carve_land(field, [(x, 14) for x in range(10, 26)])
    carve_land(field, [(26, y) for y in range(5, 16)])
    carve_land(field, [(25, y) for y in range(6, 15) if y != 10])

    first, second = game.players
    first.x, first.y = 10, 7
    first.anchor = (10, 7)
    trail_cells = [(10, y) for y in range(7, 14)]
    first.trail = list(trail_cells)
    for cell in trail_cells:
        field.set_trail(*cell, owner=0)
    second.x, second.y = 25, 10
    second.anchor = (25, 10)
    second.trail = [(25, 10)]
    field.set_trail(25, 10, owner=1)

    park_ball(game, 37, 21)
    game.set_direction(0, (0, -1))
    game.set_direction(1, (1, 0))
    run(game, config.PLAYER_TICKS_PER_CELL)

    basin = [(x, y) for x in range(11, 25) for y in range(7, 14)]
    assert all(field.state(x, y) == State.LAND for x, y in basin)
    assert first.score == len(basin) + len(trail_cells)
    assert second.score == 1, "the second player only banks its own trail"


def test_stage_change_happens_after_the_fill_of_the_same_tick():
    game = make_game(width=60, height=40, player_count=1)
    game.balls = [Ball(x=30, y=20, dx=1, dy=1, ticks_per_cell=config.STAGE_SPEEDS[0])]
    needed = math.ceil(game.field.playable_cells * config.STAGE_THRESHOLDS[0])

    land_area(game, needed)
    game.tick()

    assert game.stage == 1
    assert len(game.balls) == 2
    assert all(ball.ticks_per_cell == config.STAGE_SPEEDS[1] for ball in game.balls)


def test_a_landing_player_is_credited_before_the_round_check():
    game = make_game(width=40, height=24, player_count=1)
    park_ball(game, 37, 21)
    player = game.players[0]
    carve_land(game.field, [(x, 12) for x in range(1, 4)])
    carve_land(game.field, [(6, 12)])
    player.x, player.y = 3, 12
    player.anchor = (3, 12)
    game.set_direction(0, (1, 0))
    run(game, 2 * config.PLAYER_TICKS_PER_CELL)
    assert player.score == 0

    game.field.land_count = game.target_cells - 2
    run(game, config.PLAYER_TICKS_PER_CELL)

    assert player.score == 2
    assert game.state == "finished"
    assert game.result is not None
    assert game.result.kind == "target"
    assert game.result.winner == 0
