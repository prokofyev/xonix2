"""The real application loop, driven through pygame's event queue.

This is the closest automated stand-in for playing a round: it exercises event
handling, the tick clock, the simulation and drawing together, with a dummy
video driver so no window opens.
"""

import pygame
import pytest

from tests.helpers import park_ball
from xonix import app as app_module, config


@pytest.fixture
def app():
    instance = app_module.App()
    yield instance
    instance.stop()
    pygame.quit()


def post_key(app, kind: int, key: int) -> None:
    pygame.event.post(pygame.event.Event(kind, key=key, mod=0, unicode="", scancode=0))


def step(app, frames: int, seconds_per_frame: float = 1 / config.TICKS_PER_SECOND) -> None:
    for _ in range(frames):
        app.handle_events()
        app.update(seconds_per_frame)
        app.draw()


def quieten(app) -> None:
    """Park the balls far away so a scripted hold measures input, not luck.

    A live round has three balls wandering the field, and any of them can cross
    the trail a test is drawing at any moment. These tests assert which keys
    move the marker, so the round is made deterministic first.
    """
    park_ball(app.game, config.FIELD_WIDTH - 10, config.FIELD_HEIGHT - 10)


def test_a_full_session_runs_from_menu_to_result_and_back(app):
    post_key(app, pygame.KEYDOWN, pygame.K_2)
    step(app, 1)
    assert app.state == app_module.PLAY
    game = app.game
    assert game is not None

    post_key(app, pygame.KEYDOWN, pygame.K_d)
    post_key(app, pygame.KEYDOWN, pygame.K_LEFT)
    step(app, 120)
    assert game.players[0].x > 0
    assert game.players[1].x < game.field.width - 1

    post_key(app, pygame.KEYUP, pygame.K_d)
    post_key(app, pygame.KEYUP, pygame.K_LEFT)
    step(app, 60)
    assert game.state == "playing"

    post_key(app, pygame.KEYDOWN, pygame.K_p)
    step(app, 1)
    paused_at = [(player.x, player.y) for player in game.players]
    step(app, 120)
    assert [(player.x, player.y) for player in game.players] == paused_at
    post_key(app, pygame.KEYDOWN, pygame.K_p)
    step(app, 1)

    post_key(app, pygame.KEYDOWN, pygame.K_r)
    step(app, 1)
    restarted = app.game
    assert restarted is not game, "restart builds a fresh round"
    assert restarted.field.land_count == 0
    assert all(player.lives == config.START_LIVES for player in restarted.players)

    restarted.players[1].lives = 0
    restarted.players[1].alive = False
    step(app, 1)
    assert app.state == app_module.RESULT

    post_key(app, pygame.KEYDOWN, pygame.K_RETURN)
    step(app, 1)
    assert app.state == app_module.MENU


def test_a_solo_session_plays_by_the_same_rules(app):
    post_key(app, pygame.KEYDOWN, pygame.K_1)
    app.handle_events()

    assert app.state == app_module.PLAY
    assert len(app.game.players) == 1

    post_key(app, pygame.KEYDOWN, pygame.K_w)
    step(app, 90)
    player = app.game.players[0]
    assert player.y < app.game.field.height // 2
    assert player.lives == config.START_LIVES
    assert app.game.balls, "the solo round keeps its balls"


def test_escape_quits_from_the_menu(app):
    post_key(app, pygame.KEYDOWN, pygame.K_ESCAPE)
    app.handle_events()

    assert not app.running


def test_the_arrows_drive_the_only_marker_of_a_solo_round(app):
    post_key(app, pygame.KEYDOWN, pygame.K_1)
    app.handle_events()
    assert app.state == app_module.PLAY
    assert len(app.game.players) == 1
    quieten(app)

    post_key(app, pygame.KEYDOWN, pygame.K_RIGHT)
    step(app, 90)

    player = app.game.players[0]
    assert player.x > 0, "the solo marker must answer the second key set too"
    assert player.lives == config.START_LIVES


def test_switching_key_sets_mid_round_keeps_one_marker_in_a_solo_round(app):
    post_key(app, pygame.KEYDOWN, pygame.K_1)
    app.handle_events()
    quieten(app)

    post_key(app, pygame.KEYDOWN, pygame.K_RIGHT)
    step(app, 30)
    moved_right = app.game.players[0].x
    assert moved_right > 0

    post_key(app, pygame.KEYDOWN, pygame.K_s)
    step(app, 30)
    player = app.game.players[0]
    assert player.y > app.game.field.height // 2, "the WASD set took over"
    assert player.x == moved_right, "the released arrow set must not resume"
