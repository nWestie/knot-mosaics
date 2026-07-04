from dataclasses import dataclass
import functools
from pathlib import Path
from typing import Callable


def string2tiles(string: str) -> list[int]:
    """convert each char in the string to an int,
    using hex conversion to properly convert 'a' to 10"""
    return [int(elem, base=16) for elem in string.strip()]


def tiles2string(matrix: list[int]) -> str:
    return "".join(f"{t:x}" for t in matrix)


def count_crossings(mosaic: str | list[int]) -> int:
    if type(mosaic) is str:
        return len([t for t in mosaic if t in ["9", "a"]])
    return len([t for t in mosaic if t in [9, 10]])


def count_tiles(mosaic: str | list[int]) -> int:
    if type(mosaic) is str:
        return len([t for t in mosaic if (t not in ["0", "c"])])
    return len([t for t in mosaic if (t not in [0, 12])])


def knot_size_from_id(knot_id: str) -> int:
    return int(knot_id[0:2].removesuffix("_"))


def mosaic_dir(type: str, size: int, cubic_type: str | None = None) -> Path:
    """get the input folder of mosaics"""
    path = Path(f"data/{size}_{type}")
    if cubic_type and type == "cubic":
        path /= cubic_type
    return path


def results_dir(type: str, cubic_type: str | None = None) -> Path:
    """Get the output folder of intermediate results"""
    path = Path(f"data/{type}_res")
    if cubic_type and type == "cubic":
        path /= cubic_type
    return path


def results_dir_knotID(type: str, cubic_type: str | None = None) -> Path:
    """Get the output folder of intermediate results, based on knotID instead of polynomial"""
    path = Path(f"data/{type}_res_knID")
    if cubic_type and type == "cubic":
        path /= cubic_type
    return path


# dir of final results
output_dir = Path(f"output/")


def output_path(type: str, cubic_type: str | None = None) -> Path:
    cub_str = cubic_type + "_" if (cubic_type is not None and type == "cubic") else ""
    return output_dir / f"{type}_{cub_str}results.txt"


def img_dir(type: str, cubic_type: str | None = None) -> Path:
    """Get the output folder for images"""
    path = output_dir / f"{type}_imgs"
    if cubic_type and type == "cubic":
        path /= cubic_type
    return path


def img_filepath(dir: Path, res: "KnotResult"):
    """Path where an image for a specific result should be stored"""
    img_path = dir / (f"{res.size}-{res.knotID}-{res.mosaic_str}.png")
    return img_path




@dataclass
class KnotResult:
    """Seperating this allows us to compare results without calculating the polynomial"""

    size: int
    mosaic_str: str
    tile_ct: int
    polynomial: str
    knotID: str

    def better_than(self, other: "KnotResult|None") -> bool:
        """Returns True if self is the preferred result over other"""
        # Some result preferred to none
        if other is None:
            return True
        # Smaller mosaic is preferred
        if self.size != other.size:
            return self.size < other.size
        # lower tile number is preferred
        if self.tile_ct != other.tile_ct:
            return self.tile_ct < other.tile_ct
        # lower indexes preffered
        return int(self.mosaic_str, 16) < int(other.mosaic_str, 16)
        # TODO: Implement edge connections metric?
        # fewer edge connections preferred. Would be super annoying with only results

    def to_result(self, polynomial: str, ID) -> "KnotResult":
        """Adds a polnomial to make a complete knot result"""
        return KnotResult(self.size, self.mosaic_str, self.tile_ct, polynomial, ID)

    def to_str(self) -> str:
        return f"{self.knotID:<8}|{self.size:>4} |{self.mosaic_str}|{self.tile_ct:>4} |{self.polynomial}"

    @classmethod
    def from_str(cls, str: str):
        parts = [s.strip() for s in str.split("|")]
        return KnotResult(int(parts[1]), parts[2], int(parts[3]), parts[4], parts[0])

    @classmethod
    def from_str_dep(cls, str: str):
        if not hasattr(cls, "warned_dep"):
            cls.warned_dep = True
            print("WARN: using old results, knot IDs will be incorrect")
        parts = [s.strip() for s in str.split("|")]
        return KnotResult(int(parts[0]), parts[1], int(parts[2]), parts[3], "NONE_ID")


def load_result_file(
    file: Path, *, use_dep: bool = False
) -> tuple[list[KnotResult], bool]:
    """Extracts knot results from file. Returns true if file contains the correct end-indicator"""
    results: list[KnotResult] = []
    with file.open("r") as inp:
        for line in inp:
            # If this line is not present, indicates an interruption during writing.
            line = line.strip()
            if line == "END_RESULT":
                return results, True
            if line:
                if use_dep:
                    results.append(KnotResult.from_str_dep(line))
                else:
                    results.append(KnotResult.from_str(line))

    return results, False
