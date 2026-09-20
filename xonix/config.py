"""Game constants shared by the simulation core and the pygame shell."""

FIELD_WIDTH = 120
FIELD_HEIGHT = 80

# Reference cell size. It is the scale of the windowed default; on a larger
# surface the renderer picks the biggest whole-pixel scale that still fits.
CELL_SIZE = 6
FIELD_PIXEL_WIDTH = FIELD_WIDTH * CELL_SIZE
FIELD_PIXEL_HEIGHT = FIELD_HEIGHT * CELL_SIZE

# The HUD gets its own strip above the field, so it never covers playable cells.
HUD_MIN_HEIGHT = 22
HUD_SCALE_FACTOR = 3
WINDOW_WIDTH = FIELD_PIXEL_WIDTH
WINDOW_HEIGHT = FIELD_PIXEL_HEIGHT + HUD_MIN_HEIGHT

PERIMETER_CELLS = 2 * FIELD_WIDTH + 2 * (FIELD_HEIGHT - 2)
TOTAL_CELLS = FIELD_WIDTH * FIELD_HEIGHT
PLAYABLE_CELLS = TOTAL_CELLS - PERIMETER_CELLS

TICKS_PER_SECOND = 60

START_LIVES = 3
BALLS_AT_START = 3

PLAYER_TICKS_PER_CELL = 3

STAGE_SPEEDS = (7, 6, 5, 4)
STAGE_THRESHOLDS = (0.20, 0.40, 0.60)

# All four diagonals are equally likely at spawn. A fixed direction would send
# every ball the same way and hand the corresponding side a standing advantage.
BALL_DIRECTIONS = ((1, 1), (1, -1), (-1, 1), (-1, -1))

ROUND_TARGET_RATIO = 0.75
ROUND_TARGET_CELLS = round(PLAYABLE_CELLS * ROUND_TARGET_RATIO)

SPAWN_MIN_DISTANCE = 8

CAPTURE_FLASH_SECONDS = 0.5

WARM = (232, 114, 44)
COOL = (47, 182, 196)
