from tests.helpers import carve_land, make_game, run, stage_for
from xonix import config
from xonix.core.ball import Ball
from xonix.core.field import State


def test_ball_moves_a_cell_every_speed_ticks():
    game = make_game(width=40, height=24)
    ball = Ball(x=20, y=12, dx=1, dy=0, ticks_per_cell=4)
    game.balls = [ball]

    for _ in range(3):
        assert ball.step(game.field) is False
    assert (ball.x, ball.y) == (20, 12)
    assert ball.step(game.field) is True
    assert (ball.x, ball.y) == (21, 12)


def test_ball_bounces_off_land():
    game = make_game(width=40, height=24)
    carve_land(game.field, [(22, 12)])
    ball = Ball(x=21, y=12, dx=1, dy=0, ticks_per_cell=1)
    game.balls = [ball]

    assert ball.step(game.field) is False
    assert (ball.x, ball.y) == (21, 12)
    assert ball.dx == -1

    assert ball.step(game.field) is True
    assert (ball.x, ball.y) == (20, 12)


def test_ball_slides_along_a_wall():
    game = make_game(width=40, height=24)
    carve_land(game.field, [(20, 12)])
    ball = Ball(x=19, y=12, dx=1, dy=-1, ticks_per_cell=1)
    game.balls = [ball]

    ball.step(game.field)

    assert (ball.x, ball.y) == (19, 11)
    assert ball.dx == -1
    assert ball.dy == -1


def test_balls_pass_through_each_other():
    game = make_game(width=40, height=24)
    first = Ball(x=10, y=10, dx=1, dy=0, ticks_per_cell=1)
    second = Ball(x=11, y=10, dx=-1, dy=0, ticks_per_cell=1)
    game.balls = [first, second]

    first.step(game.field)
    second.step(game.field)

    assert (first.x, first.y) == (11, 10)
    assert (second.x, second.y) == (10, 10)
    assert first.dx == 1 and second.dx == -1


def test_ball_is_contained_by_the_perimeter():
    game = make_game(width=20, height=12)
    ball = Ball(x=18, y=5, dx=1, dy=1, ticks_per_cell=1)
    game.balls = [ball]

    for _ in range(50):
        ball.step(game.field)
        assert 0 < ball.x < game.field.width - 1
        assert 0 < ball.y < game.field.height - 1


def test_ball_kills_the_trail_owner_once_per_entry():
    game = make_game(width=40, height=24)
    player = game.players[0]
    game.balls = []
    game.set_direction(0, (1, 0))
    run(game, 6)
    trail = list(player.trail)
    assert trail

    # Aim the ball at the far end of the trail, away from where it would enter.
    ball = Ball(x=trail[-1][0] + 1, y=trail[-1][1], dx=-1, dy=0, ticks_per_cell=1)
    game.balls = [ball]
    game.tick()

    assert player.lives == config.START_LIVES - 1
    assert player.trail == []
    assert all(game.field.state(x, y) == State.SEA for x, y in trail)


def test_ball_finishing_its_step_away_from_a_trail_is_harmless():
    game = make_game(width=40, height=24)
    player = game.players[0]
    game.balls = []
    game.set_direction(0, (1, 0))
    run(game, 6)

    ball = Ball(x=2, y=2, dx=1, dy=0, ticks_per_cell=1)
    game.balls = [ball]
    game.tick()

    assert player.lives == config.START_LIVES


def test_stage_speeds_all_balls_and_keeps_markers_constant():
    game = make_game(width=40, height=24)
    game.balls = [Ball(x=5, y=5, dx=1, dy=1, ticks_per_cell=config.STAGE_SPEEDS[0])]
    stage_for(game, 0)

    game.tick()

    assert game.stage == 1
    assert len(game.balls) == 2
    assert all(ball.ticks_per_cell == config.STAGE_SPEEDS[1] for ball in game.balls)
    assert config.PLAYER_TICKS_PER_CELL == 3


def test_each_threshold_fires_exactly_once():
    game = make_game(width=40, height=24)
    game.balls = [Ball(x=5, y=5, dx=1, dy=1, ticks_per_cell=config.STAGE_SPEEDS[0])]
    stage_for(game, 0)
    game.tick()
    assert game.stage == 1
    balls_after_first = len(game.balls)

    game.tick()

    assert game.stage == 1
    assert len(game.balls) == balls_after_first
