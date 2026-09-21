"""Pixel-level checks for the presentation requirements.

These stand in for looking at the screen: they assert the properties the specs
name explicitly (single land colour, distinguishable trails, HUD clear of the
field) rather than trusting the drawing code by inspection. Coordinates come
from the renderer's own layout, so the same checks hold at every scale.
"""

import itertools

import pygame
import pytest

from tests.helpers import carve_land, make_game
from xonix import config
from xonix.render import (
    BACKGROUND,
    OWNER_COLORS,
    PLAYER_NAMES,
    CaptureFlashes,
    Renderer,
    compute_layout,
    lives_size,
)

WINDOW = (config.WINDOW_WIDTH, config.WINDOW_HEIGHT)


@pytest.fixture
def renderer():
    pygame.init()
    surface = pygame.Surface(WINDOW)
    instance = Renderer(surface)
    yield instance
    pygame.quit()


def cell_point(renderer, x: int, y: int) -> tuple[int, int]:
    return renderer.layout.cell_point(x, y)


def pixel_at(renderer, x: int, y: int) -> tuple[int, int, int]:
    return renderer.screen.get_at(cell_point(renderer, x, y))[:3]


def test_land_from_both_players_is_the_same_colour(renderer):
    game = make_game(width=40, height=24, player_count=2)
    carve_land(game.field, [(x, 5) for x in range(1, 10)])
    game.players[0].score = 9

    renderer.draw_game(game, None)
    first = pixel_at(renderer, 3, 5)

    carve_land(game.field, [(x, 8) for x in range(1, 10)])
    renderer.draw_game(game, None)
    second = pixel_at(renderer, 3, 8)

    assert first == second
    assert first != BACKGROUND


def test_trails_of_the_two_players_differ_and_are_not_the_land_colour(renderer):
    game = make_game(width=40, height=24, player_count=2)
    game.field.set_trail(5, 5, owner=0)
    game.field.set_trail(7, 5, owner=1)

    renderer.draw_game(game, None)

    warm = pixel_at(renderer, 5, 5)
    cool = pixel_at(renderer, 7, 5)
    land = pixel_at(renderer, 0, 0)
    assert warm == OWNER_COLORS[0]
    assert cool == OWNER_COLORS[1]
    assert warm != cool
    assert warm != land and cool != land


def relative_luminance(colour: tuple[int, int, int]) -> float:
    return 0.2126 * colour[0] + 0.7152 * colour[1] + 0.0722 * colour[2]


def test_the_two_trail_colours_have_comparable_brightness():
    """Warm and cool are meant to read as equals, so neither looks dominant."""
    warm = relative_luminance(OWNER_COLORS[0])
    cool = relative_luminance(OWNER_COLORS[1])

    assert abs(warm - cool) / max(warm, cool) < 0.25, "one trail looks much brighter"
    assert max(OWNER_COLORS[0]) - min(OWNER_COLORS[0]) > 100, "warm must be saturated"
    assert max(OWNER_COLORS[1]) - min(OWNER_COLORS[1]) > 100, "cool must be saturated"


def test_land_and_trail_are_visually_distinct(renderer):
    game = make_game(width=40, height=24, player_count=1)
    carve_land(game.field, [(x, 5) for x in range(1, 10)])
    game.field.set_trail(5, 8, owner=0)

    renderer.draw_game(game, None)

    assert pixel_at(renderer, 5, 5) != pixel_at(renderer, 5, 8)


def test_the_flash_paints_the_capturing_player_colour(renderer):
    game = make_game(width=40, height=24, player_count=2)
    carve_land(game.field, [(5, 5)])
    flashes = CaptureFlashes()
    flashes.add([(5, 5)], owner=1)

    renderer.draw_game(game, flashes)

    assert pixel_at(renderer, 5, 5) != pixel_at(renderer, 0, 0)


def test_the_ball_is_drawn_lighter_than_the_field(renderer):
    game = make_game(width=40, height=24, player_count=1)
    game.balls[0].x, game.balls[0].y = 20, 12
    game.balls[0].accumulator = -10_000

    renderer.draw_game(game, None)

    assert sum(pixel_at(renderer, 20, 12)) > sum(pixel_at(renderer, 30, 12))


