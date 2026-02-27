from dataclasses import dataclass
from math import sqrt
from typing import Any
from sage.all import Link  # type:ignore


def string2matrix(string: str) -> list[int]:
    """convert each char in the string to an int, 
    using hex conversion to properly convert 'a' to 11 """
    return [int(elem, base=16) for elem in string]


def count_crossings(mosaic: list[int]) -> int:
    return len([tile for tile in mosaic if tile in [9, 10]])


def count_tiles(mosaic: str):
    return len([tile for tile in mosaic if tile != '0'])


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
    def as_pos(self) -> Pos:
        return Pos(self.x, self.y)


@dataclass
class NormMosaic:
    tiles: list[int]
    width: int
    height: int
    # mapping of connections at the edges
    boundlinks: dict[tuple, MosaicConn]

    connect_moves = [
        lambda p: MosaicConn(p.x+1, p.y, 2),
        lambda p: MosaicConn(p.x, p.y-1, 3),
        lambda p: MosaicConn(p.x-1, p.y, 0),
        lambda p: MosaicConn(p.x, p.y+1, 1),
    ]

    def get_tile(self, pos: Pos) -> int | None:
        if self.in_bounds(pos):
            return self.tiles[pos.y*self.width + pos.x]
        else:
            return None

    def in_bounds(self, pos: Pos) -> bool:
        return (0 <= pos.x < self.width) and \
               (0 <= pos.y < self.height)

    def get_connecting_pos(self, pos: MosaicConn):
        # handle conn loops
        if (res := self.boundlinks.get(pos.as_tup)) is not None:
            return res

        pos = self.connect_moves[pos.side](pos)
        # if it's not in boundlinks, it shouldn't be going onto an edge...
        assert (self.in_bounds(pos))
        return pos

    @classmethod
    def build_flat(cls, string: str) -> 'NormMosaic':
        tiles = string2matrix(string)
        size = int(sqrt(len(tiles)))
        return NormMosaic(tiles, size, size, {})

    @classmethod
    def build_cylindrical(cls, string: str) -> 'NormMosaic':
        mosaic = cls.build_flat(string)

        for i in range(mosaic.height):
            if mosaic.get_tile(Pos(0, i)) in (0, 2, 3, 6):
                continue
            b1 = MosaicConn(0, i, 2)
            b2 = MosaicConn(mosaic.width-1, i, 0)
            mosaic.boundlinks[b1.as_tup] = b2
            mosaic.boundlinks[b2.as_tup] = b1
        return mosaic


def traverse_mosaic(mosaic: NormMosaic):
    pos = MosaicConn(0, 0, 0)
    # getting the first non-zero tile
    while (tile := mosaic.get_tile(pos)) == 0:
        if pos.x < mosaic.width:
            # pos = MosaicConn(pos.x + 1,pos.y,pos.side)
            pos.x += 1
        else:
            pos.x = 0
            pos.y += 1
    assert (tile is not None)
    # getting first side as a starting point
    pos.side = list(connections_dict[tile])[0]
    start_pos = pos.as_tup
    while True:
        tile = mosaic.get_tile(pos)
        assert tile is not None  # Tile should be valid...

        out_side = connections_dict[tile][pos.side]
        # do some shit to build PD codes
        pos.side = out_side
        pos = mosaic.get_connecting_pos(pos)
        if pos.as_tup == start_pos:
            break


