# SPDX-License-Identifier: GPL-3.0-or-later
"""Orientation map: the highest Schmid factor as a function of the loading axis.

The map is drawn in the standard projection of the crystal ([001] resp. [0001] in the
centre). Every point (X, Y) of the unit disc is a possible loading axis l; the map
value is

    max over all slip systems of  |(n.l)(b.l)|                (Schmid ranking)
    min over all slip systems of  tau_CRSS / |(n.l)(b.l)|     (yield-stress ranking)

A picked axis is snapped to the nearest direction (or plane normal) with small integer
indices, so that the axis used in the calculation is exactly the one displayed.
"""

from __future__ import annotations

from itertools import product

import numpy as np

from .lattice import CUBIC, Lattice, canonical, reduce_indices
from .schmid import DIRECTION, Analysis
from .stereo import inverse_project, sample_frame


def standard_frame(lattice: Lattice) -> np.ndarray:
    """Rotation crystal -> projection frame with [001] / [0001] in the centre."""
    rotation, _ = sample_frame(lattice, lattice.direction_vector((0, 0, 1)))
    return rotation


def fundamental_zone(lattice: Lattice) -> list:
    """Corners of the standard triangle (three-index directions)."""
    if lattice.system == CUBIC:
        return [(0, 0, 1), (0, 1, 1), (-1, 1, 1)]
    return [(0, 0, 1), (1, 0, 0), (2, 1, 0)]       # [0001], [2-1-10], [10-10]


def schmid_map(analysis: Analysis, pixels: int = 241):
    """Map over the standard projection. Returns X, Y (1-D) and values (2-D, nan outside).

    `values` is the maximum Schmid factor, or the minimum yield stress (in units of the
    CRSS values) if the analysis ranks by CRSS.
    """
    rotation = standard_frame(analysis.lattice)
    coordinate = np.linspace(-1.0, 1.0, pixels)
    X, Y = np.meshgrid(coordinate, coordinate)
    inside = X * X + Y * Y <= 1.0
    axes = inverse_project(np.stack([X, Y], axis=-1)) @ rotation    # sample -> crystal

    normals = np.array([r.n for r in analysis.results])
    burgers = np.array([r.b for r in analysis.results])
    values = np.full(X.shape, np.nan)
    if len(normals):
        m = np.abs((axes @ normals.T) * (axes @ burgers.T))         # (pixels, pixels, systems)
        if analysis.use_crss:
            crss = np.array([r.crss for r in analysis.results])
            with np.errstate(divide="ignore"):
                values = np.min(crss / m, axis=-1)
        else:
            values = np.max(m, axis=-1)
        values = np.where(inside, values, np.nan)
    return coordinate, coordinate, values


def snap_to_indices(lattice: Lattice, vector, kind: str = DIRECTION, max_index: int = 9) -> tuple:
    """Three Miller indices of the low-index direction / plane normal closest to `vector`.

    All index triples (cubic) or Miller-Bravais quadruples (hexagonal) with
    |index| <= max_index are compared; among equally close ones the shortest wins.
    """
    target = np.asarray(vector, dtype=float)
    target = target / np.linalg.norm(target)
    span = range(-max_index, max_index + 1)
    if lattice.four_index:
        # enumerate the first two and the last Miller-Bravais indices, third = -(1st + 2nd)
        quads = np.array([(p, q, -(p + q), r) for p, q, r in product(span, repeat=3)
                          if abs(p + q) <= max_index and (p, q, r) != (0, 0, 0)])
        if kind == DIRECTION:
            triples = np.column_stack(
                [quads[:, 0] - quads[:, 2], quads[:, 1] - quads[:, 2], quads[:, 3]])
        else:
            triples = quads[:, [0, 1, 3]]
    else:
        triples = np.array([t for t in product(span, repeat=3) if t != (0, 0, 0)])

    matrix = lattice.direct if kind == DIRECTION else lattice.reciprocal
    cartesian = triples @ matrix.T
    lengths = np.linalg.norm(cartesian, axis=1)
    cosines = cartesian @ target / lengths
    best = np.max(cosines)
    candidates = np.where(cosines >= best - 1e-12)[0]
    choice = candidates[np.argmin(lengths[candidates])]
    return reduce_indices(triples[choice])


__all__ = ["standard_frame", "fundamental_zone", "schmid_map", "snap_to_indices", "canonical"]
