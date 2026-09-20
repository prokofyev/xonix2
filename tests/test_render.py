"""Rendering runs against an offscreen surface, so no window is needed."""

import pygame
import pytest

from tests.helpers import make_game
from xonix import config
from xonix.core.game import RoundResult
from xonix.render import (
    BACKGROUND,
    HUD_BACKDROP,
    OWNER_COLORS,
    CaptureFlashes,
    Renderer,
    compute_layout,
    lives_text,
    lives_word,
    result_lines,
    row_runs,
)


@pytest.fixture
def surface():
    pygame.init()
    surface = pygame.Surface((config.WINDOW_WIDTH, config.WINDOW_HEIGHT))
    yield surface
    pygame.quit()


def test_land_is_painted_in_a_single_colour(surface):
    from tests.helpers import carve_land, make_game
    from xonix.core.field import State

    game = make_game(width=40, height=24, player_count=2)
    carve_land(game.field, [(x, 5) for x in range(1, 20)])

    runs = list(row_runs(game.field.cells, game.field.width, game.field.height, State.LAND))

    painted_row = set()
    for y, x0, x1 in runs:
        assert game.field.state(x0, y) == State.LAND
        if y == 5:
            painted_row.update(range(x0, x1))
    assert painted_row == set(range(20)) | {0, 39}


def test_trail_is_never_merged_into_a_land_run():
    from tests.helpers import carve_land, make_game
    from xonix.core.field import State

    game = make_game(width=20, height=12)
    carve_land(game.field, [(x, 5) for x in range(1, 6)])
    game.field.set_trail(7, 5, owner=0)
    game.field.set_trail(8, 5, owner=1)

    runs = list(row_runs(game.field.cells, game.field.width, game.field.height, State.LAND))

    covered = {x for row, x0, x1 in runs if row == 5 for x in range(x0, x1)}
    assert 7 not in covered
    assert 8 not in covered
    assert {1, 2, 3, 4, 5} <= covered


def test_flashes_fade_and_expire():
    flashes = CaptureFlashes(seconds=0.5)
    flashes.add([(1, 1), (2, 2)], owner=0)

    assert len(flashes.active_cells()) == 2
    flashes.update(0.25)
    strengths = [strength for _, _, _, strength in flashes.active_cells()]
    assert all(0 < strength < 1 for strength in strengths)

    flashes.update(0.3)
    assert flashes.active_cells() == []


def test_flashes_carry_the_owner_for_colouring():
    flashes = CaptureFlashes()
    flashes.add([(3, 3)], owner=1)

    _, _, owner, _ = flashes.active_cells()[0]

    assert owner == 1


def test_drawing_a_round_and_a_result_does_not_raise(surface):
    from tests.helpers import make_game

    renderer = Renderer(surface)
    game = make_game(width=config.FIELD_WIDTH, height=config.FIELD_HEIGHT, player_count=2)
    flashes = CaptureFlashes()
    flashes.add([(10, 10)], 0)

    renderer.draw_game(game, flashes)
    renderer.draw_hud(game)
    renderer.draw_pause()
    renderer.draw_menu()

    game.players[1].lives = 0
    game.players[1].alive = False
    game.tick()
    renderer.draw_result(game)


def test_the_reference_layout_matches_the_configured_cell_size():
    layout = compute_layout((config.WINDOW_WIDTH, config.WINDOW_HEIGHT))

    assert layout.scale == config.CELL_SIZE
    assert layout.origin_x == 0
    assert layout.origin_y == layout.hud_height
    assert layout.origin_y + config.FIELD_HEIGHT * layout.scale == config.WINDOW_HEIGHT
    assert config.CELL_SIZE * config.FIELD_WIDTH == config.FIELD_PIXEL_WIDTH
    assert config.CELL_SIZE * config.FIELD_HEIGHT == config.FIELD_PIXEL_HEIGHT


