from dataclasses import dataclass
from pathlib import Path
from typing import Callable


def string2tiles(string: str) -> list[int]:
    """convert each char in the string to an int,
    using hex conversion to properly convert 'a' to 11"""
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

def knot_size_from_id(knot_id: str)->int:
    return int(knot_id[0:2].removesuffix("_"))


def mosaic_dir(type: str, size: int, cubic_type: str | None = None) -> Path:
    # get the input folder of mosaics
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


def img_filepath(dir: Path, res: "KnotResult", knotid: str):
    """Path where an image for a specific result should be stored"""
    img_path = dir / (f"{res.size}-{knotid}-{res.mosaic_str}.png")
    return img_path


@dataclass
class IncompleteKnotResult:
    """Seperating this allows us to compare results without calculating the polynomial"""

    size: int
    mosaic_str: str
    tile_ct: int

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

    def to_result(self, polynomial: str) -> "KnotResult":
        """Adds a polnomial to make a complete knot result"""
        return KnotResult(self.size, self.mosaic_str, self.tile_ct, polynomial)


@dataclass
class KnotResult(IncompleteKnotResult):
    """Intermediate format for knot results"""

    polynomial: str

    def to_str(self) -> str:
        return f"{self.size}|{self.mosaic_str}|{self.tile_ct}|{self.polynomial}"

    @classmethod
    def from_str(cls, str: str):
        parts = str.strip().split("|")
        return KnotResult(
            int(parts[0]), parts[1].strip(), int(parts[2]), parts[3].strip()
        )
    
def load_result_file(file: Path) -> tuple[list[KnotResult], bool]:
    """Extracts knot results from file. Returns true if file contains the correct end-indicator"""
    results: list[KnotResult] = []
    with file.open("r") as inp:
        for line in inp:
            # If this line is not present, indicates an interruption during writing.
            line = line.strip()
            if line == "END_RESULT":
                return results, True
            if line:
                results.append(KnotResult.from_str(line))
    return results, False