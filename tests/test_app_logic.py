"""State transitions that do not need a visible window."""

import pygame
import pytest

from xonix import app as app_module, config


@pytest.fixture
def app():
    surface = pygame.Surface((config.WINDOW_WIDTH, config.WINDOW_HEIGHT))
    instance = app_module.App(screen=surface)
    yield instance
    instance.stop()
    pygame.quit()


def test_menu_opens_a_solo_round(app):
    assert app.state == app_module.MENU

    app._key_down(pygame.K_1)

    assert app.state == app_module.PLAY
    assert app.game is not None
    assert len(app.game.players) == 1


def test_menu_opens_a_two_player_round(app):
    app._key_down(pygame.K_2)

    assert app.state == app_module.PLAY
    assert app.game is not None
    assert len(app.game.players) == 2
    assert all(player.lives == config.START_LIVES for player in app.game.players)


def test_pause_stops_the_ticks(app):
    app._key_down(pygame.K_2)
    app._key_down(pygame.K_p)
    snapshot = [(player.x, player.y) for player in app.game.players]

    app.update(1.0)

    assert app.paused
    assert [(player.x, player.y) for player in app.game.players] == snapshot


def test_resuming_continues_the_round(app):
    app._key_down(pygame.K_2)
    app._key_down(pygame.K_p)
    app._key_down(pygame.K_p)

    assert not app.paused


def test_restart_returns_the_initial_state(app):
    app._key_down(pygame.K_2)
    app.game.players[0].score = 100
    app.game.players[0].lives = 1

    app._key_down(pygame.K_r)

    assert app.game.players[0].score == 0
    assert app.game.players[0].lives == config.START_LIVES
    assert app.game.field.land_count == 0


def test_escape_returns_to_the_menu(app):
    app._key_down(pygame.K_2)

    app._key_down(pygame.K_ESCAPE)

    assert app.state == app_module.MENU


def test_finished_round_shows_the_result_screen(app):
    app._key_down(pygame.K_2)
    app.game.players[1].lives = 0
    app.game.players[1].alive = False

    app.update(1 / config.TICKS_PER_SECOND)

    assert app.state == app_module.RESULT


def test_result_screen_returns_to_the_menu(app):
    app._key_down(pygame.K_2)
    app.game.players[1].lives = 0
    app.game.players[1].alive = False
    app.update(1 / config.TICKS_PER_SECOND)

    app._key_down(pygame.K_RETURN)

    assert app.state == app_module.MENU


def test_capture_flash_does_not_change_the_score(app):
    app._key_down(pygame.K_2)
    owner, x, y = 0, 5, 5
    app.flashes.add([(x, y)], owner)
    score_before = app.game.players[0].score

    app.flashes.update(0.1)

    assert app.game.players[0].score == score_before
    assert app.flashes.active_cells()


def test_flashes_expire(app):
    app.flashes.add([(1, 1)], 0)

    app.flashes.update(config.CAPTURE_FLASH_SECONDS + 0.01)

    assert app.flashes.active_cells() == []


def finish_round(app, winner, kind="target"):
    """Force the round in progress to end with a chosen result."""
    from xonix.core.game import RoundResult

    scores = (1000, 900) if winner == 0 else (900, 1000)
    percents = (56.0, 21.0) if winner == 0 else (21.0, 56.0)
    if winner is None:
        scores, percents = (1000, 1000), (35.0, 35.0)
    app.game.result = RoundResult(kind, winner, scores, percents, (3, 3))
    app.game.state = "finished"


def test_the_win_tally_starts_at_zero(app):
    assert app.win_counts == [0, 0]


def test_a_versus_round_credits_the_winner_once(app):
    app._key_down(pygame.K_2)
    finish_round(app, winner=1)

    app.update(1 / config.TICKS_PER_SECOND)

    assert app.state == app_module.RESULT
    assert app.win_counts == [0, 1]


def test_later_frames_do_not_credit_the_win_again(app):
    app._key_down(pygame.K_2)
    finish_round(app, winner=0)
    app.update(1 / config.TICKS_PER_SECOND)

    for _ in range(5):
        app.update(1 / config.TICKS_PER_SECOND)

    assert app.win_counts == [1, 0]


def test_a_win_on_lives_counts_the_same_as_a_win_on_points(app):
    app._key_down(pygame.K_2)
    app.game.players[1].lives = 0
    app.game.players[1].alive = False

    app.update(1 / config.TICKS_PER_SECOND)

    assert app.game.result.kind == "lives"
    assert app.game.result.winner == 0
    assert app.win_counts == [1, 0]


def test_a_draw_leaves_the_tally_alone(app):
    app._key_down(pygame.K_2)
    finish_round(app, winner=None)
    app.update(1 / config.TICKS_PER_SECOND)

    assert app.game.result.winner is None
    assert app.win_counts == [0, 0]


def test_wins_accumulate_across_rounds(app):
    app._key_down(pygame.K_2)
    finish_round(app, winner=0)
    app.update(1 / config.TICKS_PER_SECOND)
    app._key_down(pygame.K_r)

    finish_round(app, winner=1)
    app.update(1 / config.TICKS_PER_SECOND)

    assert app.win_counts == [1, 1]


def test_a_new_match_from_the_menu_resets_the_tally(app):
    app._key_down(pygame.K_2)
    finish_round(app, winner=1)
    app.update(1 / config.TICKS_PER_SECOND)

    app._key_down(pygame.K_ESCAPE)
    app._key_down(pygame.K_2)

    assert app.win_counts == [0, 0]


def test_restarting_the_round_keeps_the_tally(app):
    app._key_down(pygame.K_2)
    finish_round(app, winner=0)
    app.update(1 / config.TICKS_PER_SECOND)
    app._key_down(pygame.K_ESCAPE)
    app._key_down(pygame.K_2)
    finish_round(app, winner=1)
    app.update(1 / config.TICKS_PER_SECOND)

    app._key_down(pygame.K_r)

    assert app.win_counts == [0, 1]


def test_a_solo_round_never_touches_the_tally(app):
    app._key_down(pygame.K_1)
    finish_round(app, winner=0)
    app.update(1 / config.TICKS_PER_SECOND)

    assert app.state == app_module.RESULT
    assert app.win_counts == [0, 0]
