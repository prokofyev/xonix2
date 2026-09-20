"""Keyboard handling: WASD and the arrows, as two switchable key sets.

A key set is a layout, not a player: in a two-player round each player owns one
set, while a solo round owns both, because the arrows would otherwise be dead
keys nobody can use.

Direction is direct control: the marker moves while a key is held. Holding keys
on two axes is a conflict, not a diagonal, so the axis pressed last wins and
releasing it stops the marker instead of falling back to the other axis. The
same rule spans the sets, so switching from WASD to an arrow mid-hold behaves
like any other change of axis.
"""

from __future__ import annotations

import pygame

KEY_SETS: tuple[dict[int, tuple[int, int]], ...] = (
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


def layouts_for_players(
    player_count: int,
) -> tuple[tuple[dict[int, tuple[int, int]], ...], ...]:
    """Which key sets drive each player.

    Two players take one set each, so a key never reaches the other marker. A
    solo round has no second player to own the second set, so its only marker
    listens to both and either hand can drive it.
    """
    if player_count < 2:
        return (KEY_SETS,) * max(player_count, 0)
    return tuple((keys,) for keys in KEY_SETS)


def _direction_for(
    layouts: tuple[dict[int, tuple[int, int]], ...], key: int
) -> tuple[int, int] | None:
    for layout in layouts:
        direction = layout.get(key)
        if direction is not None:
            return direction
    return None


class DirectionTracker:
    """Turns key presses and releases into one direction per player."""

    def __init__(self, player_count: int = 2) -> None:
        self.player_count = player_count
        self._layouts = layouts_for_players(player_count)
        self._active: list[tuple[int, int] | None] = [None] * len(self._layouts)
        self._key_for_player: dict[int, int] = {}

    def direction(self, player_index: int) -> tuple[int, int] | None:
        return self._active[player_index]

    def press(self, key: int) -> bool:
        for index, layouts in enumerate(self._layouts):
            direction = _direction_for(layouts, key)
            if direction is not None:
                self._active[index] = direction
                self._key_for_player[index] = key
                return True
        return False

    def release(self, key: int) -> bool:
        for index, layouts in enumerate(self._layouts):
            if _direction_for(layouts, key) is None:
                continue
            if self._key_for_player.get(index) == key:
                self._active[index] = None
                del self._key_for_player[index]
            return True
        return False

    def clear(self) -> None:
        self._active = [None] * len(self._layouts)
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
