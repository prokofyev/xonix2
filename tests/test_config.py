from xonix import config


def test_field_geometry():
    assert config.FIELD_WIDTH * config.FIELD_HEIGHT == config.TOTAL_CELLS == 9600
    assert config.PERIMETER_CELLS == 396
    assert config.PLAYABLE_CELLS == 9204
    assert config.PLAYABLE_CELLS == config.TOTAL_CELLS - config.PERIMETER_CELLS


def test_the_reference_window_is_a_720x480_field_plus_the_hud_strip():
    assert config.FIELD_PIXEL_WIDTH == 720
    assert config.FIELD_PIXEL_HEIGHT == 480
    assert config.WINDOW_WIDTH == 720
    assert config.WINDOW_HEIGHT == 480 + config.HUD_MIN_HEIGHT


def test_round_target_is_three_quarters_of_playable_cells():
    assert config.ROUND_TARGET_CELLS == 6903
    assert config.ROUND_TARGET_CELLS == round(config.PLAYABLE_CELLS * 0.75)


def test_stage_ladder_is_monotonic():
    assert config.STAGE_THRESHOLDS == (0.20, 0.40, 0.60)
    assert config.STAGE_SPEEDS == (7, 6, 5, 4)
    assert config.STAGE_SPEEDS[0] > config.STAGE_SPEEDS[-1] > config.PLAYER_TICKS_PER_CELL
