"""Input mapping runs without a display, using pygame's key constants only."""

import pygame

from xonix.input import DirectionTracker, is_menu, is_pause, is_restart


def test_wasd_drives_the_first_player_and_arrows_the_second():
    tracker = DirectionTracker(2)

    tracker.press(pygame.K_d)
    tracker.press(pygame.K_LEFT)
    assert tracker.direction(0) == (1, 0)
    assert tracker.direction(1) == (-1, 0)

    tracker.release(pygame.K_d)
    assert tracker.direction(0) is None
    assert tracker.direction(1) == (-1, 0)


def test_the_key_pressed_last_wins_across_axes():
    tracker = DirectionTracker(1)

    tracker.press(pygame.K_d)
    assert tracker.direction(0) == (1, 0)
    tracker.press(pygame.K_w)
    assert tracker.direction(0) == (0, -1)


def test_releasing_the_new_axis_does_not_fall_back_to_the_old_one():
    tracker = DirectionTracker(1)
    tracker.press(pygame.K_d)
    tracker.press(pygame.K_w)

    tracker.release(pygame.K_w)

    assert tracker.direction(0) is None


def test_releasing_an_older_key_does_not_stop_current_motion():
    tracker = DirectionTracker(1)
    tracker.press(pygame.K_d)
    tracker.press(pygame.K_w)

    tracker.release(pygame.K_d)

    assert tracker.direction(0) == (0, -1)


def test_clear_drops_every_held_direction():
    tracker = DirectionTracker(2)
    tracker.press(pygame.K_w)
    tracker.press(pygame.K_RIGHT)

    tracker.clear()

    assert tracker.direction(0) is None
    assert tracker.direction(1) is None


def test_service_keys_are_recognised():
    assert is_pause(pygame.K_p)
    assert is_restart(pygame.K_r)
    assert is_menu(pygame.K_ESCAPE)
    assert not is_pause(pygame.K_w)
