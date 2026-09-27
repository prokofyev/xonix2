"""Drawing: field, trails, balls, capture flashes, HUD and the menu screens.

The field is always drawn at an integer number of pixels per cell, chosen so it
fits the window: whole pixels keep the grid crisp, and any leftover space becomes
a plain letterbox. Everything else in this module is expressed in cell-size
multiples, so one renderer works in a small window and on a large display.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pygame

from xonix import config
from xonix.core.field import State

BACKGROUND = (11, 15, 20)
LAND = (42, 47, 58)
BALL = (232, 238, 245)
HUD_TEXT = (226, 232, 240)
HUD_DIM = (140, 152, 168)
HUD_BACKDROP = (11, 15, 20)
# Lives are drawn from a pixel-art heart sprite. The default pygame font has no
# heart glyph, so a text mark is not an option: it paints an empty box. The
# sprite is red for both players, since which counter it belongs to is already
# told by the coloured name in front of it.
HEART_FILE = Path(__file__).resolve().parent / "assets" / "heart.png"
# Native size of the sprite, in its own pixels.
HEART_SIZE = (16, 13)
# The sprite is scaled by whole pixels only, so the art keeps its blocky edges
# instead of blurring into a smudge.
_HEART_CACHE: dict[int, pygame.Surface] = {}
OWNER_COLORS = (config.WARM, config.COOL)
# The players are named after their trail colour: the warm one reads red, the
# cool one reads blue, and the HUD and the result screen must use one name each.
PLAYER_NAMES = ("красный", "синий")
PLAYER_NAME_TITLES = ("Красный", "Синий")
# "У красного кончились жизни": the name is the subject of a possessive phrase.
PLAYER_NAME_GENITIVE = ("красного", "синего")
FLASH_ALPHA = 190


@dataclass(frozen=True)
class Layout:
    """Where the field sits in a window, and how big everything is drawn."""

    width: int
    height: int
    scale: int
    origin_x: int
    origin_y: int
    hud_height: int
    small_font: int
    medium_font: int
    large_font: int
    score_font: int

    def cell_point(self, x: int, y: int) -> tuple[int, int]:
        """Centre of a field cell, in window pixels."""
        return (
            self.origin_x + x * self.scale + self.scale // 2,
            self.origin_y + y * self.scale + self.scale // 2,
        )

    def cell_rect(self, x: int, y: int, w: int = 1, h: int = 1) -> tuple[int, int, int, int]:
        return (
            self.origin_x + x * self.scale,
            self.origin_y + y * self.scale,
            w * self.scale,
            h * self.scale,
        )


def compute_layout(window_size: tuple[int, int]) -> Layout:
    """Pick the largest whole-pixel cell size that fits, and centre the field.

    Integer scaling is what keeps the grid crisp: there is no interpolation
    anywhere, so a cell is always a square block of identical pixels. The HUD
    strip is reserved above the field rather than drawn over it, so no playable
    cell is ever hidden, and whatever space is left becomes a letterbox.
    """
    width, height = int(window_size[0]), int(window_size[1])
    scale = max(
        1,
        min(
            width // config.FIELD_WIDTH,
            (height - config.HUD_MIN_HEIGHT) // config.FIELD_HEIGHT,
        ),
    )
    hud_height = max(config.HUD_MIN_HEIGHT, config.HUD_SCALE_FACTOR * scale)
    while scale > 1 and hud_height + config.FIELD_HEIGHT * scale > height:
        scale -= 1
        hud_height = max(config.HUD_MIN_HEIGHT, config.HUD_SCALE_FACTOR * scale)
    field_width = min(config.FIELD_WIDTH * scale, width)
    field_height = min(config.FIELD_HEIGHT * scale, max(0, height - hud_height))
    return Layout(
        width=width,
        height=height,
        scale=scale,
        origin_x=(width - field_width) // 2,
        origin_y=hud_height + (height - hud_height - field_height) // 2,
        hud_height=hud_height,
        small_font=max(18, 3 * scale),
        medium_font=max(28, 4 * scale),
        large_font=max(48, 7 * scale),
        # The running versus tally is the biggest mark on the result screen,
        # so it gets its own step above the headline size.
        score_font=max(90, 15 * scale),
    )


def heart_sprite(hud_height: int) -> pygame.Surface:
    """The heart at the largest whole-pixel scale that still fits the HUD.

    Scaling by an integer keeps pixel art crisp, and the sprite is scaled per
    HUD height rather than per window, so the hearts grow with the counters on a
    large display. The surface is cached: the HUD is redrawn every frame.
    """
    factor = max(1, (int(hud_height) - 2) // HEART_SIZE[1])
    cached = _HEART_CACHE.get(factor)
    if cached is None:
        source = pygame.image.load(str(HEART_FILE))
        if pygame.display.get_surface() is not None:
            source = source.convert_alpha()
        cached = pygame.transform.scale(
            source, (HEART_SIZE[0] * factor, HEART_SIZE[1] * factor)
        )
        _HEART_CACHE[factor] = cached
    return cached


def lives_size(count: int, heart: pygame.Surface, gap: int) -> tuple[int, int]:
    """Bounding size of a row of ``count`` hearts separated by ``gap`` pixels."""
    lives = max(0, int(count))
    if lives == 0:
        return 0, heart.get_height()
    return (
        lives * heart.get_width() + (lives - 1) * gap,
        heart.get_height(),
    )


def lives_word(count: int) -> str:
    """Russian plural for a life count: 1 жизнь, 2 жизни, 5 жизней."""
    if count % 10 == 1 and count % 100 != 11:
        return "жизнь"
    if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
        return "жизни"
    return "жизней"


def lives_text(result, solo: bool) -> str:
    """Remaining lives of each player, e.g. "красный 3 жизни   синий 0 жизней"."""
    counts = result.lives[: 1 if solo else 2]
    return "   ".join(
        f"{PLAYER_NAMES[index]} {count} {lives_word(count)}"
        for index, count in enumerate(counts)
    )


def wins_text(wins) -> str:
    """The versus tally as bare digits, red first: "2:1"."""
    return f"{int(wins[0])}:{int(wins[1])}"


def score_text(result, solo: bool) -> str:
    """The percentages of the players, e.g. "57% против 21%"."""
    if solo:
        return f"{round(result.percents[0]):d}%"
    return (
        f"{round(result.percents[0]):d}% против {round(result.percents[1]):d}%"
    )


def result_lines(result, solo: bool) -> tuple[str, str | None]:
    """Headline and optional detail line for the result screen.

    The headline always names the reason: whose lives ran out, or who won on
    points. The score belongs in the headline when points decided the round,
    and on its own line otherwise, so it is never printed twice.
    """
    if solo:
        # The round stops at 75% of the field, not at a cleared field, so the
        # headline names the threshold instead of claiming the field is empty.
        if result.kind == "target":
            return f"Цель достигнута — {score_text(result, solo)}", None
        return f"У {PLAYER_NAME_GENITIVE[0]} кончились жизни", score_text(result, solo)
    if result.kind == "lives":
        if result.winner is None:
            return "У обоих кончились жизни", score_text(result, solo)
        loser = 1 - result.winner
        return f"У {PLAYER_NAME_GENITIVE[loser]} кончились жизни", score_text(result, solo)
    if result.winner is None:
        return f"Ничья — {score_text(result, solo)}", None
    winner = result.winner
    winner_percent = round(result.percents[winner])
    loser_percent = round(result.percents[1 - winner])
    headline = (
        f"{PLAYER_NAME_TITLES[winner]} победил — "
        f"{winner_percent}% против {loser_percent}%"
    )
    return headline, None


def row_runs(cells: bytearray, width: int, height: int, state: int):
    """Merge each row's equal cells into runs, so drawing stays cheap."""
    for y in range(height):
        start = None
        for x in range(width):
            if cells[y * width + x] == state:
                if start is None:
                    start = x
            elif start is not None:
                yield y, start, x
                start = None
        if start is not None:
            yield y, start, width