def test_the_hud_sits_above_the_field_and_never_covers_it(renderer):
    layout = renderer.layout
    assert layout.hud_height > 0
    assert layout.origin_y >= layout.hud_height, "the field must start below the HUD strip"

    game = make_game(width=config.FIELD_WIDTH, height=config.FIELD_HEIGHT, player_count=2)
    game.players[0].score = 3400
    game.players[1].score = 3000
    renderer.screen.fill(BACKGROUND)

    renderer.draw_hud(game)

    hud = pygame.Rect(0, 0, layout.width, layout.hud_height)
    painted = [
        (x, y)
        for x in range(layout.width)
        for y in range(layout.hud_height)
        if renderer.screen.get_at((x, y))[:3] != BACKGROUND
    ]
    assert painted, "the HUD must draw something"
    assert all(hud.collidepoint(point) for point in painted)


def test_the_field_top_row_is_never_overdrawn_by_the_hud(renderer):
    layout = renderer.layout
    game = make_game(width=config.FIELD_WIDTH, height=config.FIELD_HEIGHT, player_count=2)

    renderer.draw_game(game, None)

    top_row_y = layout.cell_point(0, 0)[1]
    assert top_row_y >= layout.hud_height
    assert renderer.screen.get_at(layout.cell_point(5, 0))[:3] != BACKGROUND


def test_the_two_players_hud_labels_do_not_overlap(renderer):
    layout = renderer.layout
    game = make_game(width=config.FIELD_WIDTH, height=config.FIELD_HEIGHT, player_count=2)
    game.players[0].score = 3400
    game.players[1].score = 3000
    renderer.screen.fill(BACKGROUND)

    renderer.draw_hud(game)

    row = layout.hud_height // 2
    columns = [
        x for x in range(layout.width) if renderer.screen.get_at((x, row))[:3] != BACKGROUND
    ]
    gaps = [
        (left, right)
        for left, right in itertools.pairwise(columns)
        if right - left > layout.width // 4
    ]
    assert gaps, "the two labels should be separated by a wide empty stretch"


