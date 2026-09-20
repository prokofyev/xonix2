from tests.helpers import carve_land, make_game, park_ball, run
from xonix import config
from xonix.core.ball import Ball
from xonix.core.field import State


def two_player_game(width=40, height=24):
    game = make_game(width=width, height=height, player_count=2)
    game.balls = []
    return game


def walk(game, index, direction, moves):
    """Hold a direction for exactly ``moves`` marker steps."""
    game.set_direction(index, direction)
    run(game, moves * config.PLAYER_TICKS_PER_CELL)
    game.set_direction(index, None)
    return game.players[index]


def ball_entering(cell, direction):
    """A one-tick ball that will move into ``cell`` on its next step."""
    x, y = cell
    return Ball(x=x - direction[0], y=y - direction[1], dx=direction[0], dy=direction[1],
                ticks_per_cell=1)


def test_stepping_onto_your_own_trail_costs_a_life():
    game = two_player_game()
    player = walk(game, 0, (1, 0), 2)
    trail = list(player.trail)
    assert len(trail) == 2

    game.set_direction(0, (-1, 0))
    run(game, config.PLAYER_TICKS_PER_CELL)

    assert player.lives == config.START_LIVES - 1
    assert all(game.field.state(x, y) == State.SEA for x, y in trail)


def test_180_degree_turn_in_the_sea_is_death_by_the_trail_rule():
    game = two_player_game()
    player = walk(game, 0, (1, 0), 2)
    before = player.x

    game.set_direction(0, (-1, 0))
    run(game, config.PLAYER_TICKS_PER_CELL)

    assert player.lives == config.START_LIVES - 1
    assert player.x < before


def test_stepping_on_a_rival_trail_kills_only_the_intruder_and_keeps_the_trail():
    game = two_player_game()
    first = walk(game, 0, (1, 0), 2)
    rival_trail = list(first.trail)

    second = game.players[1]
    second.x, second.y = rival_trail[-1][0], rival_trail[-1][1] + 1
    second.anchor = (second.x, second.y)
    game.set_direction(1, (0, -1))
    run(game, config.PLAYER_TICKS_PER_CELL)

    assert second.lives == config.START_LIVES - 1
    assert first.lives == config.START_LIVES
    assert all(game.field.state(x, y) == State.TRAIL for x, y in rival_trail)
    assert first.score == 0


def test_death_keeps_the_field_and_only_clears_the_victims_trail():
    game = two_player_game()
    carve_land(game.field, [(x, 5) for x in range(1, 8)])
    game.field.land_count = 7
    player = walk(game, 0, (1, 0), 2)
    trail = list(player.trail)
    player.score = 7

    game.set_direction(0, (-1, 0))
    run(game, config.PLAYER_TICKS_PER_CELL)

    assert player.lives == config.START_LIVES - 1
    assert all(game.field.state(x, y) == State.SEA for x, y in trail)
    assert game.field.is_land(3, 5)
    assert player.score == 7


def test_respawn_returns_to_the_land_cell_the_player_left():
    game = two_player_game()
    carve_land(game.field, [(x, 12) for x in range(1, 4)])
    player = game.players[0]
    player.x, player.y = 0, 12
    player.anchor = (0, 12)

    player = walk(game, 0, (1, 0), 4)
    assert player.trail, "the player should be out in the sea"
    assert player.anchor == (3, 12)

    game.balls = [ball_entering(player.trail[-1], (0, 1))]
    run(game, config.PLAYER_TICKS_PER_CELL)

    assert player.lives == config.START_LIVES - 1
    assert (player.x, player.y) == (3, 12)


def test_the_anchor_does_not_move_while_the_player_is_at_sea():
    game = two_player_game()
    carve_land(game.field, [(x, 12) for x in range(1, 4)])
    player = game.players[0]
    player.x, player.y = 0, 12
    player.anchor = (0, 12)

    player = walk(game, 0, (1, 0), 4)
    anchor_before = player.anchor
    player = walk(game, 0, (1, 0), 3)

    assert player.x > anchor_before[0]
    assert player.anchor == anchor_before

    game.balls = [ball_entering(player.trail[-1], (0, 1))]
    run(game, config.PLAYER_TICKS_PER_CELL)

    assert player.lives == config.START_LIVES - 1
    assert (player.x, player.y) == anchor_before


def test_death_on_the_first_step_off_land_respawns_on_the_cell_left_behind():
    game = two_player_game()
    first = walk(game, 0, (1, 0), 2)
    trail_cell = first.trail[-1]

    second = game.players[1]
    second.x, second.y = trail_cell[0], trail_cell[1] + 1
    second.anchor = (second.x, second.y)
    game.set_direction(1, (0, -1))
    run(game, config.PLAYER_TICKS_PER_CELL)

    assert second.lives == config.START_LIVES - 1
    assert (second.x, second.y) == (trail_cell[0], trail_cell[1] + 1)


def test_standing_on_land_is_safe_from_a_passing_ball():
    game = two_player_game()
    player = game.players[0]
    carve_land(game.field, [(x, 12) for x in range(1, 8)])
    player.x, player.y = 4, 12

    game.balls = [Ball(x=7, y=12, dx=-1, dy=0, ticks_per_cell=1)]
    run(game, 30)

    assert player.lives == config.START_LIVES
    assert game.state == "playing"


