# SPDX-License-Identifier: GPL-3.0-or-later
"""Crystal lattices (cubic, hexagonal) and conversions between index notations.

Conventions
-----------
* All lengths are in units of the lattice parameter a (Schmid factors only depend on
  angles, i.e. on c/a for the hexagonal lattice).
* Crystal Cartesian frame
    cubic      : x, y, z along a1, a2, a3
    hexagonal  : a1 = (1, 0, 0), a2 = (-1/2, sqrt(3)/2, 0), c = (0, 0, c/a)
* Internally every plane and direction is stored with three Miller indices, also for
  the hexagonal lattice. The four Miller-Bravais indices are only used for input and
  display:
    direction [uvtw] -> [UVW] = [u - t, v - t, w]         (t = -(u + v))
    direction [UVW]  -> [uvtw] = [2U - V, 2V - U, -(U + V), 3W] / 3
    plane (hkil)     <-> (hkl),  i = -(h + k)
* A direction [UVW] has the Cartesian vector D.[U, V, W]; the normal of a plane (hkl)
  is D*.(h, k, l), with D the structure matrix (columns = lattice vectors) and
  D* = (D^-1)^T the reciprocal structure matrix.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import reduce
from math import gcd, sqrt

import numpy as np

CUBIC = "cubic"
HEXAGONAL = "hexagonal"


# --------------------------------------------------------------------------- indices
def reduce_indices(indices) -> tuple:
    """Divide integer indices by their greatest common divisor."""
    ints = tuple(int(i) for i in indices)
    divisor = reduce(gcd, (abs(i) for i in ints))
    if divisor == 0:
        return ints
    return tuple(i // divisor for i in ints)


def canonical(indices) -> tuple:
    """Reduced indices with the first non-zero index positive.

    +v and -v describe the same plane (or the same slip line), so this is the key
    under which planes and slip directions are identified.
    """
    reduced = reduce_indices(indices)
    for i in reduced:
        if i != 0:
            return reduced if i > 0 else tuple(-j for j in reduced)
    return reduced


def mb_direction_to_miller(uvtw) -> tuple:
    """Miller-Bravais direction [uvtw] -> three-index direction [UVW] (reduced)."""
    u, v, t, w = (int(i) for i in uvtw)
    if u + v + t != 0:
        raise ValueError("Miller-Bravais direction needs u + v + t = 0")
    return reduce_indices((u - t, v - t, w))


def miller_to_mb_direction(uvw) -> tuple:
    """Three-index direction [UVW] -> Miller-Bravais direction [uvtw] (reduced)."""
    U, V, W = (int(i) for i in uvw)
    return reduce_indices((2 * U - V, 2 * V - U, -(U + V), 3 * W))


def mb_plane_to_miller(hkil) -> tuple:
    """Miller-Bravais plane (hkil) -> three-index plane (hkl)."""
    h, k, i, l = (int(x) for x in hkil)
    if h + k + i != 0:
        raise ValueError("Miller-Bravais plane needs h + k + i = 0")
    return (h, k, l)


def miller_to_mb_plane(hkl) -> tuple:
    """Three-index plane (hkl) -> Miller-Bravais plane (hkil)."""
    h, k, l = (int(x) for x in hkl)
    return (h, k, -(h + k), l)


def indices_text(indices, brackets: str) -> str:
    """Plain-text indices, e.g. '[1 -1 0]' (unambiguous also for two-digit indices)."""
    return brackets[0] + " ".join(str(int(i)) for i in indices) + brackets[1]


def indices_tex(indices, brackets: str) -> str:
    """Mathtext indices with overbars for negative values, e.g. r'$[1\\bar{1}0]$'."""
    separator = r"\," if any(abs(int(i)) > 9 for i in indices) else ""
    body = separator.join(
        rf"\bar{{{abs(int(i))}}}" if int(i) < 0 else str(int(i)) for i in indices
    )
    left = {"[": "[", "(": "(", "{": r"\{", "<": r"\langle "}[brackets[0]]
    right = {"]": "]", ")": ")", "}": r"\}", ">": r"\rangle "}[brackets[1]]
    return f"${left}{body}{right}$"


# --------------------------------------------------------------------------- lattice
@dataclass(frozen=True)
class Lattice:
    """Cubic or hexagonal lattice; the hexagonal one is defined by its c/a ratio."""

    system: str
    c_over_a: float = 1.0

    def __post_init__(self):
        if self.system not in (CUBIC, HEXAGONAL):
            raise ValueError(f"unknown lattice system {self.system!r}")
        if self.system == HEXAGONAL and not self.c_over_a > 0:
            raise ValueError("c/a must be positive")

    # ---- structure matrices
    @property
    def direct(self) -> np.ndarray:
        """Structure matrix D: columns are the lattice vectors in the Cartesian frame."""
        if self.system == CUBIC:
            return np.eye(3)
        return np.array(
            [
                [1.0, -0.5, 0.0],
                [0.0, sqrt(3.0) / 2.0, 0.0],
                [0.0, 0.0, self.c_over_a],
            ]
        )

    @property
    def reciprocal(self) -> np.ndarray:
        """Reciprocal structure matrix D* = (D^-1)^T: columns are reciprocal vectors."""
        return np.linalg.inv(self.direct).T

    # ---- indices -> Cartesian unit vectors
    def direction_vector(self, uvw) -> np.ndarray:
        """Unit vector along the direction [UVW] (three Miller indices)."""
        return _unit(self.direct @ np.asarray(uvw, dtype=float))

    def plane_normal(self, hkl) -> np.ndarray:
        """Unit normal of the plane (hkl) (three Miller indices)."""
        return _unit(self.reciprocal @ np.asarray(hkl, dtype=float))

    # ---- Cartesian vectors -> (real-valued) indices
    def direction_from_vector(self, vector) -> np.ndarray:
        """Real-valued direction indices [UVW] of a Cartesian vector."""
        return np.linalg.inv(self.direct) @ np.asarray(vector, dtype=float)

    def plane_from_vector(self, vector) -> np.ndarray:
        """Real-valued plane indices (hkl) of the plane normal to a Cartesian vector."""
        return self.direct.T @ np.asarray(vector, dtype=float)

    # ---- display
    @property
    def four_index(self) -> bool:
        return self.system == HEXAGONAL

    def direction_indices(self, uvw) -> tuple:
        """Indices as displayed: [uvw] (cubic) or Miller-Bravais [uvtw] (hexagonal)."""
        return miller_to_mb_direction(uvw) if self.four_index else tuple(int(i) for i in uvw)

    def plane_indices(self, hkl) -> tuple:
        """Indices as displayed: (hkl) (cubic) or Miller-Bravais (hkil) (hexagonal)."""
        return miller_to_mb_plane(hkl) if self.four_index else tuple(int(i) for i in hkl)

    def direction_text(self, uvw) -> str:
        return indices_text(self.direction_indices(uvw), "[]")

    def plane_text(self, hkl) -> str:
        return indices_text(self.plane_indices(hkl), "()")

    def direction_tex(self, uvw) -> str:
        return indices_tex(self.direction_indices(uvw), "[]")

    def plane_tex(self, hkl) -> str:
        return indices_tex(self.plane_indices(hkl), "()")


def _unit(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)
    if norm == 0:
        raise ValueError("zero vector has no direction")
    return vector / norm
