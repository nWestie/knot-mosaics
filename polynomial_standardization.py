import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from sympy import symbols, Poly, expand
from sympy.parsing.sympy_parser import parse_expr
from sage.all import KnotInfo  # type: ignore
import mosaics as M
import sage_funcs

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
        string = string.replace("^", "**")
        expr = parse_expr(string, local_dict={"v": v, "z": z})
        poly = expand(expr)
        terms = (Term.from_scipy(t) for t in poly.as_ordered_terms())
        return HOMFLY(cls.sort(terms))
    @classmethod
    def sort(cls, terms: Iterable[Term])->tuple[Term,...]:
        """puts terms in canonical order, sorted first by z power, than v"""
        return tuple(sorted(terms,key=lambda t: t.ordering(),reverse=True))

    def invert_v(self) -> "HOMFLY":
        terms = [t.invert_v() for t in self.terms]
        return HOMFLY(self.sort(terms))

    def negate(self) -> "HOMFLY":
        terms = frozenset([t.negate() for t in self.terms])
        return HOMFLY(self.sort(terms))

    def __repr__(self) -> str:
        return " + ".join(str(t) for t in self.terms)


def main():
    # list of all knots that correspond to a specific polynomial
    master_dict: dict[HOMFLY, list[str]] = {}
    with Path("homflys3-13.csv").open() as f:
        f.readline()
        for line in f:
            id, string = line.split(",")
            eqn = HOMFLY.from_string(string)
            inv_eqn = eqn.invert_v()

            # break early for testing
            # if id.removeprefix("11") != id:
            #     break
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
            print(", ".join(vals), "|",key, file=f)


def test_terms():
    # getting polynomial from mosaic
    mosaic = M.NormMosaic.build_flat("00000000210002a9102a8a9139a9a4034340")
    pd = M.traverse_mosaic(mosaic)
    assert type(pd) is list
    knot = sage_funcs.make_knot(pd)
    knot.simplify()
    knot_homf = knot.homfly_polynomial(normalization="vz")

    knotinfo_homf = "(v^4+ v^6-v^10)+ (v^2+ 2*v^4+ 2*v^6+ v^8)*z^2"
    h1 = HOMFLY.from_string(str(knot_homf)).invert_v()
    h2 = HOMFLY.from_string(knotinfo_homf)
    print(h1,h2,h1==h2,sep="\n")
    exit()

if __name__ == "__main__":
    # exit(test_terms())
    exit(main())