def test_trail_death_wins_over_ball_death_in_the_same_tick():
    game = two_player_game()
    rival_trail = [(15, 10), (16, 10)]
    for cell in rival_trail:
        game.field.set_trail(*cell, owner=1)

    victim = game.players[0]
    victim.x, victim.y = 14, 10
    victim.anchor = (14, 10)
    game.field.set_trail(13, 10, 0)
    game.field.set_trail(14, 10, 0)
    victim.trail = [(13, 10), (14, 10)]

    # On the third tick the victim steps onto the rival's trail, while a ball
    # reaches the victim's own trail. The trail death decides the outcome, so the
    # rival's line survives untouched.
    game.balls = [Ball(x=12, y=10, dx=1, dy=0, ticks_per_cell=config.PLAYER_TICKS_PER_CELL)]
    game.set_direction(0, (1, 0))
    run(game, config.PLAYER_TICKS_PER_CELL)

    assert victim.lives == config.START_LIVES - 1
    assert (game.balls[0].x, game.balls[0].y) == (13, 10)
    assert game.field.state(13, 10) == State.SEA
    assert all(game.field.state(x, y) == State.TRAIL for x, y in rival_trail)
    assert game.field.owner_at(*rival_trail[0]) == 1


def test_both_players_losing_their_last_life_in_one_tick_is_a_draw():
    game = two_player_game()
    first = walk(game, 0, (1, 0), 2)
    second = game.players[1]
    second.x, second.y = 20, 12
    second.anchor = (20, 12)
    second = walk(game, 1, (-1, 0), 2)
    first.lives = 1
    second.lives = 1

    game.balls = [
        ball_entering(first.trail[-1], (0, 1)),
        ball_entering(second.trail[-1], (0, 1)),
    ]
    run(game, config.PLAYER_TICKS_PER_CELL)

    assert game.state == "finished"
    assert game.result is not None
    assert game.result.winner is None
    assert game.result.kind == "lives"


def test_spawning_never_lands_inside_a_walled_pocket():
    game = make_game(width=60, height=40, player_count=2)
    game.balls = [park_ball(game, 20, 20)]
    field = game.field
    for x in range(30, 40):
        field.cells[field.index(x, 10)] = State.LAND
        field.cells[field.index(x, 20)] = State.LAND
    for y in range(11, 20):
        field.cells[field.index(30, y)] = State.LAND
        field.cells[field.index(39, y)] = State.LAND

    ball = game._new_ball()

    assert not (30 < ball.x < 39 and 10 < ball.y < 20)


def test_a_new_ball_spawns_at_least_the_minimum_distance_from_both_markers():
    import math

    game = make_game(width=60, height=40, player_count=2)
    game.balls = [park_ball(game, 20, 20)]

    for _ in range(50):
        ball = game._new_ball()
        assert game.field.is_sea(ball.x, ball.y)
        for player in game.players:
            distance = math.dist((ball.x, ball.y), (player.x, player.y))
            assert distance >= config.SPAWN_MIN_DISTANCE


def test_a_new_ball_falls_back_to_the_farthest_cell_when_the_field_is_tight():
    import math

    game = make_game(width=20, height=14, player_count=2)
    game.balls = [park_ball(game, 10, 7)]
    for player in game.players:
        player.x = 0 if player.owner == 0 else 19
        player.y = 7
    field = game.field
    for x in range(1, 19):
        for y in range(1, 13):
            if (x, y) not in ((10, 3), (10, 10)):
                field.cells[field.index(x, y)] = State.LAND

    ball = game._new_ball()

    markers = [(player.x, player.y) for player in game.players]
    assert min(math.dist((ball.x, ball.y), marker) for marker in markers) == max(
        min(math.dist(cell, marker) for marker in markers)
        for cell in ((10, 3), (10, 10))
    )


def test_a_new_ball_is_born_on_one_of_the_four_diagonals():
    game = make_game(width=60, height=40, player_count=2)

    directions = {game._new_ball_direction() for _ in range(200)}

    assert directions == set(config.BALL_DIRECTIONS)


def test_ball_spawn_directions_do_not_favour_one_side():
    """Three balls all heading right handed the second player the first move."""
    headings = []
    for seed in range(200):
        game = make_game(width=60, height=40, player_count=2, seed=seed)
        headings.extend(ball.dx for ball in game.balls)

    right = headings.count(1)
    left = headings.count(-1)

    assert right + left == 3 * 200
    assert abs(right - left) < 0.15 * len(headings), f"{right} right vs {left} left"


def test_ball_spawn_directions_stay_reproducible_for_a_seed():
    first = [
        (ball.x, ball.y, ball.dx, ball.dy)
        for ball in make_game(width=60, height=40, player_count=2, seed=42).balls
    ]
    second = [
        (ball.x, ball.y, ball.dx, ball.dy)
        for ball in make_game(width=60, height=40, player_count=2, seed=42).balls
    ]

    assert first == second


def test_both_vertical_components_occur_at_spawn():
    dy_values = set()
    for seed in range(200):
        game = make_game(width=60, height=40, player_count=2, seed=seed)
        dy_values.update(ball.dy for ball in game.balls)

    assert dy_values == {-1, 1}