def test_flash_runs_merge_neighbouring_cells_into_spans():
    """A landing claims thousands of cells; the flash must not be cell-by-cell."""
    flashes = CaptureFlashes()
    flashes.add([(x, 5) for x in range(3, 9)] + [(20, 5), (21, 5)], owner=0)

    runs = {(y, x): (width, owner) for x, y, width, owner, _ in flashes.active_runs()}

    assert runs[(5, 3)] == (6, 0), "the touching cells must merge into one span"
    assert runs[(5, 20)] == (2, 0), "cells separated by a gap must not merge"
    assert set(runs) == {(5, 3), (5, 20)}


def test_flash_runs_keep_owners_and_rows_apart():
    flashes = CaptureFlashes()
    flashes.add([(1, 1), (2, 1), (1, 2)], owner=0)
    flashes.add([(3, 1)], owner=1)

    runs = [(x, y, width, owner) for x, y, width, owner, _ in flashes.active_runs()]

    assert (1, 1, 2, 0) in runs
    assert (1, 2, 1, 0) in runs, "a different row is a different span"
    assert (3, 1, 1, 1) in runs, "a different owner is a different span"


def test_flash_runs_cover_every_highlighted_cell():
    flashes = CaptureFlashes()
    cells = [(x, y) for y in range(2, 9) for x in range(4, 12) if (x + y) % 3]
    flashes.add(cells, owner=1)

    covered = set()
    for x, y, width, owner, _ in flashes.active_runs():
        assert owner == 1
        covered.update((x + step, y) for step in range(width))

    assert covered == set(cells)


