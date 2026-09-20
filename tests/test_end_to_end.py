"""Scripted rounds on the real 120x80 field, with no window involved."""

from tests.helpers import make_game, park_ball, run
from xonix import config
from xonix.core.ball import Ball
from xonix.core.field import State
from xonix.core.game import Game


def walk(game: Game, index: int, direction: tuple[int, int], steps: int) -> None:
    """Hold a direction for exactly ``steps`` marker moves, then stop."""
    game.set_direction(index, direction)
    run(game, steps * config.PLAYER_TICKS_PER_CELL)
    game.set_direction(index, None)


def quiet_round(seed: int = 11, player_count: int = 1) -> Game:
    """A real field with one distant, motionless ball.

    Without any ball at all the whole sea is unreachable, so the first landing
    would capture everything. A parked ball keeps the open sea alive while the
    script describes geometry rather than luck.
    """
    game = Game(player_count=player_count, seed=seed)
    park_ball(game, config.FIELD_WIDTH - 10, config.FIELD_HEIGHT - 10)
    return game


def test_a_real_round_starts_from_the_documented_layout():
    game = Game(player_count=1, seed=11)

    assert game.field.width == config.FIELD_WIDTH
    assert game.field.height == config.FIELD_HEIGHT
    assert game.field.land_count == 0
    assert game.field.playable_cells == config.PLAYABLE_CELLS
    assert game.target_cells == config.ROUND_TARGET_CELLS
    assert len(game.balls) == config.BALLS_AT_START
    for ball in game.balls:
        assert game.field.is_sea(ball.x, ball.y)
        assert abs(ball.x - game.players[0].x) + abs(ball.y - game.players[0].y) > 0
    player = game.players[0]
    assert player.anchor == (player.x, player.y)
    assert player.lives == config.START_LIVES


def test_a_detour_into_the_sea_captures_the_cut_off_area():
    game = quiet_round()
    player = game.players[0]
    assert player.x == 0

    walk(game, 0, (1, 0), 20)
    assert player.in_sea
    assert len(player.trail) == 20

    walk(game, 0, (0, -1), 40)

    assert not player.in_sea
    assert player.score == 20 * 40
    assert game.field.land_count == player.score
    captured = [(x, y) for x in range(1, 20) for y in range(1, 40)]
    assert all(game.field.state(x, y) == State.LAND for x, y in captured)
    assert all(game.field.state(x, y) == State.SEA for x, y in [(30, 10), (60, 60)])


def test_the_top_rim_closes_a_loop_like_any_other_land():
    game = quiet_round(seed=3)
    player = game.players[0]

    walk(game, 0, (1, 0), 100)
    walk(game, 0, (0, -1), 40)

    assert not player.in_sea
    assert player.score == 100 * 40
    assert all(
        game.field.state(x, y) == State.LAND for x in range(1, 100) for y in range(1, 40)
    )


def test_a_pocket_bite_captures_only_the_piece_without_a_ball():
    game = quiet_round(seed=5)
    field = game.field
    player = game.players[0]

    walk(game, 0, (1, 0), 20)
    walk(game, 0, (0, -1), 40)
    assert player.score == 800

    # A ball sits inside a walled pocket in the lower middle. Biting the strip
    # above it must pay for every cell that is not part of the ball's pocket.
    for x in range(30, 50):
        field.cells[field.index(x, 60)] = State.LAND
        field.cells[field.index(x, 70)] = State.LAND
    for y in range(61, 70):
        field.cells[field.index(30, y)] = State.LAND
        field.cells[field.index(49, y)] = State.LAND
    game.balls = [
        *game.balls,
        Ball(x=40, y=65, dx=1, dy=1, ticks_per_cell=config.STAGE_SPEEDS[0]),
    ]

    player.x, player.y = 0, 60
    player.anchor = (0, 60)
    walk(game, 0, (1, 0), 20)
    walk(game, 0, (0, 1), 20)

    assert not player.in_sea
    gained = player.score - 800
    assert gained == game.field.land_count - 800
    assert gained > 20, "the trail itself must be paid for"
    assert all(field.state(x, y) == State.LAND for x in range(1, 20) for y in range(61, 80))
    assert field.state(40, 65) == State.SEA, "the ball keeps its pocket alive"
    assert all(
        field.state(x, y) == State.SEA for x in range(31, 49) for y in range(61, 70)
    ), "cells around the ball stay sea while the rest of the band is taken"
    assert field.state(60, 30) == State.SEA, "the open sea stays sea"


