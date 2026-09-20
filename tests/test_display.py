"""Display sizing: fullscreen default, whole-pixel scale and F11 switching."""

import pygame
import pytest

from xonix import app as app_module, config
from xonix.render import compute_layout

REFERENCE = (config.WINDOW_WIDTH, config.WINDOW_HEIGHT)


@pytest.fixture
def embedded():
    """An app drawing into a surface supplied by the caller, as tests do."""
    instance = app_module.App(screen=pygame.Surface(REFERENCE))
    yield instance
    instance.stop()
    pygame.quit()


@pytest.fixture
def standalone():
    """An app that owns the display, running on SDL's dummy video driver."""
    instance = app_module.App()
    yield instance
    instance.stop()
    pygame.quit()


def test_the_window_leaves_room_for_the_hud_above_the_field():
    layout = compute_layout(REFERENCE)

    assert layout.origin_y == layout.hud_height
    assert layout.origin_y >= config.HUD_MIN_HEIGHT
    assert layout.origin_y + config.FIELD_HEIGHT * layout.scale == REFERENCE[1]


def test_the_scale_is_always_a_whole_number_of_pixels_per_cell():
    for window in [(640, 420), (720, 502), (1024, 700), (1366, 768), (1920, 1080), (3840, 2160)]:
        layout = compute_layout(window)
        assert isinstance(layout.scale, int)
        assert layout.scale >= 1


def test_a_tiny_window_still_draws_a_usable_field():
    layout = compute_layout((200, 160))

    assert layout.scale == 1
    assert layout.origin_x >= 0
    assert layout.origin_y + config.FIELD_HEIGHT <= 160


def test_the_field_is_centred_horizontally_when_the_window_is_wider():
    layout = compute_layout((1600, 900))

    left = layout.origin_x
    right = layout.width - (layout.origin_x + config.FIELD_WIDTH * layout.scale)
    assert abs(left - right) <= 1


def test_a_larger_screen_produces_larger_cells():
    scales = [
        compute_layout(window).scale
        for window in [(720, 502), (1280, 800), (1920, 1080), (2560, 1440)]
    ]

    assert scales == sorted(scales)
    assert scales[-1] > scales[0]


def test_the_game_starts_fullscreen(standalone):
    assert standalone.fullscreen


def test_f11_requests_the_windowed_size_and_returns_to_fullscreen(standalone):
    """SDL's dummy driver ignores some mode changes, so the request is recorded."""
    requests = []

    def fake_set_mode(size, flags=0):
        requests.append((size, flags))
        return pygame.Surface(REFERENCE)

    original = pygame.display.set_mode
    pygame.display.set_mode = fake_set_mode
    try:
        standalone._key_down(pygame.K_F11)
        assert requests == [(REFERENCE, pygame.RESIZABLE)]
        assert not standalone.fullscreen
        assert standalone.renderer.scale == config.CELL_SIZE
        assert standalone.renderer.screen.get_size() == REFERENCE

        standalone._key_down(pygame.K_F11)
        assert requests[-1] == ((0, 0), pygame.FULLSCREEN)
        assert standalone.fullscreen
    finally:
        pygame.display.set_mode = original


def test_alt_enter_also_toggles_fullscreen(standalone):
    standalone._key_down(pygame.K_RETURN, pygame.KMOD_ALT)

    assert not standalone.fullscreen


def test_a_plain_enter_does_not_toggle_fullscreen(standalone):
    standalone._key_down(pygame.K_RETURN)

    assert standalone.fullscreen


def test_a_round_can_be_played_right_after_switching_modes(standalone):
    standalone._key_down(pygame.K_F11)

    standalone.start_round(2)
    for _ in range(60):
        standalone.update(1 / config.TICKS_PER_SECOND)
        standalone.draw()

    assert standalone.game is not None
    assert standalone.renderer.scale >= 1


def test_an_injected_surface_is_never_resized(embedded):
    """Tests and embedding pass their own surface, so the app must leave it alone."""
    before = embedded.screen

    embedded._key_down(pygame.K_F11)

    assert embedded.screen is before
    assert embedded.renderer.screen is before


def test_resize_events_are_applied_in_windowed_mode(standalone):
    standalone._key_down(pygame.K_F11)
    delivered = []

    def fake_set_mode(size, flags=0):
        delivered.append((size, flags))
        return pygame.Surface(size)

    original = pygame.display.set_mode
    pygame.display.set_mode = fake_set_mode
    try:
        pygame.event.post(
            pygame.event.Event(pygame.VIDEORESIZE, w=1000, h=700, size=(1000, 700))
        )
        standalone.handle_events()
    finally:
        pygame.display.set_mode = original

    assert delivered == [((1000, 700), pygame.RESIZABLE)]
    assert standalone.windowed_size == (1000, 700)
    assert standalone.renderer.screen.get_size() == (1000, 700)
    assert standalone.renderer.scale >= config.CELL_SIZE
