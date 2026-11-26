# SPDX-License-Identifier: GPL-3.0-or-later
"""Point-group symmetry and families of equivalent planes / directions.

The holohedral point groups are used: m-3m (48 operators) for the cubic lattice and
6/mmm (24 operators) for the hexagonal lattice. The operators are 3x3 orthogonal
matrices in the crystal Cartesian frame defined in :mod:`lattice`.

A family {hkl} or <uvw> is obtained by applying every operator to one seed member and
keeping each plane / slip line once (+v and -v are the same member).
"""

from __future__ import annotations

from itertools import permutations, product

import numpy as np

from .lattice import CUBIC, Lattice, canonical


def cubic_operators() -> list:
    """The 48 operators of m-3m: all signed permutation matrices."""
    operators = []
    for perm in permutations(range(3)):
        for signs in product((1.0, -1.0), repeat=3):
            matrix = np.zeros((3, 3))
            for row, (col, sign) in enumerate(zip(perm, signs)):
                matrix[row, col] = sign
            operators.append(matrix)
    return operators


def hexagonal_operators() -> list:
    """The 24 operators of 6/mmm, generated from 6 || z, 2 || x and the inversion."""
    cos60, sin60 = 0.5, np.sqrt(3.0) / 2.0
    six_fold_z = np.array([[cos60, -sin60, 0.0], [sin60, cos60, 0.0], [0.0, 0.0, 1.0]])
    two_fold_x = np.diag([1.0, -1.0, -1.0])
    inversion = -np.eye(3)
    return _close_group([six_fold_z, two_fold_x, inversion])


def point_group(lattice: Lattice) -> list:
    """Symmetry operators of the lattice point group (Cartesian matrices)."""
    return cubic_operators() if lattice.system == CUBIC else hexagonal_operators()


def equivalent_directions(lattice: Lattice, uvw) -> list:
    """All members of the family <uvw> (three Miller indices), one per slip line."""
    to_cartesian = lattice.direct
    to_indices = np.linalg.inv(lattice.direct)
    return _family(lattice, uvw, to_cartesian, to_indices)


def equivalent_planes(lattice: Lattice, hkl) -> list:
    """All members of the family {hkl} (three Miller indices), one per plane."""
    to_cartesian = lattice.reciprocal
    to_indices = lattice.direct.T
    return _family(lattice, hkl, to_cartesian, to_indices)


# --------------------------------------------------------------------------- helpers
def _family(lattice, seed, to_cartesian, to_indices) -> list:
    vector = to_cartesian @ np.asarray(seed, dtype=float)
    members = set()
    for operator in point_group(lattice):
        real = to_indices @ (operator @ vector)
        integers = np.rint(real)
        if not np.allclose(real, integers, atol=1e-9):
            raise ArithmeticError("symmetry operator did not map onto a lattice vector")
        members.add(canonical(integers.astype(int)))
    return sorted(members, reverse=True)


def _close_group(generators) -> list:
    """Multiply the generators with each other until no new operator appears."""
    def key(matrix):
        return tuple(np.round(matrix, 9).ravel() + 0.0)

    group = {key(np.eye(3)): np.eye(3)}
    frontier = [np.eye(3)]
    while frontier:
        new = []
        for element in frontier:
            for generator in generators:
                candidate = generator @ element
                if key(candidate) not in group:
                    group[key(candidate)] = candidate
                    new.append(candidate)
        frontier = new
    return list(group.values())
