"""Rendering runs against an offscreen surface, so no window is needed."""

import pygame
import pytest

from tests.helpers import make_game
from xonix import config
from xonix.core.game import RoundResult
from xonix.render import (
    BACKGROUND,
    HEART_FILE,
    HEART_SIZE,
    HUD_BACKDROP,
    HUD_DIM,
    HUD_TEXT,
    OWNER_COLORS,
    PLAYER_NAMES,
    CaptureFlashes,
    Renderer,
    compute_layout,
    heart_sprite,
    lives_size,
    result_lines,
    row_runs,
    wins_text,
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


def hud_shows(renderer, text, colour, left, top, font=None, background=HUD_BACKDROP) -> bool:
    """Is ``text`` in ``colour`` painted at that spot, glyph for glyph?"""
    font = font or renderer.small
    width, height = font.size(text)
    expected = pygame.Surface((width, height))
    expected.fill(background)
    expected.blit(font.render(text, True, colour), (0, 0))
    actual = renderer.screen.subsurface(pygame.Rect(left, top, width, height)).copy()
    return bytes(expected.get_view("1")) == bytes(actual.get_view("1"))


def heart_asset() -> pygame.Surface:
    return pygame.image.load(str(HEART_FILE))


def heart_ink() -> list[tuple[int, int]]:
    """The sprite's own pixels that carry art, as (x, y) pairs."""
    sprite = heart_asset()
    return [
        (x, y)
        for x in range(HEART_SIZE[0])
        for y in range(HEART_SIZE[1])
        if sprite.get_at((x, y))[3]
    ]


def heart_colours() -> set[tuple[int, int, int]]:
    sprite = heart_asset()
    return {sprite.get_at((x, y))[:3] for x, y in heart_ink()}


def heart_red() -> tuple[int, int, int]:
    """The dominant red of the sprite, for checks that only need "red"."""
    return max(heart_colours(), key=lambda colour: colour[0])


def heart_row(renderer, game, owner: int) -> tuple[int, int]:
    """Where the HUD puts this player's hearts: left edge and top edge."""
    layout = renderer.layout
    player = game.players[owner]
    label = renderer.small.render(
        f"{PLAYER_NAMES[owner]} "
        f"{round(100.0 * player.score / game.field.playable_cells):d}%",
        True,
        (0, 0, 0),
    )
    margin = max(8, 2 * layout.scale)
    gap = max(8, renderer.small.get_height() // 2)
    width, height = lives_size(player.lives, renderer.heart, renderer.heart_gap)
    group = label.get_width() + gap + width
    left = margin if owner == 0 else layout.width - margin - group
    return left + label.get_width() + gap, (layout.hud_height - height) // 2


def heart_paint(renderer, rect) -> int:
    """How many pixels of a rect carry the sprite's own ink colours."""
    left, top, width, height = rect
    inks = heart_colours()
    return sum(
        renderer.screen.get_at((x, y))[:3] in inks
        for x in range(left, left + width)
        for y in range(top, top + height)
    )


def heart_rects(renderer, game, owner: int) -> list[tuple[int, int, int, int]]:
    """The rect each of this player's hearts is drawn into."""
    step = renderer.heart.get_width() + renderer.heart_gap
    left, top = heart_row(renderer, game, owner)
    return [
        (left + index * step, top, *renderer.heart.get_size())
        for index in range(game.players[owner].lives)
    ]


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
        # right aligned against the mirrored margin, each followed by its hearts.
        for owner, label, percent in ((0, "красный", 36), (1, "синий", 32)):
            text = f"{label} {percent}%"
            lives_width = lives_size(
                game.players[owner].lives, renderer.heart, renderer.heart_gap
            )[0]
            group = font.size(text)[0] + gap + lives_width
            left = margin if owner == 0 else layout.width - margin - group

            assert hud_shows(renderer, text, OWNER_COLORS[owner], left, row)
            assert not hud_shows(renderer, f"P{owner + 1} {percent}%", OWNER_COLORS[owner],
                                 left, row), "the numeric player label must be gone"
            assert not hud_shows(renderer, "xxx", HUD_TEXT, left + font.size(text)[0] + gap, row), \
                "the x marks must be gone"
    finally:
        pygame.quit()


def test_the_heart_asset_is_a_red_pixel_art_heart():
    """The sprite must be red, transparent around the art, and heart-shaped.

    This is the guard against the bug that started the change: a heart drawn
    from a font has no shape and came out as an empty box.
    """
    pygame.init()
    try:
        sprite = heart_asset()
        assert sprite.get_size() == HEART_SIZE, "the art must keep its own pixel grid"
        assert sprite.get_alpha() is not None, "the sprite needs transparency"
        assert sprite.get_at((0, 0))[3] == 0, "the corners must be transparent"

        ink = [
            (x, y)
            for x in range(HEART_SIZE[0])
            for y in range(HEART_SIZE[1])
            if sprite.get_at((x, y))[3]
        ]
        assert len(ink) < HEART_SIZE[0] * HEART_SIZE[1], "a filled square is not a heart"
        reds = [colour for colour in heart_colours() if colour[0] > 180]
        assert reds, "the heart must be red"
        assert all(colour[0] > colour[1] + 60 for colour in reds), "the ink must read red"

        top = [x for x in range(HEART_SIZE[0]) if sprite.get_at((x, 0))[3]]
        middle = HEART_SIZE[0] // 2
        assert middle not in top, "the top of a heart is two lobes, not one bar"
        assert top[0] == 2 and top[-1] == HEART_SIZE[0] - 3, "the lobes sit at the top corners"

        bottom = [x for x in range(HEART_SIZE[0]) if sprite.get_at((x, HEART_SIZE[1] - 1))[3]]
        width = lambda y: len([x for x in range(HEART_SIZE[0]) if sprite.get_at((x, y))[3]])
        assert len(bottom) <= 2, "a heart comes to a point at the bottom"
        assert width(0) > width(HEART_SIZE[1] - 1), "the art must taper downwards"
    finally:
        pygame.quit()


def test_the_heart_sprite_scales_by_whole_pixels_only():
    """Pixel art stays crisp, and the sprite grows with the HUD strip."""
    pygame.init()
    try:
        small = heart_sprite(22)
        large = heart_sprite(48)

        assert small.get_size() == HEART_SIZE, "the small HUD uses the native art"
        assert large.get_width() % HEART_SIZE[0] == 0, "the scale must be a whole number"
        assert large.get_height() == HEART_SIZE[1] * (large.get_width() // HEART_SIZE[0])
        assert large.get_width() > small.get_width(), "a large HUD gets large hearts"
        assert small.get_height() <= 22 and large.get_height() <= 48, "the art must fit the HUD"
        assert heart_sprite(22) is small, "the sprite must be cached between frames"
    finally:
        pygame.quit()


@pytest.mark.parametrize("lives", [3, 2, 1, 0])
def test_the_hud_draws_one_heart_per_life(lives):
    """The counter reads as hearts, and their number is the lives left."""
    pygame.init()
    try:
        renderer = Renderer(pygame.Surface((config.WINDOW_WIDTH, config.WINDOW_HEIGHT)))
        game = make_game(width=config.FIELD_WIDTH, height=config.FIELD_HEIGHT, player_count=2)
        game.players[0].lives = lives
        game.players[1].lives = lives
        renderer.screen.fill(BACKGROUND)

        renderer.draw_hud(game)

        for owner in (0, 1):
            rects = heart_rects(renderer, game, owner)
            assert len(rects) == lives, "one heart per life"
            for rect in rects:
                assert heart_paint(renderer, rect) > 0, "a life must paint a heart"
            if lives == 0:
                continue
            # A heart is not a filled box: its top corners carry no ink.
            left, top, width, _ = rects[0]
            assert renderer.screen.get_at((left, top))[:3] not in heart_colours()
            assert renderer.screen.get_at((left + width - 1, top))[:3] not in heart_colours()
    finally:
        pygame.quit()


def test_the_hud_places_each_heart_where_the_layout_says():
    """The hearts sit right after their own label, one sprite apart."""
    pygame.init()
    try:
        renderer = Renderer(pygame.Surface((config.WINDOW_WIDTH, config.WINDOW_HEIGHT)))
        layout = renderer.layout
        game = make_game(width=config.FIELD_WIDTH, height=config.FIELD_HEIGHT, player_count=2)
        game.players[0].lives = 3
        game.players[1].lives = 2
        renderer.screen.fill(BACKGROUND)

        renderer.draw_hud(game)

        step = renderer.heart.get_width() + renderer.heart_gap
        inks = heart_ink()
        for owner in (0, 1):
            rects = heart_rects(renderer, game, owner)
            assert len(rects) == game.players[owner].lives
            for rect in rects:
                assert heart_paint(renderer, rect) > 0, "a heart is missing from its slot"
                assert rect[0] >= 0 and rect[0] + rect[2] <= layout.width
                assert rect[1] >= 0 and rect[1] + rect[3] <= layout.hud_height
            # The gap between two hearts of one counter must stay empty.
            for left, top, width, height in rects[:-1]:
                gap_column = left + width
                assert not any(
                    renderer.screen.get_at((gap_column, y))[:3] in inks
                    for y in range(top, top + height)
                ), "the hearts of one counter must stay apart"
            # Both counters must sit on their own side of the screen.
            middle = layout.width // 2
            if owner == 0:
                assert rects[-1][0] + rects[-1][2] < middle, "the counters must not meet"
            else:
                assert rects[0][0] >= middle, "the counters must not meet"
        assert step > renderer.heart.get_width(), "the gap must separate the hearts"
    finally:
        pygame.quit()


@pytest.mark.parametrize("lives", [3, 2, 1])
def test_the_counters_keep_their_own_hearts(lives):
    """The two players may hold different lives; each group stays by its label."""
    pygame.init()
    try:
        renderer = Renderer(pygame.Surface((config.WINDOW_WIDTH, config.WINDOW_HEIGHT)))
        game = make_game(width=config.FIELD_WIDTH, height=config.FIELD_HEIGHT, player_count=2)
        game.players[0].lives = lives
        game.players[1].lives = config.START_LIVES
        renderer.screen.fill(BACKGROUND)

        renderer.draw_hud(game)

        assert len(heart_rects(renderer, game, 0)) == lives
        assert len(heart_rects(renderer, game, 1)) == config.START_LIVES
        for owner in (0, 1):
            assert all(
                heart_paint(renderer, rect) > 0
                for rect in heart_rects(renderer, game, owner)
            ), "a counter is missing a heart"
    finally:
        pygame.quit()


def test_the_hud_shows_hearts_instead_of_x_marks():
    """The old light x marks must be gone, and the hearts are not that mark."""
    pygame.init()
    try:
        renderer = Renderer(pygame.Surface((config.WINDOW_WIDTH, config.WINDOW_HEIGHT)))
        game = make_game(width=config.FIELD_WIDTH, height=config.FIELD_HEIGHT, player_count=1)
        game.players[0].lives = 3
        renderer.screen.fill(BACKGROUND)

        renderer.draw_hud(game)

        left, top = heart_row(renderer, game, 0)
        red = heart_red()
        assert len(heart_rects(renderer, game, 0)) == 3
        assert not hud_shows(renderer, "xxx", HUD_TEXT, left, top), "the x marks must be gone"
        assert not hud_shows(renderer, "xxx", red, left, top), "these are not x marks in red"
        assert all(
            heart_paint(renderer, rect) > 0 for rect in heart_rects(renderer, game, 0)
        )
        # A heart is not a filled block: its corners are empty, a box would not be.
        first = heart_rects(renderer, game, 0)[0]
        assert renderer.screen.get_at((first[0], first[1]))[:3] != red, "a box, not a heart"
        assert renderer.screen.get_at((first[0] + first[2] - 1, first[1]))[:3] != red
    finally:
        pygame.quit()


@pytest.mark.parametrize("window", [(720, 502), (1280, 892), (1920, 1338), (2560, 1784)])
def test_the_hearts_fit_the_hud_at_every_scale(window):
    """On a big display the hearts must still stay inside the HUD strip."""
    pygame.init()
    try:
        renderer = Renderer(pygame.Surface(window))
        layout = renderer.layout
        game = make_game(width=config.FIELD_WIDTH, height=config.FIELD_HEIGHT, player_count=2)
        renderer.screen.fill(BACKGROUND)

        renderer.draw_hud(game)

        _, height = lives_size(config.START_LIVES, renderer.heart, renderer.heart_gap)
        assert height <= layout.hud_height, "the hearts must fit the strip"
        for owner in (0, 1):
            rects = heart_rects(renderer, game, owner)
            assert len(rects) == config.START_LIVES
            assert rects[0][0] >= 0
            assert rects[-1][0] + renderer.heart.get_width() <= layout.width
            for rect in rects:
                assert rect[1] >= 0 and rect[1] + rect[3] <= layout.hud_height
                assert heart_paint(renderer, rect) > 0
    finally:
        pygame.quit()


def test_the_hearts_are_red_and_not_a_player_label_colour():
    inks = heart_colours()
    reds = [colour for colour in inks if colour[0] > 180]
    assert reds, "the heart must carry red pixels"
    assert all(colour[0] > colour[1] + 60 and colour[0] > colour[2] + 60 for colour in reds)
    assert all(colour not in OWNER_COLORS for colour in inks), "a heart repeats a label colour"
    assert HUD_TEXT not in inks and HUD_BACKDROP not in inks


def test_lives_size_counts_one_sprite_per_life():
    pygame.init()
    try:
        heart = heart_sprite(22)
        assert lives_size(0, heart, 3) == (0, heart.get_height())
        assert lives_size(1, heart, 3) == (heart.get_width(), heart.get_height())
        assert lives_size(3, heart, 3) == (3 * heart.get_width() + 6, heart.get_height())
    finally:
        pygame.quit()


def test_the_tally_is_bare_digits_red_then_blue():
    assert wins_text((0, 0)) == "0:0"
    assert wins_text((2, 1)) == "2:1"
    assert wins_text((5, 3)) == "5:3"


def finish_versus_game(player_count=2):
    game = make_game(width=config.FIELD_WIDTH, height=config.FIELD_HEIGHT, player_count=player_count)
    game.players[0].lives = 0
    game.players[0].alive = False
    game.tick()
    return game


def tally_spot(renderer, text):
    """Where the top-of-screen tally is centred, as the app draws it."""
    layout = renderer.layout
    width = renderer.score.size(text)[0]
    return (layout.width - width) // 2, 2 * layout.scale


def test_the_result_screen_shows_the_tally_large_at_the_top(surface):
    renderer = Renderer(surface)
    game = finish_versus_game()

    renderer.draw_result(game, [2, 1])

    text = wins_text((2, 1))
    left, top = tally_spot(renderer, text)
    assert hud_shows(renderer, text, HUD_TEXT, left, top, renderer.score, BACKGROUND), \
        "the versus result must show the running tally at the top"
    assert renderer.score.size(text)[1] > renderer.large.size(text)[1], \
        "the tally must be larger than the result headline"
    assert top < renderer.layout.height // 4, "the tally must sit near the top of the screen"


def test_the_solo_result_screen_has_no_tally(surface):
    renderer = Renderer(surface)
    game = finish_versus_game(player_count=1)

    renderer.draw_result(game, [3, 0])

    text = wins_text((3, 0))
    left, top = tally_spot(renderer, text)
    assert not hud_shows(renderer, text, HUD_TEXT, left, top, renderer.score, BACKGROUND), \
        "a solo round must not show a win tally"


def finished_game(lives, player_count=2, winner=0):
    """A game whose round is over, with the given lives left per player."""
    game = make_game(
        width=config.FIELD_WIDTH, height=config.FIELD_HEIGHT, player_count=player_count
    )
    percents = (56.0, 21.0) if player_count >= 2 else (54.0, 0.0)
    game.result = RoundResult("target", winner, (1000, 900), percents, tuple(lives))
    game.state = "finished"
    return game


def result_heart_rects(renderer, game):
    """Every heart the result screen draws, per owner."""
    solo = game.player_count < 2
    step = renderer.heart.get_width() + renderer.heart_gap
    rects = {}
    for owner, _label, _label_left, heart_left, row_top in renderer.result_lives_rows(
        game.result, solo
    ):
        size = renderer.heart.get_size()
        rects[owner] = [
            (heart_left + index * step, row_top, *size)
            for index in range(game.result.lives[owner])
        ]
    return rects


def test_the_result_screen_draws_one_heart_per_life_left(surface):
    renderer = Renderer(surface)
    game = finished_game(lives=(2, 0))

    renderer.draw_result(game, [1, 0])

    rects = result_heart_rects(renderer, game)
    assert len(rects[0]) == 2, "red had two lives left, so two hearts"
    assert rects[1] == [], "blue had none, so no hearts"
    assert all(heart_paint(renderer, rect) > 0 for rect in rects[0]), \
        "the hearts must be painted from the sprite"


def test_the_result_screen_does_not_spell_lives_as_words(surface):
    """The life counters read as hearts; the numbered phrasing must be gone.

    The check scans the band where the lives line used to sit: that is where a
    regression would draw the numbers, and a bounded scan keeps it fast.
    """
    renderer = Renderer(surface)
    game = finished_game(lives=(3, 0))

    renderer.draw_result(game, [1, 0])

    layout = renderer.layout
    rows = renderer.result_lives_rows(game.result, solo=False)
    top = min(row_top for _o, _l, _ll, _hl, row_top in rows)
    bottom = max(row_top for _o, _l, _ll, _hl, row_top in rows) + renderer.heart.get_height()
    colours = (*OWNER_COLORS, HUD_DIM, HUD_TEXT)
    for phrase in ("3 жизни", "1 жизнь", "0 жизней", "3 жизней"):
        width, height = renderer.small.size(phrase)
        found = any(
            hud_shows(renderer, phrase, colour, x, y, renderer.small, BACKGROUND)
            for colour in colours
            for y in range(top, min(bottom, layout.height - height) + 1)
            for x in range(layout.width - width + 1)
        )
        assert not found, f"the result screen must not spell lives: {phrase!r}"


def test_the_result_screen_keeps_the_colour_label_at_zero_lives(surface):
    renderer = Renderer(surface)
    game = finished_game(lives=(0, 3))

    renderer.draw_result(game, [0, 1])

    for owner, _label, label_left, heart_left, row_top in renderer.result_lives_rows(
        game.result, solo=False
    ):
        assert hud_shows(
            renderer,
            PLAYER_NAMES[owner],
            OWNER_COLORS[owner],
            label_left,
            row_top + (renderer.heart.get_height() - renderer.small.get_height()) // 2,
            renderer.small,
            BACKGROUND,
        ), "every counter keeps its colour label, even at zero lives"
        assert heart_left >= label_left


def test_the_solo_result_screen_shows_hearts_for_the_single_player(surface):
    renderer = Renderer(surface)
    game = finished_game(lives=(2,), player_count=1, winner=0)

    renderer.draw_result(game)

    rects = result_heart_rects(renderer, game)
    assert list(rects) == [0], "a solo round draws a counter only for its single player"
    assert len(rects[0]) == 2, "two lives left, so two hearts"
    assert all(heart_paint(renderer, rect) > 0 for rect in rects[0])


@pytest.mark.parametrize("window", [(720, 502), (1280, 892), (1920, 1338)])
def test_the_result_hearts_fit_the_window_at_every_scale(window):
    pygame.init()
    try:
        renderer = Renderer(pygame.Surface(window))
        layout = renderer.layout
        game = finished_game(lives=(3, 3))

        renderer.draw_result(game, [2, 1])

        rows = renderer.result_lives_rows(game.result, solo=False)
        for owner, _label, label_left, heart_left, row_top in rows:
            assert label_left >= 0, "the counter must not spill off the left edge"
            step = renderer.heart.get_width() + renderer.heart_gap
            count = game.result.lives[owner]
            right = heart_left + count * step - renderer.heart_gap
            assert right <= layout.width, "the heart row must fit the window width"
            assert row_top >= 0
            assert row_top + renderer.heart.get_height() <= layout.height
        tops = [row_top for _o, _l, _ll, _hl, row_top in rows]
        assert tops[0] != tops[1], "the two counters must not sit on the same line"
        assert abs(tops[0] - tops[1]) >= renderer.heart.get_height(), \
            "the counters must not overlap"
    finally:
        pygame.quit()
