"""Compare the field walk against a plain reference BFS on random fields.

The simulation leans on reachability for every capture, so the fast walk must
agree with the obvious implementation on every shape, including mazes.
"""

import random
from collections import deque

from xonix.core.field import Field, State


def reference_reachable(field: Field, sources):
    seen = bytearray(len(field.cells))
    queue: deque[int] = deque()
    width, height, cells = field.width, field.height, field.cells
    for x, y in sources:
        if 0 <= x < width and 0 <= y < height:
            index = y * width + x
            if not seen[index] and cells[index] != State.LAND:
                seen[index] = 1
                queue.append(index)
    while queue:
        index = queue.popleft()
        x = index % width
        y = index // width
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < width and 0 <= ny < height:
                neighbour = ny * width + nx
                if not seen[neighbour] and cells[neighbour] != State.LAND:
                    seen[neighbour] = 1
                    queue.append(neighbour)
    return seen


def random_field(rng: random.Random) -> Field:
    width, height = rng.choice([(12, 10), (20, 14), (33, 21), (60, 40)])
    field = Field(width=width, height=height)
    for _ in range(rng.randint(0, width * height // 8)):
        x = rng.randrange(1, width - 1)
        y = rng.randrange(1, height - 1)
        state = rng.choice([State.LAND, State.TRAIL, State.SEA, State.SEA])
        if state == State.TRAIL:
            field.set_trail(x, y, rng.randrange(2))
        else:
            field.cells[field.index(x, y)] = state
    return field


def test_walk_matches_reference_on_random_fields():
    rng = random.Random(20260920)
    for _ in range(300):
        field = random_field(rng)
        sources = [
            (rng.randrange(field.width), rng.randrange(field.height))
            for _ in range(rng.randint(0, 4))
        ]
        assert field.reachable_sea(sources) == reference_reachable(field, sources)


def test_walk_from_an_empty_start_reaches_the_whole_field():
    field = Field()

    seen = field.reachable_sea([(field.width // 2, field.height // 2)])

    assert sum(seen) == (field.width - 2) * (field.height - 2)


def test_open_trail_lets_the_walk_pass_through():
    field = Field(width=20, height=12)
    for y in range(1, 11):
        field.set_trail(10, y, owner=1)

    seen = field.reachable_sea([(3, 5)])

    assert seen[field.index(15, 5)] == 1


def test_land_wall_stops_the_walk():
    field = Field(width=20, height=12)
    for y in range(1, 11):
        field.cells[field.index(10, y)] = State.LAND

    seen = field.reachable_sea([(3, 5)])

    assert seen[field.index(15, 5)] == 0
    assert seen[field.index(3, 5)] == 1


def test_walk_result_is_reset_between_calls():
    field = Field(width=20, height=12)
    for y in range(1, 11):
        field.cells[field.index(10, y)] = State.LAND
    first = field.reachable_sea([(3, 5)])
    assert first[field.index(15, 5)] == 0

    second = field.reachable_sea([(15, 5)])

    assert second is first
    assert second[field.index(3, 5)] == 0
    assert second[field.index(15, 5)] == 1


def reference_components(field: Field):
    seen = bytearray(len(field.cells))
    width, height, cells = field.width, field.height, field.cells
    components = []
    for start in range(len(cells)):
        if cells[start] != State.SEA or seen[start]:
            continue
        seen[start] = 1
        queue: deque[int] = deque([start])
        component = []
        while queue:
            index = queue.popleft()
            x = index % width
            y = index // width
            if cells[index] == State.SEA:
                component.append((x, y))
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if 0 <= nx < width and 0 <= ny < height:
                    neighbour = ny * width + nx
                    if not seen[neighbour] and cells[neighbour] != State.LAND:
                        seen[neighbour] = 1
                        queue.append(neighbour)
        components.append(component)
    components.sort(key=len, reverse=True)
    return components


def canonical(components):
    """Compare components regardless of walk order or order within a component.

    Only two things are contractual: every component is complete, and the list
    is largest first. Which cell a depth-first walk happens to visit first is
    not, so the comparison must not pin it down.
    """
    return sorted((len(component), tuple(sorted(component))) for component in components)


def test_component_walk_matches_reference_on_random_fields():
    rng = random.Random(20260921)
    for _ in range(200):
        field = random_field(rng)
        assert canonical(field.sea_components()) == canonical(reference_components(field))