def parse_mosaic(mosaic_string) -> Link | str | None:
    """Parses mosaic, returning a valid knot, the string if it crashes, or none if it's an invalid knot"""
    size = int(len(mosaic_string)**(0.5))
    # ASK: why initialize to 10? isn't this a crossing?
    mosaic = [[10]*(size**2)]
    mosaic.append([0]*(size**2))
    satisfied: list[list[bool]] = [[False]*(size ** 2)]
    # THIS CHANGED - used to be mirred between both layers
    satisfied.append([False]*(size**2))
    crossing_strands = [
        [[0]*4 for _ in range((size ** 2))] for _ in range(2)]

    made_connections = [[[] for _ in range(size ** 2)] for _ in range(2)]
    crossing_indices = []
    pd_codes: list[list[int]] = []
    # Layer 0 "front", 1 holds hidden crossings
    tile_index = layer = tile_connection = 0
    strand_number = 1

    for i, char in enumerate(mosaic_string.strip()):
        num = int(char, base=16)
        mosaic[0][i] = num
        # all zero tiles are already satisfied
        satisfied[0][i] = (num == 0)

    # move index to start on the first non-zero tile
    while mosaic[0][tile_index] == 0:
        tile_index += 1

    for i in range(size):
        # iterating through left side
        if mosaic[0][i*size] not in (0, 2, 3, 6):
            for j in range(size):
                # adding 5 to the whole row? Other one adds 6 if it is on top edge?
                mosaic[1][i*size + j] += 5
        # iterating through top row edge?
        if mosaic[0][i] not in (0, 1, 2, 5):
            for j in range(size):
                mosaic[1][(j+1)*size - (i+1)] += 6

    # curr_tile always starts at a non-zero tile, so this never errs
    curr_tile = mosaic[layer][tile_index]
    tile_connection = valid_connections[curr_tile][0][0]  # type: ignore
    not_looped = True  # tracks if we've completed a whole loop
    loop_ct = 0
    while not_looped:
        loop_ct += 1
        if loop_ct > 10_000:
            # TODO: this is a nasty hack and shouldn't stay
            return mosaic_string

        curr_tile = mosaic[layer][tile_index]
        for conn in valid_connections[curr_tile]:
            if conn[0] == tile_connection:
                if conn in made_connections[layer][tile_index]:
                    # think this is checking if we're back where we started?
                    not_looped = False
                    break  # break for & while

                made_connections[layer][tile_index].append(conn)
                # if non crossing and has 1 or crossing and has 2
                num_connections = len(made_connections[layer][tile_index])
                if ((num_connections == 1) and curr_tile < 7) or (num_connections == 2):
                    # If the tile has all the connections it needs, that tile is 'satisfied'
                    satisfied[layer][tile_index] = True

                # Crossing logic
                if curr_tile > 8:  # if it is a crossing
                    if satisfied[layer][tile_index]:
                        crossing_indices.append([layer, tile_index])
                    crossing_strands[layer][tile_index][tile_connection] = strand_number
                    strand_number += 1
                    crossing_strands[layer][tile_index][(
                        tile_connection + 2) % 4] = strand_number
                else:
                    tile_connection = (conn[1] + 2) % 4

                # Go to next tile
                if tile_connection == 0:  # left
                    if tile_index % size == 0:
                        layer = (layer + 1) % 2
                        tile_index = size*((tile_index//size) + 1) - 1
                    else:
                        tile_index -= 1
                elif tile_connection == 1:  # down
                    if (tile_index // size) == size - 1:
                        layer = (layer + 1) % 2
                        tile_index = size**2 - (tile_index % size + 1)
                        tile_connection = 3
                    else:
                        tile_index += size
                elif tile_connection == 2:  # right
                    if tile_index % size == size - 1:
                        layer = (layer + 1) % 2
                        tile_index = size*(tile_index // size)
                    else:
                        tile_index += 1
                elif tile_connection == 3:  # up
                    if tile_index // size == 0:
                        layer = (layer + 1) % 2
                        tile_index = size - (tile_index + 1)
                        tile_connection = 1
                    else:
                        tile_index -= size
                break
    # This is pretty much a completely different phase of the func
    # assume it's the part that actually figures out what knot it is?
    if all(satisfied[0]):
        if len(crossing_indices) < 3:
            # Must be the unknot if there's less than 3 crossings
            homf = 1
        else:
            for i0, i1 in crossing_indices:
                strands = crossing_strands[i0][i1]
                if mosaic[i0][i1] == 9:
                    if (0, 2) in made_connections[i0][i1]:
                        pd_codes.append(strands)
                    else:
                        # Rotated by 2
                        pd_codes.append(strands[2:] + strands[:2])
                else:
                    if (1, 3) in made_connections[i0][i1]:
                        pd_codes.append(strands[1:] + strands[:1])
                    else:
                        pd_codes.append(strands[3:] + strands[:3])
            for l in range(len(pd_codes[-1])):
                if pd_codes[-1][l] == strand_number:
                    pd_codes[-1][l] = 1
                    break
            return Link(pd_codes)


# sides numbered counterclockwise from the right
valid_connections = (
    (()),
    ((2, 3), (3, 2)),
    ((0, 3), (3, 0)),
    ((0, 1), (1, 0)),
    ((2, 1), (1, 2)),
    ((2, 0), (0, 2)),
    ((1, 3), (3, 1)),
    ((2, 3), (3, 2), (1, 0), (0, 1)),
    ((0, 3), (3, 0), (2, 1), (1, 2)),
    ((0, 2), (1, 3), (2, 0), (3, 1)),
    ((0, 2), (1, 3), (2, 0), (3, 1)),
    ((0, 2), (1, 3), (2, 0), (3, 1))
)
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
    {0: 2, 1: 3, 2: 0, 3: 1}
]
