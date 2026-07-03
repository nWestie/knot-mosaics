from dataclasses import dataclass
import functools
from pathlib import Path
import pickle
from time import time
from typing import Iterable
from sympy import symbols, expand
from sympy.parsing.sympy_parser import parse_expr
import mosaic_util as util
# from sage.all import KnotInfo  # type: ignore
import mosaics as M

v, z = symbols("v z")


@dataclass(frozen=True)
class Term:
    """A single term of a homfly polynomial"""

    coeff: int
    v_pow: int
    z_pow: int

    def __repr__(self) -> str:
        out = []
        match self.coeff:
            case 1:
                if (self.v_pow == 0) and (self.z_pow == 0):
                    return "1"
                pass
            case -1:
                out.append("-1")
            case _:
                out.append(str(self.coeff))

        def pow_repr(out: list[str], base: str, pow: int):
            # out-variable makes life easier here, because it might not add a term
            match pow:
                case 0:
                    return
                case 1:
                    out.append(f"{base}")
                case _:
                    out.append(f"{base}^{pow}")

        pow_repr(out, "v", self.v_pow)
        pow_repr(out, "z", self.z_pow)
        return "*".join(out)

    def invert_v(self) -> "Term":
        return Term(self.coeff, -self.v_pow, self.z_pow)

    def negate(self) -> "Term":
        return Term(-self.coeff, self.v_pow, self.z_pow)

    def ordering(self) -> int:
        """This is a hacky way to sort them...
        we're just assuming v won't be to a power higher than 1000, which holds for reasonable knots
        """
        return self.z_pow * 1000 + self.v_pow

    @classmethod
    def from_scipy(cls, term) -> "Term":
        powers: dict = term.as_powers_dict()
        v_pow = int(powers.pop(v, 0))
        z_pow = int(powers.pop(z, 0))
        coeff = 1
        if len(powers):
            coeff = int(list(powers.keys())[0])
        return Term(coeff, v_pow, z_pow)


@dataclass(frozen=True)
class HOMFLY:
    """A homfly polynomial, parsed into a standard form"""

    terms: tuple[Term, ...]

    @classmethod
    @functools.cache
    def from_string(cls, string):
        """
        Parse HOMFLY polynomial string into standard form using SymPy.
        """
        string = string.replace("^", "**").strip()
        expr = parse_expr(string, local_dict={"v": v, "z": z})
        poly = expand(expr)
        terms = [Term.from_scipy(t) for t in poly.as_ordered_terms()]
        return HOMFLY(cls.sort(terms))

    @classmethod
    def from_knot(cls, knot):
        """Build HOMFLY polynomial from mosaic object"""
        knot_homf = knot.homfly_polynomial(normalization="vz")
        return cls.from_string(str(knot_homf))

    @classmethod
    def sort(cls, terms: Iterable[Term]) -> tuple[Term, ...]:
        """puts terms in canonical order, sorted first by z power, than v"""
        return tuple(sorted(terms, key=lambda t: t.ordering(), reverse=True))

    def invert_v(self) -> "HOMFLY":
        terms = [t.invert_v() for t in self.terms]
        return HOMFLY(self.sort(terms))

    def negate(self) -> "HOMFLY":
        terms = frozenset([t.negate() for t in self.terms])
        return HOMFLY(self.sort(terms))

    def __repr__(self) -> str:
        return " + ".join(str(t) for t in self.terms)


class KnotIDDB:
    """A lookup table from homfly to knotID(s)"""

    def lookup(self, poly: str | HOMFLY) -> tuple[str,...] | None:
        if type(poly) is str:
            poly = HOMFLY.from_string(poly)
        res = self.lookup_table.get(poly)  # type: ignore
        if res is not None:
            return res
        return self.lookup_table.get(poly.invert_v())  # type: ignore

    @classmethod
    def load_from_file(cls, path: Path) -> "KnotIDDB":
        with path.open("rb") as file:
            knots: KnotIDDB = pickle.load(file)
            if type(knots) is not KnotIDDB:
                raise ValueError(f"{path} is not a KnotIDDB pickle")
        return knots

    def dump_to_file(self, path: Path):
        with path.open("wb") as file:
            pickle.dump(self, file)

    def __init__(
        self, LUT_file: Path = Path("homflys/knotsToHOMFLY.txt"), max_size: int = 14
    ):
        self.lookup_table: dict[HOMFLY, tuple[str,...]] = {}

        for line in LUT_file.open():
            knots, homf = line.split("|")
            knots = tuple(k.strip() for k in knots.split(","))

            # status printing
            size = util.knot_size_from_id(knots[0])
            if size > max_size:
                return
            # save key
            key = HOMFLY.from_string(homf)
            self.lookup_table[key] = knots


def build_lookup():
    """Constructs a Lookup-file - each line is a list of knot IDs, and their homfly in a standardized form"""
    master_dict: dict[HOMFLY, list[str]] = {}
    with Path("homflys/homflys3-13.csv").open() as f:
        f.readline()  # Remove header
        for line in f:
            id, string = line.split(",")
            eqn = HOMFLY.from_string(string)
            inv_eqn = eqn.invert_v()

            print(id)
            if eqn in master_dict:
                master_dict[eqn].append(id)
            elif inv_eqn in master_dict:
                master_dict[inv_eqn].append(id)
            else:
                master_dict[eqn] = [id]

    with Path("homflys/knotsToHOMFLY.txt").open("w") as f:
        for key, vals in master_dict.items():
            # if len(vals) > 1:
            print(", ".join(vals), "|", key, file=f)


def main():
    # build_lookup()

    # Testing
    # print(knot_poly)
    # # list of all knots that correspond to a specific polynomial

    # knots = KnotIDDB(max_size=14)
    pkl_file = Path("data/knotIDDB.pkl")
    # print("loaded")

    s_time = time()
    knots = KnotIDDB.load_from_file(pkl_file)
    print(f"Load Time: {time()-s_time:.4g}")
    mosaic = M.NormMosaic.build_mobius("2125a9a1639a4034")
    knot_poly = HOMFLY.from_knot(mosaic)
    print(knots.lookup(knot_poly))


if __name__ == "__main__":
    exit(main())
