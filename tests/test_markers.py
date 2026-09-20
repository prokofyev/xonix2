from tests.helpers import carve_land, make_game, park_ball, run
from xonix import config
from xonix.core.field import State


def quiet_game(player_count: int = 1, width: int = 40, height: int = 24):
    game = make_game(width=width, height=height, player_count=player_count)
    game.balls = []
    return game


def test_marker_moves_one_cell_every_three_ticks():
    game = quiet_game()
    player = game.players[0]
    direction = (1, 0)
    game.set_direction(0, direction)

    for _ in range(config.PLAYER_TICKS_PER_CELL - 1):
        game.tick()
    assert player.x == 0, "the marker must not move before its interval elapses"

    game.tick()
    assert player.x == 1

    run(game, config.PLAYER_TICKS_PER_CELL)
    assert player.x == 2


def test_releasing_input_stops_the_marker():
    game = quiet_game()
    player = game.players[0]
    game.set_direction(0, (1, 0))
    run(game, 30)
    moved_to = player.x

    game.set_direction(0, None)
    run(game, 30)

    assert player.x == moved_to


def test_sea_cells_become_trail_including_the_marker_cell():
    game = quiet_game()
    player = game.players[0]
    game.set_direction(0, (1, 0))
    run(game, 6)

    assert game.field.state(player.x, player.y) == State.TRAIL
    assert game.field.owner_at(player.x, player.y) == player.owner
    assert player.trail[-1] == (player.x, player.y)
    assert player.trail[0] == (1, player.y)


def test_standing_still_in_the_sea_keeps_the_trail():
    game = quiet_game()
    player = game.players[0]
    game.set_direction(0, (1, 0))
    run(game, 6)
    trail = list(player.trail)

    game.set_direction(0, None)
    run(game, 30)

    assert player.trail == trail
    assert all(game.field.state(x, y) == State.TRAIL for x, y in trail)


def test_walking_along_land_moves_the_respawn_anchor():
    game = quiet_game()
    player = game.players[0]
    carve_land(game.field, [(x, player.y) for x in range(1, 11)])

    game.set_direction(0, (1, 0))
    run(game, 30)

    assert player.x == 10
    assert player.anchor == (10, player.y)
    assert player.trail == []


def test_returning_to_land_captures_the_trail():
    game = quiet_game()
    park_ball(game, 15, 3)
    player = game.players[0]
    carve_land(game.field, [(x, player.y) for x in range(1, 6)])
    carve_land(game.field, [(8, player.y)])

    game.set_direction(0, (1, 0))
    run(game, 24)

    assert player.x == 8
    assert player.trail == []
    assert player.score == 2
    assert game.field.is_land(6, player.y) and game.field.is_land(7, player.y)


def test_landing_fills_water_the_ball_cannot_reach():
    game = quiet_game()
    park_ball(game, 15, 3)
    player = game.players[0]
    carve_land(game.field, [(x, player.y) for x in range(1, 6)])
    carve_land(game.field, [(8, player.y)])
    carve_land(game.field, [(10, y) for y in range(1, 23)])

    game.set_direction(0, (1, 0))
    run(game, 24)

    # The wall seals the left half away from the only ball, so everything the
    # player cannot be reached from becomes land, while the ball's side stays sea.
    assert player.score > 2
    assert game.field.is_land(5, 5)
    assert game.field.is_land(2, 20)
    assert game.field.is_sea(15, 5)


def test_two_markers_can_share_a_land_cell():
    game = quiet_game(player_count=2)
    first, second = game.players
    second.x, second.y = first.x, first.y

    game.set_direction(0, None)
    game.set_direction(1, None)
    game.tick()

    assert (first.x, first.y) == (second.x, second.y)
    assert game.state == "playing"