def hud_heart_rects(renderer, game, owner: int) -> list[tuple[int, int, int, int]]:
    """The rects the HUD draws this player's hearts into, from the same layout."""
    layout = renderer.layout
    font = renderer.small
    player = game.players[owner]
    label = f"{PLAYER_NAMES[owner]} {round(100.0 * player.score / game.field.playable_cells):d}%"
    margin = max(8, 2 * layout.scale)
    gap = max(8, font.get_height() // 2)
    width, height = lives_size(player.lives, renderer.heart, renderer.heart_gap)
    group = font.size(label)[0] + gap + width
    left = margin if owner == 0 else layout.width - margin - group
    start = left + font.size(label)[0] + gap
    top = (layout.hud_height - height) // 2
    step = renderer.heart.get_width() + renderer.heart_gap
    return [
        (start + index * step, top, *renderer.heart.get_size())
        for index in range(player.lives)
    ]


def heart_ink_colours(renderer) -> set[tuple[int, int, int]]:
    """The colours the (scaled) sprite paints, for spotting it on the screen."""
    sprite = renderer.heart
    return {
        sprite.get_at((x, y))[:3]
        for x in range(sprite.get_width())
        for y in range(sprite.get_height())
        if sprite.get_at((x, y))[3]
    }


def painted_heart_pixels(renderer, rect) -> int:
    left, top, width, height = rect
    inks = heart_ink_colours(renderer)
    return sum(
        renderer.screen.get_at((x, y))[:3] in inks
        for x in range(left, left + width)
        for y in range(top, top + height)
    )


@pytest.mark.parametrize("window", [(720, 502), (1920, 1338)])
def test_the_hud_lives_are_painted_hearts(window):
    """Each life paints a heart sprite, and the sprite is not a solid box."""
    pygame.init()
    try:
        renderer = Renderer(pygame.Surface(window))
        game = make_game(width=config.FIELD_WIDTH, height=config.FIELD_HEIGHT, player_count=2)
        game.players[0].lives = 3
        game.players[1].lives = 1
        renderer.screen.fill(BACKGROUND)

        renderer.draw_hud(game)

        first, second = game.players[0].lives, game.players[1].lives
        rects = [hud_heart_rects(renderer, game, owner) for owner in (0, 1)]
        assert len(rects[0]) == first and len(rects[1]) == second
        for owner in (0, 1):
            for rect in rects[owner]:
                assert painted_heart_pixels(renderer, rect) > 0, "a heart is missing"
            # A solid rectangle would fill all four corners; a heart does not.
            left, top, _, _ = rects[owner][0]
            assert renderer.screen.get_at((left, top))[:3] not in heart_ink_colours(renderer)
        # The two counters stay on their own side of the screen.
        assert rects[0][-1][0] + rects[0][-1][2] < renderer.layout.width // 2
        assert rects[1][0][0] >= renderer.layout.width // 2
    finally:
        pygame.quit()


@pytest.mark.parametrize("window", [(720, 502), (1280, 892), (1920, 1338), (2560, 1784)])
def test_the_hud_hearts_stay_inside_the_strip_and_off_the_field(window):
    """The hearts must never spill out of the HUD onto the playable cells."""
    pygame.init()
    try:
        renderer = Renderer(pygame.Surface(window))
        layout = renderer.layout
        game = make_game(width=config.FIELD_WIDTH, height=config.FIELD_HEIGHT, player_count=2)
        renderer.screen.fill(BACKGROUND)

        renderer.draw_hud(game)

        assert renderer.heart.get_height() <= layout.hud_height
        for owner in (0, 1):
            for left, top, width, height in hud_heart_rects(renderer, game, owner):
                assert left >= 0 and left + width <= layout.width
                assert top >= 0 and top + height <= layout.hud_height
                assert painted_heart_pixels(renderer, (left, top, width, height)) > 0
        # Nothing may be painted over the top row of playable cells.
        assert renderer.screen.get_at(layout.cell_point(5, 0))[:3] == BACKGROUND
    finally:
        pygame.quit()


def test_cells_are_drawn_crisp_without_smoothing(renderer):
    """Cell edges land on exact multiples of the cell size, so nothing blurs."""
    layout = renderer.layout
    scale = layout.scale
    game = make_game(width=40, height=24, player_count=1)
    carve_land(game.field, [(x, 5) for x in range(10, 16)])
    renderer.screen.fill(BACKGROUND)

    renderer.draw_game(game, None)

    y = layout.cell_point(0, 5)[1]
    left = layout.origin_x + 10 * scale
    right = layout.origin_x + 16 * scale

    def pixel(column: int) -> tuple[int, int, int]:
        return renderer.screen.get_at((column, y))[:3]

    assert all(pixel(x) != BACKGROUND for x in range(left, right))
    assert pixel(left - 1) == BACKGROUND, "land must not bleed left of its cell"
    assert pixel(right) == BACKGROUND, "land must not bleed right of its cell"


def test_a_marker_stays_inside_its_own_cell(renderer):
    layout = renderer.layout
    scale = layout.scale
    game = make_game(width=40, height=24, player_count=2)
    renderer.screen.fill(BACKGROUND)

    renderer.draw_game(game, None)

    for player in game.players:
        colour = OWNER_COLORS[player.owner]
        assert pixel_at(renderer, player.x, player.y) == colour
        left = layout.origin_x + player.x * scale
        top = layout.origin_y + player.y * scale
        painted = [
            (x, y)
            for x in range(left - scale, left + 2 * scale)
            for y in range(top - scale, top + 2 * scale)
            if 0 <= x < layout.width
            and 0 <= y < layout.height
            and renderer.screen.get_at((x, y))[:3] == colour
        ]
        assert painted, "the marker must be visible"
        assert min(x for x, _ in painted) >= left
        assert max(x for x, _ in painted) <= left + scale - 1
        assert min(y for _, y in painted) >= top
        assert max(y for _, y in painted) <= top + scale - 1


@pytest.mark.parametrize(
    "window",
    [(320, 200), (720, 502), (800, 600), (1280, 800), (1920, 1080), (2560, 1440), (3840, 2160)],
)
def test_every_field_cell_is_drawn_inside_every_window(window):
    layout = compute_layout(window)
    assert layout.origin_x >= 0 and layout.origin_y >= 0
    assert layout.origin_x + config.FIELD_WIDTH * layout.scale <= layout.width
    assert layout.origin_y + config.FIELD_HEIGHT * layout.scale <= layout.height


def test_a_bigger_window_draws_bigger_cells():
    small = compute_layout((720, 502))
    big = compute_layout((1920, 1080))

    assert big.scale > small.scale
    assert compute_layout((3840, 2160)).scale > big.scale


def hex_cells_horizontal(field, y, x0, x1, owner):
    for x in range(x0, x1):
        field.set_trail(x, y, owner)


@pytest.mark.parametrize(
    "window",
    [(720, 502), (1280, 800), (1920, 1080), (2560, 1440), (3840, 2160)],
)
def test_a_trail_is_a_thin_line_at_every_scale(window):
    """A trail must read as a line, so it may not fill its cells like land does."""
    pygame.init()
    try:
        surface = pygame.Surface(window)
        renderer = Renderer(surface)
        scale = renderer.layout.scale
        game = make_game(width=40, height=24, player_count=1)
        hex_cells_horizontal(game.field, 5, 10, 20, owner=0)

        renderer.draw_game(game, None)

        thickness = max(2, scale // 4)
        y = renderer.layout.cell_point(0, 5)[1]
        painted = [
            row
            for row in range(y - scale, y + scale)
            if 0 <= row < renderer.layout.height
            and renderer.screen.get_at((renderer.layout.cell_point(15, 5)[0], row))[:3]
            == OWNER_COLORS[0]
        ]
        assert painted, "the trail must be visible at its centre"
        assert max(painted) - min(painted) + 1 <= thickness + 1, "the trail is too thick"
    finally:
        pygame.quit()


@pytest.mark.parametrize("window", [(720, 502), (1920, 1080), (2560, 1440)])
def test_adjacent_trail_cells_join_without_gaps(window):
    """Odd cell sizes used to leave a one-pixel break between segments."""
    pygame.init()
    try:
        surface = pygame.Surface(window)
        renderer = Renderer(surface)
        layout = renderer.layout
        game = make_game(width=40, height=24, player_count=1)
        hex_cells_horizontal(game.field, 5, 10, 20, owner=0)

        renderer.draw_game(game, None)

        # The line runs along cell centres, so continuity is required from the
        # centre of the first trail cell to the centre of the last one.
        row = layout.cell_point(0, 5)[1]
        start = layout.cell_point(10, 5)[0]
        end = layout.cell_point(19, 5)[0]
        gap = [
            x
            for x in range(start, end + 1)
            if renderer.screen.get_at((x, row))[:3] != OWNER_COLORS[0]
        ]
        assert gap == [], f"the trail is broken at columns {gap[:5]}"
    finally:
        pygame.quit()


def test_a_bend_in_the_trail_stays_connected():
    pygame.init()
    try:
        surface = pygame.Surface((1920, 1080))
        renderer = Renderer(surface)
        layout = renderer.layout
        game = make_game(width=40, height=24, player_count=1)
        for x in range(10, 16):
            game.field.set_trail(x, 5, owner=0)
        for y in range(6, 12):
            game.field.set_trail(15, y, owner=0)

        renderer.draw_game(game, None)

        corner = layout.cell_point(15, 5)
        assert renderer.screen.get_at(corner)[:3] == OWNER_COLORS[0]
        assert renderer.screen.get_at(layout.cell_point(15, 11))[:3] == OWNER_COLORS[0]
        assert renderer.screen.get_at(layout.cell_point(10, 5))[:3] == OWNER_COLORS[0]
    finally:
        pygame.quit()


def test_trails_of_different_owners_are_not_joined():
    pygame.init()
    try:
        surface = pygame.Surface((1920, 1080))
        renderer = Renderer(surface)
        layout = renderer.layout
        game = make_game(width=40, height=24, player_count=2)
        game.field.set_trail(10, 5, owner=0)
        game.field.set_trail(11, 5, owner=1)

        renderer.draw_game(game, None)

        left = layout.cell_point(10, 5)
        right = layout.cell_point(11, 5)
        row = left[1]
        boundary = layout.origin_x + 11 * layout.scale
        assert renderer.screen.get_at(left)[:3] == OWNER_COLORS[0]
        assert renderer.screen.get_at(right)[:3] == OWNER_COLORS[1]
        # The join between the two cells must not be painted as one line.
        assert renderer.screen.get_at((boundary, row))[:3] != OWNER_COLORS[0]
    finally:
        pygame.quit()


@pytest.mark.parametrize("window", [(720, 502), (1920, 1080), (2560, 1440)])
@pytest.mark.parametrize(
    "cells",
    [
        [(15, y) for y in range(5, 25)],
        [(10 + x, 5 + x) for x in range(12)],
        [(10 + x, 5 + x // 2) for x in range(12)],
    ],
    ids=["vertical", "diagonal", "staircase"],
)
def test_every_joint_between_trail_cells_is_drawn(window, cells):
    """Neighbouring trail cells must be joined, whichever way the line turns."""
    pygame.init()
    try:
        surface = pygame.Surface(window)
        renderer = Renderer(surface)
        layout = renderer.layout
        game = make_game(width=40, height=30, player_count=1)
        for cell in cells:
            game.field.set_trail(*cell, owner=0)

        renderer.draw_game(game, None)

        paintable = set(cells)
        broken = []
        for x, y in cells:
            centre = layout.cell_point(x, y)
            for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
                if (x + dx, y + dy) not in paintable:
                    continue
                other = layout.cell_point(x + dx, y + dy)
                midpoint = ((centre[0] + other[0]) // 2, (centre[1] + other[1]) // 2)
                if renderer.screen.get_at(midpoint)[:3] != OWNER_COLORS[0]:
                    broken.append(((x, y), (x + dx, y + dy)))
        assert broken == [], f"unjoined trail cells: {broken[:3]}"
    finally:
        pygame.quit()
