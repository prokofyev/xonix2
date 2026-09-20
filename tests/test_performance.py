"""A capture's reachability pass must fit comfortably inside a frame budget."""

import time

from xonix import config
from xonix.core.field import Field
from xonix.core.game import Game

FRAME_BUDGET = 1.0 / config.TICKS_PER_SECOND


def average_seconds(call, repeats: int) -> float:
    started = time.perf_counter()
    for _ in range(repeats):
        call()
    return (time.perf_counter() - started) / repeats


def test_full_field_reachability_is_a_fraction_of_a_frame():
    field = Field()
    game = Game(player_count=2, seed=5, field=field)
    balls = [(ball.x, ball.y) for ball in game.balls]

    elapsed = average_seconds(lambda: field.reachable_sea(balls), 20)

    assert elapsed < FRAME_BUDGET / 3, f"a reachability pass took {elapsed * 1000:.2f} ms"


def test_sea_components_on_the_full_field_is_fast():
    field = Field()

    elapsed = average_seconds(field.sea_components, 10)

    assert elapsed < FRAME_BUDGET


def test_a_landing_on_the_full_field_stays_inside_one_frame():
    """The worst case the player can trigger: a capture on the real field."""
    game = Game(player_count=2, seed=5)
    field = game.field
    trail = [(x, 40) for x in range(30, 90)]
    for cell in trail:
        field.set_trail(*cell, owner=0)
    balls = [(ball.x, ball.y) for ball in game.balls]

    elapsed = average_seconds(lambda: field.fill(trail, balls), 5)

    assert elapsed < FRAME_BUDGET, f"a landing took {elapsed * 1000:.2f} ms"


def test_drawing_a_dense_field_at_hd_resolution_stays_near_a_frame():
    """Guards the presentation scale: 4K draws a bigger picture, not a slower game.

    The bound is deliberately generous because it is a machine-dependent check;
    it exists to catch a pathological regression (drawing cell by cell, copying
    the frame per cell), not to police a few milliseconds either way.
    """
    import pygame

    from xonix.core.field import State
    from xonix.core.game import Game
    from xonix.render import Renderer

    pygame.init()
    surface = pygame.Surface((1920, 1080))
    renderer = Renderer(surface)
    game = Game(player_count=2, seed=5)
    field = game.field
    for y in range(1, field.height - 1):
        for x in range(1, field.width - 1, 2):
            field.cells[field.index(x, y)] = State.LAND
            field.land_count += 1
    for index in range(0, 2000, 2):
        field.set_trail(index % (field.width - 2) + 1, index % (field.height - 2) + 1, index % 2)

    elapsed = average_seconds(lambda: renderer.draw_game(game, None), 5)
    pygame.quit()

    assert elapsed < 4 * FRAME_BUDGET, f"a dense frame took {elapsed * 1000:.2f} ms"
