"""Keyboard handling: WASD for the first player, arrows for the second.

Direction is direct control: the marker moves while a key is held. Holding keys
on two axes is a conflict, not a diagonal, so the axis pressed last wins and
releasing it stops the marker instead of falling back to the other axis.
"""

from __future__ import annotations

import pygame

PLAYER_KEYS: tuple[dict[int, tuple[int, int]], ...] = (
    {
        pygame.K_w: (0, -1),
        pygame.K_s: (0, 1),
        pygame.K_a: (-1, 0),
        pygame.K_d: (1, 0),
    },
    {
        pygame.K_UP: (0, -1),
        pygame.K_DOWN: (0, 1),
        pygame.K_LEFT: (-1, 0),
        pygame.K_RIGHT: (1, 0),
    },
)

PAUSE_KEYS = (pygame.K_p,)
FULLSCREEN_KEYS = (pygame.K_F11,)
RESTART_KEYS = (pygame.K_r,)
MENU_KEYS = (pygame.K_ESCAPE,)
SOLO_KEYS = (pygame.K_1,)
VERSUS_KEYS = (pygame.K_2,)
CONFIRM_KEYS = (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)


class DirectionTracker:
    """Turns key presses and releases into one direction per player."""

    def __init__(self, player_count: int = 2) -> None:
        self.player_count = player_count
        self._active: list[tuple[int, int] | None] = [None] * player_count
        self._key_for_player: dict[int, int] = {}

    def direction(self, player_index: int) -> tuple[int, int] | None:
        return self._active[player_index]

    def press(self, key: int) -> bool:
        for index in range(self.player_count):
            direction = PLAYER_KEYS[index].get(key)
            if direction is not None:
                self._active[index] = direction
                self._key_for_player[index] = key
                return True
        return False

    def release(self, key: int) -> bool:
        for index in range(self.player_count):
            if PLAYER_KEYS[index].get(key) is None:
                continue
            if self._key_for_player.get(index) == key:
                self._active[index] = None
                del self._key_for_player[index]
            return True
        return False

    def clear(self) -> None:
        self._active = [None] * self.player_count
        self._key_for_player.clear()


def is_pause(key: int) -> bool:
    return key in PAUSE_KEYS


def is_fullscreen(key: int) -> bool:
    return key in FULLSCREEN_KEYS


def is_restart(key: int) -> bool:
    return key in RESTART_KEYS


def is_menu(key: int) -> bool:
    return key in MENU_KEYS


def is_solo(key: int) -> bool:
    return key in SOLO_KEYS


def is_versus(key: int) -> bool:
    return key in VERSUS_KEYS


def is_confirm(key: int) -> bool:
    return key in CONFIRM_KEYS
