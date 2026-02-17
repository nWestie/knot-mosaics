from sage.all import Link #type:ignore

def string2matrix(string: str) -> list[int]:
    """convert each char in the string to an int, 
    using hex conversion to properly convert 'a' to 11 """
    return [int(elem, base=16) for elem in string]


def count_crossings(mosaic: list[int]) -> int:
    return len([tile for tile in mosaic if tile in [9, 10]])


def count_tiles(mosaic: str):
    return len([tile for tile in mosaic if tile != '0'])


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
    tile_index = layer = face = 0
    strand_number = 1

    for i, char in enumerate(mosaic_string.strip()):
        num = int(char, base=16)
        mosaic[0][i] = num
        satisfied[0][i] = (num == 0)

    # move index to start on the first non-zero tile
    while mosaic[0][tile_index] == 0:
        tile_index += 1

    for i in range(size):
        # iterating through left side
        if mosaic[0][i*size] > 6 or mosaic[0][i*size] in (1, 4, 5):
            for j in range(size):
                # ASK: adding 5 to the whole row? Other one adds 6 if it is on top edge?
                mosaic[1][i*size + j] += 5
        # iterating through top row edge?
        if mosaic[0][i] > 6 or mosaic[0][i] in (3, 4, 6):
            for j in range(size):
                mosaic[1][(j+1)*size - (i+1)] += 6

    # curr_tile always starts at a non-zero tile, so this never errs
    curr_tile = mosaic[layer][tile_index]
    face = valid_connections[curr_tile][0][0]  # type: ignore
    not_looped = True
    loop_ct = 0
    while not_looped:
        loop_ct += 1
        if loop_ct > 10_000:
            # TODO: this is a nasty hack and shouldn't stay
            return mosaic_string

        curr_tile = mosaic[layer][tile_index]
        for conn in valid_connections[curr_tile]:
            if conn[0] == face:
                if conn in made_connections[layer][tile_index]:
                    not_looped = False
                    break  # break for & while

                made_connections[layer][tile_index].append(conn)
                if ((len(made_connections[layer][tile_index]) == 1) and curr_tile < 7) or (len(made_connections[layer][tile_index]) == 2):
                    # If the tile has all the connections it needs, we're done
                    satisfied[layer][tile_index] = True

                # Crossing logic
                if curr_tile > 8:  # if it is a crossing
                    if satisfied[layer][tile_index]:
                        crossing_indices.append([layer, tile_index])
                    crossing_strands[layer][tile_index][face] = strand_number
                    strand_number += 1
                    crossing_strands[layer][tile_index][(
                        face + 2) % 4] = strand_number
                else:
                    face = (conn[1] + 2) % 4

                # Go to next tile
                if face == 0:  # left
                    if tile_index % size == 0:
                        layer = (layer + 1) % 2
                        tile_index = size*((tile_index//size) + 1) - 1
                    else:
                        tile_index -= 1
                elif face == 1:  # down
                    if (tile_index // size) == size - 1:
                        layer = (layer + 1) % 2
                        tile_index = size**2 - (tile_index % size + 1)
                        face = 3
                    else:
                        tile_index += size
                elif face == 2:  # right
                    if tile_index % size == size - 1:
                        layer = (layer + 1) % 2
                        tile_index = size*(tile_index // size)
                    else:
                        tile_index += 1
                elif face == 3:  # up
                    if tile_index // size == 0:
                        layer = (layer + 1) % 2
                        tile_index = size - (tile_index + 1)
                        face = 1
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
                if mosaic[i0][i1] == 9:
                    if (0, 2) in made_connections[i0][i1]:
                        pd_codes.append(
                            crossing_strands[i0][i1])
                    else:
                        # Rotated by 2
                        pd_codes.append(
                            crossing_strands[i0][i1][2:] + crossing_strands[i0][i1][:2])
                else:
                    if (1, 3) in made_connections[i0][i1]:
                        pd_codes.append(
                            crossing_strands[i0][i1][1:] + crossing_strands[i0][i1][:1])
                    else:
                        pd_codes.append(
                            crossing_strands[i0][i1][3:] + crossing_strands[i0][i1][:3])
            for l in range(len(pd_codes[-1])):
                if pd_codes[-1][l] == strand_number:
                    pd_codes[-1][l] = 1
                    break
            return Link(pd_codes)


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
