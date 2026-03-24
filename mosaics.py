from dataclasses import dataclass
from enum import Enum
from math import sqrt
from operator import xor
from typing import ClassVar, Callable
from sage.all import Link  # type:ignore
from mosaic_util import *


@dataclass
class Pos:
    x: int
    y: int


@dataclass
class MosaicConn(Pos):
    side: int  # sides are numbered counter clockwise starting from the right

    @property
    def as_tup(self) -> tuple[int, int, int]:
        return self.x, self.y, self.side

    @property
    def as_pos_tup(self) -> tuple[int, int]:
        return self.x, self.y


class NotAKnot(Enum):
    BAD_CONNECTIONS = -1
    UNKNOT = 0
    LINK = 1
    NO_TILES = 2  # Mosaic is completly empty
    GOODKNOT = 3


@dataclass
class NormMosaic:
    tiles: list[int]
    width: int
    height: int
    nominal_size: int
    # mapping of connections at the edges
    boundlinks: dict[tuple[int, int, int], MosaicConn]

    connect_moves: ClassVar[list[Callable[[MosaicConn], MosaicConn]]] = [
        lambda p: MosaicConn(p.x + 1, p.y, 2),
        lambda p: MosaicConn(p.x, p.y - 1, 3),
        lambda p: MosaicConn(p.x - 1, p.y, 0),
        lambda p: MosaicConn(p.x, p.y + 1, 1),
    ]  # type: ignore

    def get_tile(self, pos: Pos) -> int | None:
        if self.in_bounds(pos):
            return self.tiles[pos.y * self.width + pos.x]
        else:
            return None

    def in_bounds(self, pos: Pos) -> bool:
        return (0 <= pos.x < self.width) and (0 <= pos.y < self.height)

    def get_connecting_pos(self, pos: MosaicConn) -> MosaicConn | NotAKnot:
        # handle conn loops
        if (res := self.boundlinks.get(pos.as_tup)) is not None:
            return res

        pos = self.connect_moves[pos.side](pos)
        # if it's not in boundlinks, it shouldn't be going onto an edge...
        if not self.in_bounds(pos):
            return NotAKnot.BAD_CONNECTIONS
        return pos

    @classmethod
    def build_flat(cls, string: str) -> "NormMosaic":
        tiles = string2matrix(string)
        size = int(sqrt(len(tiles)))
        return NormMosaic(tiles, size, size, size, {})

    @classmethod
    def build_cylindrical(cls, string: str) -> "NormMosaic":
        mosaic = cls.build_flat(string)
        # adding the left <-> right links
        for i in range(mosaic.height):
            if mosaic.get_tile(Pos(0, i)) in (0, 2, 3, 6):
                continue  # no connections out the sides
            edge1 = MosaicConn(0, i, 2)
            edge2 = MosaicConn(mosaic.width - 1, i, 0)
            mosaic.boundlinks[edge1.as_tup] = edge2
            mosaic.boundlinks[edge2.as_tup] = edge1
        return mosaic

    @classmethod
    def build_toric(cls, string: str) -> "NormMosaic":
        raise NotImplementedError("Need added matrix")
        mosaic = cls.build_cylindrical(string)
        # adding the top <-> bottom links
        for i in range(mosaic.width):
            if mosaic.get_tile(Pos(i, 0)) in (0, 1, 2, 5):
                continue  # no connections out the top
            b1 = MosaicConn(i, 0, 1)
            b2 = MosaicConn(i, mosaic.height - 1, 3)
            mosaic.boundlinks[b1.as_tup] = b2
            mosaic.boundlinks[b2.as_tup] = b1
        return mosaic


def traverse_mosaic(  # type: ignore
    mosaic: NormMosaic,
    prune_links: bool = True,
    prune_unknots: bool = True,
    classify_only: bool = False,
) -> Link | NotAKnot:
    pos: MosaicConn = MosaicConn(0, 0, 0)
    # getting the first non-zero tile
    while (tile := mosaic.get_tile(pos)) == 0:
        pos.x += 1
        if pos.x == mosaic.width:
            pos.x = 0
            pos.y += 1
    if tile is None:
        return NotAKnot.NO_TILES

    under_crosses: list[tuple[MosaicConn, int]] = []
    over_crosses: dict[tuple[int, int], tuple[MosaicConn, int]] = {}

    # this should equal # of moves through the mosaic,
    # if it's a knot (meaning traversing will visit all tiles)
    # for a valid knot, this count should not be exceeded
    exp_moves = count_tiles(mosaic.tiles) + len([t for t in mosaic.tiles if t >= 7])

    # getting first side as a starting point
    pos.side = list(connections_dict[tile])[0]
    start_pos = pos.as_tup
    move_ct = 0
    edge_ct = 0
    while True:
        move_ct += 1
        if move_ct > exp_moves:
            return NotAKnot.BAD_CONNECTIONS
        tile = mosaic.get_tile(pos)
        assert tile is not None  # Tile should be valid...

        if tile in (9, 10):  # if it's a crossing
            edge_ct += 1
            # check if under or over
            if xor(tile == 10, pos.side % 2 == 0):
                under_crosses.append((pos, edge_ct))
            else:
                over_crosses[pos.as_pos_tup] = (pos, edge_ct)
        out_side = connections_dict[tile].get(pos.side)
        if out_side is None:
            return NotAKnot.BAD_CONNECTIONS
        pos.side = out_side
        res = mosaic.get_connecting_pos(pos)
        if type(res) is not MosaicConn:
            return res
        pos = res
        if pos.as_tup == start_pos:
            break

    # if we get less moves than expected, must be a link
    if exp_moves != move_ct and prune_links:
        return NotAKnot.LINK
    # if there are < 3 crossings, must be an unknot
    if len(under_crosses) < 3 and prune_unknots:
        return NotAKnot.UNKNOT
    # calculating the PD codes from the crossing data
    max_edge = 2 * len(under_crosses)
    pd_codes: list[list[int]] = []
    for u_cross, u_edge in under_crosses:
        # get overcrossing corresponding to this intersection
        o_cross, o_edge = over_crosses[u_cross.as_pos_tup]
        # check which way
        if o_cross.side == (u_cross.side + 1) % 4:
            pd_code = (u_edge, o_edge, u_edge + 1, o_edge + 1)
        else:
            pd_code = (u_edge, o_edge + 1, u_edge + 1, o_edge)
        # wrap edges back to zero
        pd_code = [(1 if i > max_edge else i) for i in pd_code]
        pd_codes.append(pd_code)

    return NotAKnot.GOODKNOT if classify_only else Link(pd_codes)


connections_dict: list[dict[int, int]] = [
    {},
    {2: 3, 3: 2},
    {0: 3, 3: 0},
    {0: 1, 1: 0},
    {2: 1, 1: 2},
    {2: 0, 0: 2},
    {1: 3, 3: 1},
    {2: 3, 3: 2, 1: 0, 0: 1},
    {0: 3, 3: 0, 2: 1, 1: 2},
    {0: 2, 1: 3, 2: 0, 3: 1},
    {0: 2, 1: 3, 2: 0, 3: 1},
    {0: 2, 1: 3, 2: 0, 3: 1},
]
