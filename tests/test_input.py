"""Input mapping runs without a display, using pygame's key constants only."""

import pygame

from xonix.input import (
    KEY_SETS,
    DirectionTracker,
    is_menu,
    is_pause,
    is_restart,
    layouts_for_players,
)


def test_a_two_player_round_gives_each_player_one_key_set():
    layouts = layouts_for_players(2)

    assert len(layouts) == 2
    assert layouts[0] == (KEY_SETS[0],)
    assert layouts[1] == (KEY_SETS[1],)


def test_a_solo_round_gives_its_only_player_both_key_sets():
    layouts = layouts_for_players(1)

    assert layouts == (KEY_SETS,), "the arrows would otherwise be dead keys"
    assert pygame.K_d in layouts[0][0] and pygame.K_LEFT in layouts[0][1], (
        "both layouts must reach the solo marker"
    )


def test_either_layout_drives_the_only_player_in_a_solo_round():
    for key, expected in (
        (pygame.K_w, (0, -1)),
        (pygame.K_a, (-1, 0)),
        (pygame.K_s, (0, 1)),
        (pygame.K_d, (1, 0)),
        (pygame.K_UP, (0, -1)),
        (pygame.K_LEFT, (-1, 0)),
        (pygame.K_DOWN, (0, 1)),
        (pygame.K_RIGHT, (1, 0)),
    ):
        tracker = DirectionTracker(1)

        assert tracker.press(key), f"{pygame.key.name(key)} must be accepted"
        assert tracker.direction(0) == expected


def test_the_other_players_keys_do_not_move_your_marker_in_a_two_player_round():
    tracker = DirectionTracker(2)

    tracker.press(pygame.K_LEFT)
    assert tracker.direction(0) is None
    assert tracker.direction(1) == (-1, 0)

    tracker.release(pygame.K_LEFT)
    tracker.press(pygame.K_d)
    assert tracker.direction(0) == (1, 0)
    assert tracker.direction(1) is None


def test_switching_layout_mid_hold_follows_the_last_key_pressed():
    tracker = DirectionTracker(1)
    tracker.press(pygame.K_d)
    assert tracker.direction(0) == (1, 0)

    tracker.press(pygame.K_UP)

    assert tracker.direction(0) == (0, -1), "the second layout overrides the hold"


def test_releasing_the_key_of_the_other_layout_stops_instead_of_falling_back():
    tracker = DirectionTracker(1)
    tracker.press(pygame.K_d)
    tracker.press(pygame.K_UP)

    tracker.release(pygame.K_UP)

    assert tracker.direction(0) is None


def test_releasing_the_abandoned_key_of_the_first_layout_keeps_the_new_one():
    tracker = DirectionTracker(1)
    tracker.press(pygame.K_d)
    tracker.press(pygame.K_UP)

    tracker.release(pygame.K_d)

    assert tracker.direction(0) == (0, -1)


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
