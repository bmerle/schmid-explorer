# SPDX-License-Identifier: GPL-3.0-or-later
"""Inverse pole figure: the loading axis in the standard triangle of the crystal.

An inverse pole figure shows a direction of the sample - here the loading axis l - in
the frame of the crystal. The point-group operators (48 in cubic, 24 in hexagonal
crystals, the inversion included) turn l into its symmetry-equivalent directions, and
exactly one of them lies in the standard triangle (`orientation_map.fundamental_zone`):

    cubic      [001] - [011] - [-111]
    hexagonal  [0001] - [2-1-10] - [10-10]

A unit vector v lies in the triangle with the corners c0, c1, c2 if it is on the inner
side of the three great circles through two corners each:

    v . e_k >= 0,   e_k = +-(c_i x c_j) / |c_i x c_j|,  sign such that e_k . c_k > 0

The smallest of the three products is the "depth" of v in the triangle (the sine of the
angle to the nearest edge, negative outside). The equivalent direction with the largest
depth is the one inside the triangle; on an edge or at a corner several operators give
the same direction.

Because the inversion belongs to both point groups, l and -l - i.e. tension and
compression along the same axis - are the same point of the inverse pole figure.

Frame of the figure: first corner in the centre of the projection (z), second corner on
the +X axis, third corner at Y > 0. For the cubic lattice this is the frame of the
orientation map (`orientation_map.standard_frame`); the hexagonal sector lies flat on
the X axis, turned by 90 degrees with respect to the orientation map.
"""

from __future__ import annotations

import numpy as np

from .lattice import Lattice
from .orientation_map import fundamental_zone
from .schmid import DIRECTION, Loading
from .stereo import project
from .symmetry import point_group


def triangle_corners(lattice: Lattice) -> np.ndarray:
    """Unit vectors of the three corners of the standard triangle (rows), crystal Cartesian frame."""
    return np.array([lattice.direction_vector(corner) for corner in fundamental_zone(lattice)])


def triangle_frame(lattice: Lattice) -> np.ndarray:
    """Rotation crystal -> frame of the inverse pole figure (v_frame = R @ v_crystal)."""
    first, second, third = triangle_corners(lattice)
    z = first
    x = second - np.dot(second, z) * z
    x = x / np.linalg.norm(x)
    y = np.cross(z, x)
    if np.dot(y, third) < 0:
        raise ArithmeticError("the corners of the standard triangle must be given counter-clockwise")
    return np.vstack([x, y, z])


def edge_normals(lattice: Lattice) -> np.ndarray:
    """Inward unit normals e_k (rows) of the three great circles bounding the standard triangle."""
    corners = triangle_corners(lattice)
    normals = []
    for k in range(3):
        opposite, start, end = corners[k], corners[(k + 1) % 3], corners[(k + 2) % 3]
        normal = np.cross(start, end)
        normal = normal / np.linalg.norm(normal)
        normals.append(normal if np.dot(normal, opposite) > 0 else -normal)
    return np.array(normals)


def depth(lattice: Lattice, vector) -> float:
    """Sine of the angle between `vector` and the nearest edge of the triangle (negative: outside)."""
    v = np.asarray(vector, dtype=float)
    return float(np.min(edge_normals(lattice) @ (v / np.linalg.norm(v))))


def triangle_operator(lattice: Lattice, vector) -> np.ndarray:
    """Point-group operator (Cartesian matrix) that takes `vector` into the standard triangle."""
    v = np.asarray(vector, dtype=float)
    v = v / np.linalg.norm(v)
    normals = edge_normals(lattice)
    operators = point_group(lattice)
    depths = [np.min(normals @ (operator @ v)) for operator in operators]
    return operators[int(np.argmax(depths))]


def reduce_vector(lattice: Lattice, vector) -> np.ndarray:
    """Unit vector of the direction equivalent to `vector` inside the standard triangle."""
    v = np.asarray(vector, dtype=float)
    return triangle_operator(lattice, v) @ (v / np.linalg.norm(v))


def reduce_loading(lattice: Lattice, loading: Loading) -> Loading:
    """The symmetry-equivalent loading axis inside the standard triangle, with integer indices.

    A direction [uvw] is transformed with the structure matrix D, a plane normal (hkl)
    with the reciprocal matrix D* (see `symmetry`); the loading sense is kept.
    """
    if loading.kind == DIRECTION:
        to_cartesian, to_indices = lattice.direct, np.linalg.inv(lattice.direct)
    else:
        to_cartesian, to_indices = lattice.reciprocal, lattice.direct.T
    vector = to_cartesian @ np.asarray(loading.indices, dtype=float)
    real = to_indices @ (triangle_operator(lattice, vector) @ vector)
    integers = np.rint(real)
    if not np.allclose(real, integers, atol=1e-9):
        raise ArithmeticError("symmetry operator did not map onto a lattice vector")
    return Loading(tuple(int(i) for i in integers), loading.kind, loading.sense)


def triangle_point(lattice: Lattice, vector) -> np.ndarray:
    """Stereographic coordinates (X, Y) of `vector` in the inverse pole figure."""
    reduced = triangle_frame(lattice) @ reduce_vector(lattice, vector)
    reduced[2] = max(reduced[2], 0.0)              # rounding on the hexagonal basal edge
    return project(reduced)


__all__ = ["triangle_corners", "triangle_frame", "edge_normals", "depth", "triangle_operator",
           "reduce_vector", "reduce_loading", "triangle_point"]
