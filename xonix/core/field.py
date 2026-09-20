"""The playing field: cell states, trail bookkeeping and territory fill."""

from __future__ import annotations

from enum import IntEnum

from xonix import config

NO_OWNER = 0xFF


class State(IntEnum):
    SEA = 0
    LAND = 1
    TRAIL = 2


class Field:
    """A grid of cells, each either sea, land or a player's trail.

    Land does not remember who captured it; only trail cells carry an owner,
    because the owner is needed for clearing a trail, for the respawn anchor
    and for the trail colour.
    """

    def __init__(self, width: int = config.FIELD_WIDTH, height: int = config.FIELD_HEIGHT) -> None:
        self.width = width
        self.height = height
        self.cells = bytearray(width * height)
        self.trail_owner = bytearray(b"\xff" * (width * height))
        self._reachable_buffer = bytearray(width * height)
        self._zero_block = bytes(width * height)
        self.land_count = 0
        self.reset()

    def reset(self) -> None:
        self.cells = bytearray(self.width * self.height)
        self.trail_owner = bytearray(b"\xff" * (self.width * self.height))
        for x in range(self.width):
            self.cells[self.index(x, 0)] = State.LAND
            self.cells[self.index(x, self.height - 1)] = State.LAND
        for y in range(1, self.height - 1):
            self.cells[self.index(0, y)] = State.LAND
            self.cells[self.index(self.width - 1, y)] = State.LAND
        self.land_count = 0

    def index(self, x: int, y: int) -> int:
        return y * self.width + x

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def state(self, x: int, y: int) -> int:
        return self.cells[self.index(x, y)]

    def is_land(self, x: int, y: int) -> bool:
        return self.cells[self.index(x, y)] == State.LAND

    def is_sea(self, x: int, y: int) -> bool:
        return self.cells[self.index(x, y)] == State.SEA

    def is_trail(self, x: int, y: int) -> bool:
        return self.cells[self.index(x, y)] == State.TRAIL

    def owner_at(self, x: int, y: int) -> int:
        return self.trail_owner[self.index(x, y)]

    def set_trail(self, x: int, y: int, owner: int) -> None:
        index = self.index(x, y)
        self.cells[index] = State.TRAIL
        self.trail_owner[index] = owner

    def _to_land(self, index: int) -> None:
        if self.cells[index] != State.LAND:
            self.cells[index] = State.LAND
            self.trail_owner[index] = NO_OWNER
            if index % self.width not in (0, self.width - 1):
                row = index // self.width
                if row not in (0, self.height - 1):
                    self.land_count += 1

    def clear_trail(self, trail: list[tuple[int, int]]) -> None:
        for x, y in trail:
            index = self.index(x, y)
            if self.cells[index] == State.TRAIL:
                self.cells[index] = State.SEA
                self.trail_owner[index] = NO_OWNER

    def reachable_sea(self, sources: list[tuple[int, int]]) -> bytearray:
        """Every sea cell a ball can swim to.

        Only land is a wall. Open trail cells are passable, so a trail that has
        not reached land cuts nothing off and earns its owner no territory.

        The walk works on flat cell indices with an explicit stack, and the
        result buffer is reused between calls: a full-field pass costs about
        3 ms, which only ever happens when a player lands, not every tick.
        """
        seen = self._reachable_buffer
        seen[:] = self._zero_block
        cells = self.cells
        width = self.width
        last_row_start = (self.height - 1) * width
        stack: list[int] = []
        for x, y in sources:
            if 0 <= x < self.width and 0 <= y < self.height:
                index = y * width + x
                if not seen[index] and cells[index] != State.LAND:
                    seen[index] = 1
                    stack.append(index)
        while stack:
            index = stack.pop()
            if index >= width:
                neighbour = index - width
                if not seen[neighbour] and cells[neighbour] != State.LAND:
                    seen[neighbour] = 1
                    stack.append(neighbour)
            if index < last_row_start:
                neighbour = index + width
                if not seen[neighbour] and cells[neighbour] != State.LAND:
                    seen[neighbour] = 1
                    stack.append(neighbour)
            neighbour = index - 1
            if not seen[neighbour] and cells[neighbour] != State.LAND:
                seen[neighbour] = 1
                stack.append(neighbour)
            neighbour = index + 1
            if not seen[neighbour] and cells[neighbour] != State.LAND:
                seen[neighbour] = 1
                stack.append(neighbour)
        return seen

    def sea_components(self) -> list[list[tuple[int, int]]]:
        """All connected areas of sea, largest first.

        Spawning a ball runs this, so like :meth:`reachable_sea` it walks flat
        cell indices with an explicit stack instead of unpacking coordinates:
        on the full field that is the difference between most of a frame and a
        comfortable fraction of one.
        """
        seen = bytearray(len(self.cells))
        components: list[list[tuple[int, int]]] = []
        width = self.width
        cells = self.cells
        for start in range(len(cells)):
            if cells[start] != State.SEA or seen[start]:
                continue
            seen[start] = 1
            stack = [start]
            component: list[tuple[int, int]] = []
            while stack:
                index = stack.pop()
                column = index % width
                if cells[index] == State.SEA:
                    component.append((column, index // width))
                if index >= width:
                    neighbour = index - width
                    if not seen[neighbour] and cells[neighbour] != State.LAND:
                        seen[neighbour] = 1
                        stack.append(neighbour)
                if index + width < len(cells):
                    neighbour = index + width
                    if not seen[neighbour] and cells[neighbour] != State.LAND:
                        seen[neighbour] = 1
                        stack.append(neighbour)
                if column:
                    neighbour = index - 1
                    if not seen[neighbour] and cells[neighbour] != State.LAND:
                        seen[neighbour] = 1
                        stack.append(neighbour)
                if column != width - 1:
                    neighbour = index + 1
                    if not seen[neighbour] and cells[neighbour] != State.LAND:
                        seen[neighbour] = 1
                        stack.append(neighbour)
            components.append(component)
        components.sort(key=len, reverse=True)
        return components

    def fill(self, trail: list[tuple[int, int]], ball_cells: list[tuple[int, int]]) -> list[int]:
        """Turn a landed trail into land, then land every sea cell no ball reaches.

        This single rule covers closing a loop around empty water, closing one
        around a ball, biting a piece off a pocket, and stepping back onto land.
        Cells are visited once: reachability, the flip and the point tally happen
        in a single pass over the field.
        """
        captured: list[int] = []
        for x, y in trail:
            index = self.index(x, y)
            if self.cells[index] == State.TRAIL:
                self._to_land(index)
                captured.append(index)
        if not captured:
            return captured
        reachable = self.reachable_sea(ball_cells)
        cells = self.cells
        width = self.width
        height = self.height
        playable_columns = range(1, width - 1)
        for y in range(1, height - 1):
            row_start = y * width
            for x in playable_columns:
                index = row_start + x
                if not reachable[index] and cells[index] == State.SEA:
                    cells[index] = State.LAND
                    self.trail_owner[index] = NO_OWNER
                    self.land_count += 1
                    captured.append(index)
        return captured

    @property
    def playable_cells(self) -> int:
        """The field minus its perimeter; the perimeter is nobody's territory."""
        return (self.width - 2) * (self.height - 2)

    def land_ratio(self) -> float:
        return self.land_count / self.playable_cells
