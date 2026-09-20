from tests.helpers import carve_land, land_area, make_game, run
from xonix import config
from xonix.core.ball import Ball
from xonix.core.field import State


def test_percentages_are_measured_against_playable_cells():
    game = make_game(width=120, height=80, player_count=2, seed=3)
    game.players[0].score = 3313
    game.players[1].score = 2945

    first, second = game._percents()

    assert round(first, 1) == 36.0
    assert round(second, 1) == 32.0
    assert round(first + second, 1) == 68.0


def test_the_perimeter_contributes_nothing_to_either_percentage():
    game = make_game(width=120, height=80, player_count=2, seed=3)

    first, second = game._percents()

    assert (first, second) == (0.0, 0.0)
    assert config.ROUND_TARGET_CELLS == 6903
    assert config.ROUND_TARGET_CELLS == round(config.PLAYABLE_CELLS * 0.75)


def test_round_ends_when_the_target_share_is_land():
    game = make_game(width=40, height=24, player_count=2)
    game.balls = []
    land_area(game, game.target_cells)
    game.players[0].score = 100
    game.players[1].score = 50

    game.tick()

    assert game.state == "finished"
    assert game.result is not None
    assert game.result.winner == 0
    assert game.result.kind == "target"


def test_equal_scores_at_the_target_are_a_draw():
    game = make_game(width=40, height=24, player_count=2)
    game.balls = []
    land_area(game, game.target_cells)
    game.players[0].score = 80
    game.players[1].score = 80

    game.tick()

    assert game.result is not None
    assert game.result.winner is None
    assert game.result.kind == "target"


def test_round_does_not_continue_past_the_target():
    game = make_game(width=40, height=24, player_count=2)
    game.balls = []
    land_area(game, game.target_cells)
    game.tick()

    position = (game.players[0].x, game.players[0].y)
    game.set_direction(0, (1, 0))
    run(game, 30)

    assert game.state == "finished"
    assert (game.players[0].x, game.players[0].y) == position


def test_running_out_of_lives_hands_the_round_to_the_survivor():
    game = make_game(width=40, height=24, player_count=2)
    game.balls = []
    game.players[0].lives = 0
    game.players[1].lives = 2
    game.players[0].alive = False

    game.tick()

    assert game.state == "finished"
    assert game.result is not None
    assert game.result.winner == 1
    assert game.result.kind == "lives"


def test_solo_round_ends_in_defeat_when_lives_run_out():
    game = make_game(width=40, height=24, player_count=1)
    game.balls = []
    game.players[0].lives = 0
    game.players[0].alive = False

    game.tick()

    assert game.result is not None
    assert game.result.kind == "defeat"
    assert game.result.winner is None


def test_solo_round_can_be_won_by_reaching_the_target():
    game = make_game(width=40, height=24, player_count=1)
    game.balls = []
    land_area(game, game.target_cells)
    game.players[0].score = 400

    game.tick()

    assert game.result is not None
    assert game.result.kind == "target"
    assert game.result.winner == 0


def test_stage_ladder_climbs_once_per_threshold():
    game = make_game(width=60, height=40, player_count=2)
    game.balls = [Ball(x=30, y=20, dx=1, dy=1, ticks_per_cell=config.STAGE_SPEEDS[0])]
    field = game.field

    expected_balls = 1
    for stage, threshold in enumerate(config.STAGE_THRESHOLDS, start=1):
        needed = int(field.playable_cells * threshold) - field.land_count + 1
        land_area(game, needed)
        game.tick()
        expected_balls += 1
        assert game.stage == stage
        assert len(game.balls) == expected_balls
        assert all(
            ball.ticks_per_cell == config.STAGE_SPEEDS[stage] for ball in game.balls
        )

    game.tick()
    assert game.stage == len(config.STAGE_THRESHOLDS)
    assert len(game.balls) == expected_balls


def test_input_is_applied_at_the_start_of_the_next_tick():
    game = make_game(width=40, height=24, player_count=1)
    game.balls = []

    game.set_direction(0, (1, 0))
    assert game.players[0].direction is None
    game.tick()
    assert game.players[0].direction == (1, 0)


def test_a_stopped_round_ignores_further_ticks():
    game = make_game(width=40, height=24, player_count=2)
    game.balls = []
    land_area(game, game.target_cells)
    game.tick()
    scores = (game.players[0].score, game.players[1].score)

    game.set_direction(0, (1, 0))
    run(game, 30)

    assert game.state == "finished"
    assert (game.players[0].score, game.players[1].score) == scores


def test_restart_returns_the_field_scores_and_lives():
    game = make_game(width=40, height=24, player_count=2)
    game.balls = []
    game.players[0].score = 120
    game.players[0].lives = 1
    carve_land(game.field, [(x, 3) for x in range(1, 10)])
    game.field.land_count = 9

    game.reset()

    assert game.field.land_count == 0
    assert game.state == "playing"
    assert game.stage == 0
    assert all(player.lives == config.START_LIVES for player in game.players)
    assert all(player.score == 0 for player in game.players)
    assert all(player.trail == [] for player in game.players)
    assert len(game.balls) == config.BALLS_AT_START
    assert all(cell == State.LAND for cell in game.field.cells[: game.field.width])