class CaptureFlashes:
    """Short-lived colour bursts marking who just took which cells.

    This is display-only state: it never feeds back into the simulation.
    """

    def __init__(self, seconds: float = config.CAPTURE_FLASH_SECONDS) -> None:
        self.seconds = seconds
        self._entries: list[tuple[list[tuple[int, int]], int, float]] = []

    def add(self, cells: list[tuple[int, int]], owner: int) -> None:
        if cells:
            self._entries.append((cells, owner, self.seconds))

    def update(self, dt: float) -> None:
        refreshed = []
        for cells, owner, remaining in self._entries:
            remaining -= dt
            if remaining > 0:
                refreshed.append((cells, owner, remaining))
        self._entries = refreshed

    def active_cells(self) -> list[tuple[int, int, int, float]]:
        """Cells to highlight, as (x, y, owner, strength)."""
        result = []
        for cells, owner, remaining in self._entries:
            strength = remaining / self.seconds
            result.extend((x, y, owner, strength) for x, y in cells)
        return result

    def active_runs(self) -> list[tuple[int, int, int, int, int]]:
        """Highlighted cells merged into horizontal spans.

        Returns (x, y, width, owner, alpha). A single landing can turn a large
        part of the field, and every captured cell flashes; blitting thousands
        of one-cell patches does not fit in a frame on a large display, while
        merging touching cells into spans cuts the blit count by orders of
        magnitude for exactly the big claims that used to hurt.
        """
        rows: dict[tuple[int, int, int], list[int]] = {}
        for cells, owner, remaining in self._entries:
            strength = remaining / self.seconds
            alpha = int(FLASH_ALPHA * max(0.0, min(1.0, strength)))
            if alpha <= 0:
                continue
            for x, y in cells:
                rows.setdefault((owner, alpha, y), []).append(x)
        runs = []
        for (owner, alpha, y), columns in rows.items():
            columns.sort()
            start = previous = columns[0]
            for x in columns[1:]:
                if x != previous + 1:
                    runs.append((start, y, previous - start + 1, owner, alpha))
                    start = x
                previous = x
            runs.append((start, y, previous - start + 1, owner, alpha))
        return runs

    def clear(self) -> None:
        self._entries = []