def test_bumping_a_ball_costs_a_life_and_keeps_the_rest_of_the_field():
    game = quiet_round(seed=7)
    player = game.players[0]
    walk(game, 0, (1, 0), 20)
    walk(game, 0, (0, -1), 40)
    captured_before = player.score
    assert captured_before == 800
    assert (player.x, player.y) == (20, 0)

    # Step off the freshly captured edge into the open sea to the east, then let
    # a ball cross the new trail behind the marker.
    player.x, player.y = 21, 1
    player.anchor = (19, 1)
    walk(game, 0, (1, 0), 10)
    assert len(player.trail) == 10
    on_trail = player.trail[0]
    ball = Ball(x=on_trail[0], y=on_trail[1] + 1, dx=0, dy=-1, ticks_per_cell=1)
    game.balls = [ball, *game.balls]
    run(game, config.PLAYER_TICKS_PER_CELL)

    assert player.lives == config.START_LIVES - 1
    assert player.score == captured_before
    assert game.field.land_count == captured_before
    assert player.trail == []
    assert (player.x, player.y) == (19, 1)


def test_the_round_ends_and_reports_a_winner_when_the_target_is_met():
    game = quiet_round(seed=9, player_count=2)
    game.balls = []
    field = game.field
    field.land_count = game.target_cells
    game.players[0].score = 4000
    game.players[1].score = 3200

    game.tick()

    assert game.state == "finished"
    assert game.result is not None
    assert game.result.winner == 0
    assert game.result.kind == "target"
    assert round(sum(game.result.percents), 1) == round(
        100 * 7200 / config.PLAYABLE_CELLS, 1
    )


def test_a_two_player_round_keeps_both_players_independent():
    game = make_game(width=60, height=40, player_count=2, seed=4)
    game.balls = []
    game.set_direction(0, (1, 0))
    game.set_direction(1, (-1, 0))
    run(game, 60)

    first, second = game.players
    assert first.x > 1
    assert second.x < game.field.width - 2
    assert first.lives == config.START_LIVES
    assert second.lives == config.START_LIVES
    assert first.trail and second.trail
    assert game.field.owner_at(*first.trail[0]) == 0
    assert game.field.owner_at(*second.trail[0]) == 1


def test_the_simulation_is_deterministic_for_a_seed():
    def scripted_round():
        game = make_game(width=60, height=40, player_count=2, seed=99)
        for step in range(600):
            direction = ((1, 0), (0, 1), (-1, 0), (0, -1))[step // 40 % 4]
            game.set_direction(0, direction)
            game.set_direction(1, direction)
            game.tick()
        return (
            [(player.x, player.y, player.score, player.lives) for player in game.players],
            [(ball.x, ball.y) for ball in game.balls],
            game.field.land_count,
            game.stage,
        )

    assert scripted_round() == scripted_round()


def test_a_long_round_never_leaves_the_field_or_the_documented_bounds():
    game = Game(player_count=2, seed=21)
    for step in range(3000):
        direction = ((1, 0), (0, -1), (1, 0), (0, 1))[step // 120 % 4]
        game.set_direction(0, direction)
        game.set_direction(1, (0, -1) if step // 90 % 2 else (0, 1))
        game.tick()
        field = game.field
        assert 0 <= game.players[0].x < field.width
        assert 0 <= game.players[1].x < field.width
        for ball in game.balls:
            assert 0 < ball.x < field.width - 1
            assert 0 < ball.y < field.height - 1
        assert field.land_count <= field.playable_cells
        if game.state == "finished":
            break
    assert 0 <= game.stage <= len(config.STAGE_THRESHOLDS)
