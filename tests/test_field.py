from tests.helpers import carve_land, make_field
from xonix import config
from xonix.core.field import NO_OWNER, Field, State


def test_start_layout_is_land_rim_and_sea_inside():
    field = Field()
    land = sum(1 for cell in field.cells if cell == State.LAND)
    assert land == config.PERIMETER_CELLS == 396
    assert all(cell == State.SEA for cell in field.cells if cell == State.SEA)
    assert field.land_count == 0
    assert field.is_land(0, 0) and field.is_land(60, 79) and field.is_land(119, 40)
    assert field.is_sea(60, 40)


def test_trail_carries_owner_and_land_does_not():
    field = make_field()
    field.set_trail(3, 3, owner=1)
    assert field.is_trail(3, 3)
    assert field.owner_at(3, 3) == 1

    captured = field.fill([(3, 3)], ball_cells=[(10, 6)])
    assert captured[0] == field.index(3, 3)
    assert field.is_land(3, 3)
    assert field.owner_at(3, 3) == NO_OWNER


def test_cells_are_exactly_one_state():
    field = make_field()
    field.set_trail(4, 4, owner=0)
    states = {
        field.state(0, 0),
        field.state(1, 1),
        field.state(4, 4),
    }
    assert states == {State.LAND, State.SEA, State.TRAIL}


def test_walled_off_water_is_unreachable_by_a_ball():
    field = make_field()
    carve_land(field, [(x, 2) for x in range(2, 8)] + [(x, 6) for x in range(2, 8)])
    carve_land(field, [(2, y) for y in range(2, 7)] + [(7, y) for y in range(2, 7)])

    reachable = field.reachable_sea([(15, 6)])

    enclosed = [(x, y) for x in range(3, 7) for y in range(3, 6)]
    assert all(not reachable[field.index(x, y)] for x, y in enclosed)
    assert reachable[field.index(15, 6)] == 1


def test_landing_fills_water_no_ball_can_reach():
    field = make_field()
    carve_land(field, [(x, 3) for x in range(1, 9)] + [(x, 9) for x in range(1, 9)])
    carve_land(field, [(8, y) for y in range(4, 9)])
    field.set_trail(1, 3, owner=0)
    field.set_trail(1, 9, owner=0)

    captured = field.fill([(1, 3), (1, 9)], ball_cells=[(15, 6)])

    enclosed = [(x, y) for x in range(2, 8) for y in range(4, 9)]
    assert {field.index(x, y) for x, y in enclosed} <= set(captured)
    assert all(field.state(x, y) == State.LAND for x, y in enclosed)
    assert field.state(15, 6) == State.SEA


def test_walled_in_ball_keeps_its_pocket_as_sea():
    field = make_field()
    box = [(x, 4) for x in range(2, 9)] + [(x, 9) for x in range(2, 9)]
    box += [(2, y) for y in range(5, 9)] + [(8, y) for y in range(5, 9)]
    carve_land(field, box)
    field.set_trail(1, 6, owner=0)

    captured = field.fill([(1, 6)], ball_cells=[(5, 6)])

    pocket = [(x, y) for x in range(3, 8) for y in range(5, 9)]
    assert all(field.state(x, y) == State.SEA for x, y in pocket)
    assert field.state(15, 6) == State.LAND
    assert field.index(1, 6) in captured


def test_captured_cells_include_the_trail_itself():
    field = make_field()
    field.set_trail(4, 3, owner=0)
    field.set_trail(4, 4, owner=0)

    captured = field.fill([(4, 3), (4, 4)], ball_cells=[(15, 6)])

    assert field.index(4, 3) in captured
    assert field.index(4, 4) in captured
    assert field.is_land(4, 3) and field.is_land(4, 4)
    assert field.land_count == len(captured)


def test_captured_cells_and_land_count_stay_in_sync():
    field = make_field()
    field.set_trail(5, 5, owner=0)
    captured = field.fill([(5, 5)], ball_cells=[(10, 6)])
    assert field.index(5, 5) in captured
    assert field.land_count == len(captured)
    assert field.is_land(5, 5)


def test_land_count_ignores_perimeter_growth():
    field = make_field()
    assert field.land_count == 0
    field.fill([], ball_cells=[])
    assert field.land_count == 0


def test_sea_components_returns_largest_first():
    field = make_field()
    for y in range(1, 11):
        field.cells[field.index(10, y)] = State.LAND
    components = field.sea_components()
    assert len(components) == 2
    assert len(components[0]) >= len(components[1])
    assert all(x < 10 for x, _ in components[1]) or all(x > 10 for x, _ in components[1])


def test_open_trail_is_not_a_wall():
    field = make_field()
    for y in range(1, 11):
        field.set_trail(10, y, owner=1)
    field.fill([], ball_cells=[(5, 5)])
    reachable = field.reachable_sea([(5, 5)])
    assert reachable[field.index(15, 5)] == 1
