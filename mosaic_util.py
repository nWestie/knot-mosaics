def string2matrix(string: str) -> list[int]:
    """convert each char in the string to an int, 
    using hex conversion to properly convert 'a' to 11 """
    return [int(elem, base=16) for elem in string]


def matrix2string(matrix: list[int]) -> str:
    return "".join((hex(t) for t in matrix))


def count_crossings(mosaic: str | list[int]) -> int:
    if type(mosaic) is str:
        return len([t for t in mosaic if t in ['9', 'a']])
    return len([t for t in mosaic if t in [9, 10]])


def count_tiles(mosaic: str | list[int]) -> int:
    if type(mosaic) is str:
        return len([t for t in mosaic if t != '0'])
    return len([t for t in mosaic if t != 0])

