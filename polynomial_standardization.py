from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from sympy import symbols, expand
from sympy.parsing.sympy_parser import parse_expr

# from sage.all import KnotInfo  # type: ignore
import mosaics as M

v, z = symbols("v z")


@dataclass(frozen=True)
class Term:
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
    terms: tuple[Term, ...]

    @classmethod
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
    def from_mosaic(cls, mosaic: M.NormMosaic):
        """Build HOMFLY polynomial from mosaic object"""
        import sage_funcs

        # getting polynomial from mosaic
        pd = M.traverse_mosaic(mosaic, prune_unknots=False)
        assert type(pd) is list
        knot = sage_funcs.make_knot(pd)
        new_knot = knot.simplify()
        if new_knot is not None:
            knot = new_knot
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
    """A lookup from homfly to knotID(s)"""

    def lookup(self, poly: str | HOMFLY) -> list[str] | None:
        if type(poly) is str:
            poly = HOMFLY.from_string(poly)
        res = self.lookup_table.get(poly)  # type: ignore
        if res is not None:
            return res
        return self.lookup_table.get(poly.invert_v())  # type: ignore

    def __init__(
        self, LUT_file: Path = Path("homflys/knotsToHOMFLY.txt"), max_size: int = 14
    ):
        self.lookup_table: dict[HOMFLY, list[str]] = {}
        last_size = ""
        for line in LUT_file.open():
            knots, homf = line.split("|")
            knots = [k.strip() for k in knots.split(",")]

            # status printing
            size = knots[0][0:2].removesuffix("_")
            if size != last_size:
                if int(size) > max_size:
                    return
                print(size)
                last_size = size
            # save key
            key = HOMFLY.from_string(homf)
            self.lookup_table[key] = knots


def build_lookup():
    master_dict: dict[HOMFLY, list[str]] = {}
    with Path("homflys3-13.csv").open() as f:
        f.readline()
        for line in f:
            id, string = line.split(",")
            eqn = HOMFLY.from_string(string)
            inv_eqn = eqn.invert_v()

            # break early for testing
            if id.removeprefix("10_165") != id:
                pass
            print(id)
            if eqn in master_dict:
                master_dict[eqn].append(id)
            elif inv_eqn in master_dict:
                master_dict[inv_eqn].append(id)
            else:
                master_dict[eqn] = [id]

    with Path("data/knotsToHOMFLY.txt").open("w") as f:
        for key, vals in master_dict.items():
            # if len(vals) > 1:
            print(", ".join(vals), "|", key, file=f)


def main():
    mosaic = M.NormMosaic.build_mobius("2125a9a1639a4034")
    knot_poly = HOMFLY.from_mosaic(mosaic)
    print(knot_poly)
    # # list of all knots that correspond to a specific polynomial
    knots = KnotIDDB(max_size=10)

    print(knots.lookup(knot_poly))


if __name__ == "__main__":
    exit(main())
