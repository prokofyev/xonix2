"""The pygame shell: MENU, PLAY and RESULT around the simulation core.

The game starts fullscreen, scaled to the largest whole-pixel cell size the
display allows, with F11 (or Alt+Enter) switching back to a window. Everything
about a round is decided by the core; this module only moves keys in and pixels
out.
"""

from __future__ import annotations

import pygame

from xonix import config, input as game_input
from xonix.core.clock import TickClock
from xonix.core.game import Game
from xonix.render import CaptureFlashes, Renderer

MENU = "menu"
PLAY = "play"
RESULT = "result"

# A frame longer than this is treated as a stall, not as gameplay time to catch
# up on: a dragged or minimised window must not replay hundreds of ticks at once.
MAX_FRAME_SECONDS = 0.1


class App:
    def __init__(self, screen: pygame.Surface | None = None, fullscreen: bool = True) -> None:
        pygame.init()
        self._owns_screen = screen is None
        self.fullscreen = fullscreen and self._owns_screen
        self.windowed_size = (config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        self.screen = self._create_surface(screen)
        pygame.display.set_caption("Xonix")
        self.renderer = Renderer(self.screen)
        self.clock = pygame.time.Clock()
        self.ticks = TickClock()
        self.flashes = CaptureFlashes()
        self.tracker = game_input.DirectionTracker(player_count=2)
        self.game: Game | None = None
        self.player_count = 2
        self.state = MENU
        self.paused = False
        self.running = True
        # Wins counted per colour for the current session of versus play. The
        # core models one round, so a running tally belongs to the shell.
        self.win_counts = [0, 0]

    def _create_surface(self, screen: pygame.Surface | None) -> pygame.Surface:
        if screen is not None:
            return screen
        if self.fullscreen:
            return pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        return pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)

    def toggle_fullscreen(self) -> None:
        if not self._owns_screen:
            return
        if not self.fullscreen:
            self.windowed_size = self.screen.get_size()
        self.fullscreen = not self.fullscreen
        self.screen = self._create_surface(None)
        self.renderer.set_screen(self.screen)

    def start_round(self, player_count: int, reset_wins: bool = False) -> None:
        if reset_wins:
            # A fresh match from the menu starts the tally over. A restart of
            # the round keeps it, so the players can continue their series.
            self.win_counts = [0, 0]
        self.player_count = player_count
        self.game = Game(player_count=player_count, seed=None)
        self.tracker = game_input.DirectionTracker(player_count=player_count)
        self.flashes.clear()
        self.ticks.reset()
        self.paused = False
        self.state = PLAY

    def run(self) -> None:
        while self.running:
            elapsed = self.clock.tick(config.TICKS_PER_SECOND) / 1000.0
            self.handle_events()
            self.update(min(elapsed, MAX_FRAME_SECONDS))
            self.draw()
            pygame.display.flip()
        if self._owns_screen:
            pygame.quit()

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.VIDEORESIZE:
                if not self.fullscreen and self._owns_screen:
                    self.windowed_size = (event.w, event.h)
                    self.screen = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)
                    self.renderer.set_screen(self.screen)
            elif event.type == pygame.KEYDOWN:
                self._key_down(event.key, getattr(event, "mod", 0))
            elif event.type == pygame.KEYUP:
                self.tracker.release(event.key)

    def _key_down(self, key: int, modifiers: int = 0) -> None:
        alt_enter = key in (pygame.K_RETURN, pygame.K_KP_ENTER) and modifiers & pygame.KMOD_ALT
        if game_input.is_fullscreen(key) or alt_enter:
            self.toggle_fullscreen()
            return

        if self.state == MENU:
            if game_input.is_menu(key):
                self.running = False
            elif game_input.is_solo(key):
                self.start_round(1, reset_wins=True)
            elif game_input.is_versus(key):
                self.start_round(2, reset_wins=True)
            return

        if self.state == RESULT:
            if game_input.is_menu(key) or game_input.is_confirm(key):
                self.state = MENU
            elif game_input.is_restart(key):
                self.start_round(self.player_count, reset_wins=False)
            return

        if game_input.is_menu(key):
            self.state = MENU
            self.tracker.clear()
            return
        if game_input.is_pause(key):
            self.paused = not self.paused
            return
        if game_input.is_restart(key):
            self.start_round(self.player_count, reset_wins=False)
            return
        if not self.paused:
            self.tracker.press(key)

    def update(self, dt: float) -> None:
        if self.state != PLAY or self.game is None:
            return
        self.flashes.update(dt)
        if self.paused:
            return
        game = self.game
        for index in range(len(game.players)):
            game.set_direction(index, self.tracker.direction(index))
        for _ in range(self.ticks.advance(dt)):
            game.tick()
            self._flash_captures()
        if game.state == "finished":
            # update() only runs while the state is PLAY, so this is the single
            # PLAY -> RESULT transition: the win is credited exactly once.
            self._record_win(game)
            self.state = RESULT

    def _record_win(self, game: Game) -> None:
        """Credit one win per finished versus round, and none on a draw.

        A round won on points and one won by outlasting the rival both count the
        same; only a defined winner scores, so a draw leaves the tally alone.
        Solo play has no rival to beat, so it never touches the tally.
        """
        if self.player_count < 2 or game.result is None:
            return
        winner = game.result.winner
        if winner is not None:
            self.win_counts[winner] += 1

    def _flash_captures(self) -> None:
        """One flash entry per player per tick, not per captured cell.

        A single landing can claim thousands of cells; grouping them keeps the
        display list short, which matters now that the burst is drawn as spans.
        """
        game = self.game
        if game is None:
            return
        by_owner: dict[int, list[tuple[int, int]]] = {}
        for owner, x, y in game.captures:
            by_owner.setdefault(owner, []).append((x, y))
        for owner, cells in by_owner.items():
            self.flashes.add(cells, owner)

    def draw(self) -> None:
        if self.state == MENU:
            self.renderer.draw_menu()
        elif self.state == RESULT and self.game is not None:
            self.renderer.draw_result(self.game, self.win_counts)
        elif self.game is not None:
            self.renderer.draw_game(self.game, self.flashes)
            if self.paused:
                self.renderer.draw_pause()

    def stop(self) -> None:
        self.running = False


def main() -> None:
    App().run()


if __name__ == "__main__":
    main()