def test_a_whole_row_capture_flashes_as_one_span():
    """The cost guard for the flash: touching cells must merge, not blit each."""
    pygame.init()
    try:
        surface = pygame.Surface((1920, 1080))
        renderer = Renderer(surface)
        layout = renderer.layout
        game = make_game(width=config.FIELD_WIDTH, height=config.FIELD_HEIGHT, player_count=1)
        flashes = CaptureFlashes()
        row = [(x, 10) for x in range(1, config.FIELD_WIDTH - 1)]
        flashes.add(row, owner=0)

        renderer.draw_game(game, flashes)

        runs = flashes.active_runs()
        assert len(runs) == 1, f"a contiguous claim became {len(runs)} spans"
        assert runs[0][2] == config.FIELD_WIDTH - 2, "the span must cover the whole row"
        for x in (1, config.FIELD_WIDTH // 2, config.FIELD_WIDTH - 2):
            assert renderer.screen.get_at(layout.cell_point(x, 10))[:3] != BACKGROUND
    finally:
        pygame.quit()


def test_an_entire_field_capture_flashes_as_few_spans():
    """The worst case a landing can produce must not become thousands of blits."""
    pygame.init()
    try:
        surface = pygame.Surface((1920, 1080))
        renderer = Renderer(surface)
        game = make_game(width=config.FIELD_WIDTH, height=config.FIELD_HEIGHT, player_count=1)
        flashes = CaptureFlashes()
        everything = [
            (x, y)
            for y in range(1, config.FIELD_HEIGHT - 1)
            for x in range(1, config.FIELD_WIDTH - 1)
        ]
        flashes.add(everything, owner=0)

        renderer.draw_game(game, flashes)

        assert len(flashes.active_runs()) == config.FIELD_HEIGHT - 2, "one span per captured row"
    finally:
        pygame.quit()


def result(kind, winner, percents, lives=(3, 3)) -> RoundResult:
    return RoundResult(kind, winner, (1000, 900), percents, lives)


def test_the_result_names_players_by_colour_not_by_number():
    headline, _ = result_lines(result("lives", 1, (13.0, 8.7), lives=(2, 0)), solo=False)

    assert headline == "У красного кончились жизни"
    assert "P1" not in headline and "P2" not in headline


def test_the_result_says_whose_lives_ran_out():
    first_out, _ = result_lines(result("lives", 1, (20.0, 5.0), lives=(0, 3)), solo=False)
    second_out, _ = result_lines(result("lives", 0, (5.0, 20.0), lives=(3, 0)), solo=False)

    assert first_out == "У красного кончились жизни"
    assert second_out == "У синего кончились жизни"


def test_losing_both_players_at_once_is_a_draw_without_a_loser():
    headline, score = result_lines(result("lives", None, (8.7, 9.8), lives=(0, 0)), solo=False)

    assert headline == "У обоих кончились жизни"
    assert score == "9% против 10%"


def test_a_points_win_puts_the_score_in_the_headline():
    headline, score = result_lines(result("target", 0, (56.5, 20.6)), solo=False)

    assert headline == "Красный победил — 56% против 21%"
    assert score is None, "the score must not be printed twice"


def test_the_second_player_winning_is_named_too():
    headline, _ = result_lines(result("target", 1, (20.6, 56.5)), solo=False)

    assert headline == "Синий победил — 56% против 21%"


def test_a_points_draw_says_so_with_the_equal_score():
    headline, score = result_lines(result("target", None, (35.9, 35.9)), solo=False)

    assert headline == "Ничья — 36% против 36%"
    assert score is None


def test_the_solo_result_names_the_reason_without_a_second_player():
    reached, reached_score = result_lines(result("target", 0, (54.3, 0.0)), solo=True)
    defeated, defeated_score = result_lines(result("defeat", None, (9.8, 0.0)), solo=True)

    assert reached == "Цель достигнута — 54%", "the round stops at 75%, it is not a cleared field"
    assert reached_score is None
    assert defeated == "У красного кончились жизни"
    assert defeated_score == "10%", "a solo defeat still shows how far the player got"


def test_the_life_count_declines_correctly():
    assert lives_word(1) == "жизнь"
    assert lives_word(2) == "жизни"
    assert lives_word(3) == "жизни"
    assert lives_word(5) == "жизней"
    assert lives_word(0) == "жизней"
    assert lives_word(11) == "жизней"
    assert lives_word(21) == "жизнь"


def test_the_result_shows_how_many_lives_each_player_had_left():
    both = lives_text(result("target", 0, (56.5, 20.6), lives=(3, 1)), solo=False)
    solo = lives_text(result("defeat", None, (9.8, 0.0), lives=(0, 0)), solo=True)

    assert both == "красный 3 жизни   синий 1 жизнь"
    assert solo == "красный 0 жизней"


def hud_shows(renderer, text, colour, left, top) -> bool:
    """Is ``text`` in ``colour`` painted at that spot, glyph for glyph?"""
    font = renderer.small
    width, height = font.size(text)
    expected = pygame.Surface((width, height))
    expected.fill(HUD_BACKDROP)
    expected.blit(font.render(text, True, colour), (0, 0))
    actual = renderer.screen.subsurface(pygame.Rect(left, top, width, height)).copy()
    return bytes(expected.get_view("1")) == bytes(actual.get_view("1"))


def test_the_hud_names_the_players_by_colour():
    """The counters must read "красный 36%", not "P1 36%"."""
    pygame.init()
    try:
        renderer = Renderer(pygame.Surface((config.WINDOW_WIDTH, config.WINDOW_HEIGHT)))
        layout = renderer.layout
        font = renderer.small
        game = make_game(width=config.FIELD_WIDTH, height=config.FIELD_HEIGHT, player_count=2)
        game.players[0].score = round(game.field.playable_cells * 0.36)
        game.players[1].score = round(game.field.playable_cells * 0.32)

        renderer.draw_hud(game)

        row = (layout.hud_height - font.get_height()) // 2
        margin = max(8, 2 * layout.scale)
        gap = max(8, font.get_height() // 2)
        # Both labels are laid out exactly as the HUD does: left from the margin,
        # right aligned against the mirrored margin, each followed by its lives.
        for owner, label, percent, lives in ((0, "красный", 36, 3), (1, "синий", 32, 3)):
            text = f"{label} {percent}%"
            lives_width = font.size("x" * lives)[0]
            group = font.size(text)[0] + gap + lives_width
            left = margin if owner == 0 else layout.width - margin - group

            assert hud_shows(renderer, text, OWNER_COLORS[owner], left, row)
            assert not hud_shows(renderer, f"P{owner + 1} {percent}%", OWNER_COLORS[owner],
                                 left, row), "the numeric player label must be gone"
    finally:
        pygame.quit()