class Renderer:
    def __init__(self, screen: pygame.Surface) -> None:
        self.set_screen(screen)

    def set_screen(self, screen: pygame.Surface) -> None:
        """Adopt a new surface, which happens when the display mode changes."""
        if not pygame.font.get_init():
            # The renderer must work on its own surface, not only inside App.
            pygame.font.init()
        self.screen = screen
        self.layout = compute_layout(screen.get_size())
        self.heart = heart_sprite(self.layout.hud_height)
        # Hearts nearly touch in the sprite, so a small gap keeps the marks of a
        # counter apart instead of fusing into one long blob.
        self.heart_gap = max(1, self.heart.get_width() // 8)
        self.small = pygame.font.Font(None, self.layout.small_font)
        self.medium = pygame.font.Font(None, self.layout.medium_font)
        self.large = pygame.font.Font(None, self.layout.large_font)
        self.score = pygame.font.Font(None, self.layout.score_font)

    @property
    def scale(self) -> int:
        return self.layout.scale

    def draw_game(self, game, flashes: CaptureFlashes | None = None) -> None:
        field = game.field
        layout = self.layout
        self.screen.fill(BACKGROUND)
        for y, x0, x1 in row_runs(field.cells, field.width, field.height, State.LAND):
            pygame.draw.rect(self.screen, LAND, layout.cell_rect(x0, y, x1 - x0))
        self._draw_trails(field)
        if flashes is not None:
            self._draw_flashes(flashes)
        for ball in game.balls:
            pygame.draw.circle(
                self.screen,
                BALL,
                layout.cell_point(ball.x, ball.y),
                max(1, layout.scale // 2 - 1),
            )
        for player in game.players:
            pygame.draw.circle(
                self.screen,
                OWNER_COLORS[player.owner % len(OWNER_COLORS)],
                layout.cell_point(player.x, player.y),
                max(2, layout.scale // 2),
            )
        self.draw_hud(game)

    def _draw_trails(self, field) -> None:
        """Draw each trail as a thin line, not as a filled cell.

        A cell alone is drawn as a small centred block; where a neighbouring
        cell belongs to the same trail, a band is drawn towards it. The result
        is a connected polyline at every scale, which keeps a trail readable as
        a dangerous line instead of a row of blocks that looks like land.
        """
        layout = self.layout
        cells = field.cells
        owner_of = field.trail_owner
        width = field.width
        height = field.height
        thickness = max(2, layout.scale // 4)
        half = thickness // 2
        # Reach exactly to the neighbouring cell's centre, so segments meet even
        # when the cell size is odd (scale // 2 alone leaves a one-pixel gap).
        reach = layout.scale - layout.scale // 2
        for index, state in enumerate(cells):
            if state != State.TRAIL:
                continue
            owner = owner_of[index]
            colour = OWNER_COLORS[owner % len(OWNER_COLORS)] if owner != 0xFF else BALL
            x = index % width
            y = index // width
            left = layout.origin_x + x * layout.scale
            top = layout.origin_y + y * layout.scale
            centre_x = left + layout.scale // 2
            centre_y = top + layout.scale // 2
            pygame.draw.rect(
                self.screen,
                colour,
                (centre_x - half, centre_y - half, thickness, thickness),
            )
            for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
                nx, ny = x + dx, y + dy
                if not (0 <= nx < width and 0 <= ny < height):
                    continue
                neighbour = ny * width + nx
                if cells[neighbour] != State.TRAIL or owner_of[neighbour] != owner:
                    continue
                if dx > 0:
                    pygame.draw.rect(
                        self.screen, colour, (centre_x, centre_y - half, reach, thickness)
                    )
                elif dx < 0:
                    pygame.draw.rect(
                        self.screen, colour, (centre_x - reach, centre_y - half, reach, thickness)
                    )
                elif dy > 0:
                    pygame.draw.rect(
                        self.screen, colour, (centre_x - half, centre_y, thickness, reach)
                    )
                else:
                    pygame.draw.rect(
                        self.screen, colour, (centre_x - half, centre_y - reach, thickness, reach)
                    )

    def _draw_flashes(self, flashes: CaptureFlashes) -> None:
        layout = self.layout
        scale = layout.scale
        origin_x, origin_y = layout.origin_x, layout.origin_y
        patches: dict[tuple[int, int, int], pygame.Surface] = {}
        for x, y, width, owner, alpha in flashes.active_runs():
            key = (owner, alpha, width)
            patch = patches.get(key)
            if patch is None:
                colour = OWNER_COLORS[owner % len(OWNER_COLORS)]
                patch = pygame.Surface((width * scale, scale), pygame.SRCALPHA)
                patch.fill((*colour, alpha))
                patches[key] = patch
            self.screen.blit(patch, (origin_x + x * scale, origin_y + y * scale))

    def draw_hud(self, game) -> None:
        """Percent and life counters, named after each player's colour."""
        layout = self.layout
        pygame.draw.rect(
            self.screen, HUD_BACKDROP, (0, 0, layout.width, layout.hud_height)
        )
        margin = max(8, 2 * layout.scale)
        gap = max(8, self.small.get_height() // 2)
        spare = layout.hud_height - self.small.get_height()
        row = spare // 2 if spare > 0 else 0
        for player in game.players:
            percent = 100.0 * player.score / game.field.playable_cells
            label = f"{PLAYER_NAMES[player.owner]} {round(percent):d}%"
            colour = OWNER_COLORS[player.owner % len(OWNER_COLORS)]
            text = self.small.render(label, True, colour)
            lives_width, lives_height = lives_size(player.lives, self.heart, self.heart_gap)
            group = text.get_width() + gap + lives_width
            left = margin if player.owner == 0 else layout.width - margin - group
            self.screen.blit(text, (left, row))
            heart_left = left + text.get_width() + gap
            heart_top = (layout.hud_height - lives_height) // 2
            for index in range(player.lives):
                self.screen.blit(
                    self.heart,
                    (heart_left + index * (self.heart.get_width() + self.heart_gap), heart_top),
                )

    def draw_pause(self) -> None:
        layout = self.layout
        veil = pygame.Surface((layout.width, layout.height), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 140))
        self.screen.blit(veil, (0, 0))
        centre = layout.height // 2
        self._centre_text("ПАУЗА", centre - 40, self.large, HUD_TEXT)
        self._centre_text(
            "P — продолжить    R — заново    Esc — в меню    F11 — во весь экран",
            centre + 40,
            self.small,
            HUD_DIM,
        )

    def draw_menu(self) -> None:
        layout = self.layout
        self.screen.fill(BACKGROUND)
        centre = layout.height // 2
        self._centre_text("XONIX", centre - 13 * layout.scale, self.large, HUD_TEXT)
        self._centre_text(
            "1 — один игрок", centre - 2 * layout.scale, self.medium, OWNER_COLORS[0]
        )
        self._centre_text(
            "2 — двое игроков", centre + 5 * layout.scale, self.medium, OWNER_COLORS[1]
        )
        self._centre_text(
            f"{PLAYER_NAMES[0]}: W A S D     {PLAYER_NAMES[1]}: стрелки     "
            "P — пауза     R — заново",
            centre + 15 * layout.scale,
            self.small,
            HUD_DIM,
        )
        self._centre_text(
            "F11 — во весь экран    Esc — выход", centre + 20 * layout.scale,
            self.small, HUD_DIM,
        )

    def draw_result(self, game, wins=None) -> None:
        layout = self.layout
        self.screen.fill(BACKGROUND)
        result = game.result
        if result is None:
            return
        centre = layout.height // 2
        solo = game.player_count < 2
        headline, score = result_lines(result, solo)
        self._centre_text(headline, centre - 25 * layout.scale, self.large, HUD_TEXT)
        if score is not None:
            self._centre_text(score, centre - 12 * layout.scale, self.medium, HUD_TEXT)
        self._centre_text(
            lives_text(result, solo), centre - 5 * layout.scale, self.small, HUD_DIM
        )
        if wins is not None and not solo:
            # The running tally is a versus feature, so a solo round hides it.
            # It sits at the very top, large: "red:blue", the order the players
            # are named everywhere else.
            self._centre_text(wins_text(wins), 2 * layout.scale, self.score, HUD_TEXT)
        self._centre_text(
            "Enter — в меню    R — ещё раз    F11 — во весь экран",
            centre + 13 * layout.scale,
            self.medium,
            HUD_DIM,
        )

    def _centre_text(self, text: str, y: int, font, colour) -> None:
        surface = font.render(text, True, colour)
        self.screen.blit(surface, ((self.layout.width - surface.get_width()) // 2, y))
