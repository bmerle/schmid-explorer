# SPDX-License-Identifier: GPL-3.0-or-later
"""Stereographic projection, pillar geometry, orientation map, inverse pole figure and table export."""

import csv
import io

import numpy as np
import pytest

from schmid_explorer.core import export, inverse_pole_figure, orientation_map, pillar, stereo, symmetry
from schmid_explorer.core.lattice import CUBIC, HEXAGONAL, Lattice, mb_direction_to_miller
from schmid_explorer.core.schmid import (
    DIRECTION, PLANE_NORMAL, Loading, analyse, force_sign, load_axis,
)


# ------------------------------------------------------------------ projection
def test_sample_frame():
    lattice = Lattice(CUBIC)
    rotation, reference = stereo.sample_frame(lattice, np.array([0.0, 0.0, 1.0]))
    assert reference == (1, 0, 0)
    assert np.allclose(rotation @ rotation.T, np.eye(3)) and np.isclose(np.linalg.det(rotation), 1)
    # standard (001) projection: [100] at the south, [010] at the east, [001] in the centre
    assert np.allclose(rotation @ [1, 0, 0], [0, -1, 0])
    assert np.allclose(rotation @ [0, 1, 0], [1, 0, 0])
    assert np.allclose(rotation @ [0, 0, 1], [0, 0, 1])
    # load axis parallel to the first reference direction -> fallback reference
    rotation, reference = stereo.sample_frame(lattice, np.array([1.0, 0.0, 0.0]))
    assert reference == (0, 1, 0)
    assert np.allclose(rotation @ [1, 0, 0], [0, 0, 1])
    # the azimuth turns the crystal counter-clockwise in the projection
    turned, _ = stereo.sample_frame(lattice, np.array([0.0, 0.0, 1.0]), 90.0)
    assert np.allclose(turned @ [1, 0, 0], [1, 0, 0])


@pytest.mark.parametrize("azimuth", [0.0, 30.0])
def test_sample_frame_follows_the_force(azimuth):
    """Tension: the pillar frame. Compression: z along the force, by a half turn about y."""
    lattice = Lattice(CUBIC)
    axis = np.array([0.0, 1.0, 2.0]) / np.sqrt(5)
    pillar_rotation, _ = stereo.pillar_frame(lattice, axis, azimuth)
    tension, _ = stereo.sample_frame(lattice, axis, azimuth, sign=1)
    compression, _ = stereo.sample_frame(lattice, axis, azimuth, sign=-1)
    assert np.allclose(tension, pillar_rotation)
    assert np.allclose(tension @ axis, [0, 0, 1])
    assert np.allclose(compression @ -axis, [0, 0, 1])          # the force is the centre of the projection
    assert np.allclose(compression @ compression.T, np.eye(3)) and np.isclose(np.linalg.det(compression), 1)
    # x is reversed, y is kept; the crystal does not move in the pillar
    assert np.allclose(compression, stereo.HALF_TURN @ pillar_rotation)
    assert np.allclose(compression[0], -tension[0]) and np.allclose(compression[1], tension[1])
    assert np.allclose(stereo.to_pillar(-1) @ compression, pillar_rotation)
    assert np.allclose(stereo.to_pillar(1), np.eye(3))
    assert np.allclose(stereo.to_pillar(-1) @ stereo.to_pillar(-1), np.eye(3))
    # a vector v in tension and -v in compression: same X, mirrored Y
    v = np.array([1.0, 1.0, 1.0]) / np.sqrt(3)
    assert np.allclose(stereo.project(compression @ -v), stereo.project(tension @ v) * [1, -1])
    if azimuth == 0:                                            # the reference [100] stays at the south
        south = stereo.project(stereo.upper(compression @ [1.0, 0, 0]))
        assert np.isclose(south[0], 0) and south[1] < 0


def test_projection_round_trip_and_radius():
    rng = np.random.default_rng(1)
    v = rng.normal(size=(50, 3))
    v = stereo.upper(v / np.linalg.norm(v, axis=1, keepdims=True))
    assert np.all(v[:, 2] >= 0)
    xy = stereo.project(v)
    assert np.all(np.linalg.norm(xy, axis=1) <= 1 + 1e-12)
    assert np.allclose(stereo.inverse_project(xy), v)
    # a direction at rho from the centre plots at tan(rho / 2)
    rho = np.radians(35.0)
    assert np.isclose(np.linalg.norm(stereo.project([np.sin(rho), 0, np.cos(rho)])), np.tan(rho / 2))


def test_great_circle_is_normal_to_pole():
    pole = np.array([1.0, 2.0, 2.0]) / 3.0
    trace = stereo.inverse_project(stereo.great_circle(pole))
    assert np.allclose(trace @ pole, 0, atol=1e-12)
    assert np.all(trace[:, 2] >= -1e-12)
    primitive = stereo.great_circle([0, 0, 1])
    assert np.allclose(np.linalg.norm(primitive, axis=1), 1)


def test_equatorial_poles_plot_twice():
    assert len(stereo.plot_points(np.array([1.0, 0.0, 0.0]))) == 2
    assert len(stereo.plot_points(np.array([0.6, 0.0, 0.8]))) == 1
    assert np.allclose(stereo.plot_points(np.array([0.6, 0.0, -0.8])), [[-1 / 3, 0]])


@pytest.mark.parametrize("sense", ["tension", "compression"])
def test_every_normal_and_slip_direction_plots_in_the_hemisphere_of_the_force(sense):
    """In the sample frame n and b have z >= 0; their distance from the centre gives theta and lambda."""
    analysis = analyse("bcc", Loading((1, 2, 3), sense=sense), ["bcc_110_111", "bcc_112_111"])
    rotation, _ = stereo.sample_frame(analysis.lattice, analysis.axis, 20.0, force_sign(sense))
    assert np.allclose(rotation @ analysis.force, [0, 0, 1])
    for r in analysis.results:
        for vector, angle in ((r.n, r.theta_deg), (r.b, r.lambda_deg)):
            assert (rotation @ vector)[2] >= -1e-12
            xy = stereo.plot_points(rotation @ vector)[0]
            assert np.isclose(np.hypot(*xy), np.tan(np.radians(angle) / 2))


def test_arc_and_small_circle():
    points = stereo.arc([0, 0, 1], [1, 0, 0], 10)
    assert np.allclose(np.linalg.norm(points, axis=1), 1)
    assert np.allclose(points[0], [0, 0, 1]) and np.allclose(points[-1], [1, 0, 0])
    circle = stereo.small_circle_about_axis(45.0)
    assert np.allclose(np.linalg.norm(circle, axis=1), np.tan(np.radians(22.5)))


# ------------------------------------------------------------------ pillar
@pytest.mark.parametrize("normal", [
    (0, 0, 1), (1, 1, 1), (1, 0, 0), (0.2, -0.1, 1), (3, 1, 0.5), (1, 2, 0),
])
def test_split_conserves_volume(normal):
    shape = pillar.PillarShape()
    below, above = pillar.split(normal, shape)
    total = pillar.prism_volume(shape)
    assert pillar.volume(below) + pillar.volume(above) == pytest.approx(total, rel=1e-9)
    assert pillar.volume(below) == pytest.approx(total / 2, rel=1e-9)   # plane through the centre
    n = np.array(normal, float) / np.linalg.norm(normal)
    for polygon in [p for group in below.values() for p in group]:
        assert np.all(polygon @ n <= 1e-9)
    for polygon in [p for group in above.values() for p in group]:
        assert np.all(polygon @ n >= -1e-9)


def test_section_lies_in_plane_and_pillar():
    shape = pillar.PillarShape()
    n = np.array([1.0, 1.0, 1.0]) / np.sqrt(3)
    polygon = pillar.section(n, shape)
    assert len(polygon) > 10
    assert np.allclose(polygon @ n, 0, atol=1e-9)
    assert np.all(np.hypot(polygon[:, 0], polygon[:, 1]) <= shape.radius + 1e-9)
    assert np.all(np.abs(polygon[:, 2]) <= shape.height / 2 + 1e-9)


@pytest.mark.parametrize("normal", [(1, 1, 1), (0.2, -0.1, 1), (3, 1, 0.5), (0, 0, 1)])
def test_blocks_are_ordered_by_the_top_face(normal):
    """Whatever the sign of the normal: (block on the substrate, block carrying the top face)."""
    shape = pillar.PillarShape()
    n = np.array(normal, float)
    for signed in (n, -n):
        resting, loaded = pillar.blocks(signed, shape)
        top = sum(_area(polygon) for polygon in loaded["top"])
        bottom = sum(_area(polygon) for polygon in resting["bottom"])
        assert top > sum(_area(polygon) for polygon in resting["top"])
        assert bottom > sum(_area(polygon) for polygon in loaded["bottom"])
        assert pillar.volume(resting) + pillar.volume(loaded) == pytest.approx(pillar.prism_volume(shape))


def _area(polygon) -> float:
    edges = np.cross(polygon, np.roll(polygon, -1, axis=0))
    return 0.5 * float(np.linalg.norm(edges.sum(axis=0)))


def test_slip_displacement():
    b = np.array([-0.6, 0.0, -0.8])                 # slip direction of the loaded block, compression
    assert np.allclose(pillar.slip_displacement(b, 0.5), [-0.3, 0, -0.4])
    # the pillar becomes shorter in compression and longer in tension, for every slip system
    for sense, shortening in (("compression", True), ("tension", False)):
        for r in analyse("fcc", Loading((1, 2, 3), sense=sense)).results:
            dz = pillar.slip_displacement(r.b, 0.5) @ load_axis(Lattice(CUBIC), Loading((1, 2, 3)))
            assert (dz <= 1e-12) if shortening else (dz >= -1e-12)
    block = {"top": [np.zeros((3, 3))]}
    assert np.allclose(pillar.translate(block, [1, 2, 3])["top"][0], [[1, 2, 3]] * 3)


# ------------------------------------------------------------------ orientation map
def test_schmid_map_matches_analysis():
    analysis = analyse("fcc", Loading((0, 0, 1)))
    x, y, values = orientation_map.schmid_map(analysis, pixels=41)
    centre = values[20, 20]
    assert centre == pytest.approx(1 / np.sqrt(6))            # [001] in the centre
    assert np.isnan(values[0, 0])                             # outside the primitive circle
    assert np.nanmax(values) <= 0.5 + 1e-12
    assert np.nanmin(values) >= np.sqrt(2 / 3) / 3 - 1e-9     # fcc minimum is at <111>
    # one pixel compared with a direct calculation
    rotation = orientation_map.standard_frame(analysis.lattice)
    axis = rotation.T @ stereo.inverse_project([x[30], y[12]])
    direct = max(abs((r.n @ axis) * (r.b @ axis)) for r in analysis.results)
    assert values[12, 30] == pytest.approx(direct)


def test_snap_to_indices():
    cubic = Lattice(CUBIC)
    assert orientation_map.snap_to_indices(cubic, [0.01, 1.0, 2.0], max_index=3) == (0, 1, 2)
    assert orientation_map.snap_to_indices(cubic, [2.0, 2.0, 2.0]) == (1, 1, 1)
    hexagonal = Lattice(HEXAGONAL, 1.624)
    target = hexagonal.direction_vector(mb_direction_to_miller((2, -1, -1, 3)))
    assert orientation_map.snap_to_indices(hexagonal, target, DIRECTION, 4) == \
        mb_direction_to_miller((2, -1, -1, 3))
    normal = hexagonal.plane_normal((1, 0, 2))
    assert orientation_map.snap_to_indices(hexagonal, normal, PLANE_NORMAL, 4) == (1, 0, 2)


def test_fundamental_zone_corners():
    assert orientation_map.fundamental_zone(Lattice(CUBIC)) == [(0, 0, 1), (0, 1, 1), (-1, 1, 1)]
    hexagonal = Lattice(HEXAGONAL, 1.6)
    corners = [hexagonal.direction_vector(c) for c in orientation_map.fundamental_zone(hexagonal)]
    assert np.isclose(np.degrees(np.arccos(corners[1] @ corners[2])), 30)


# ------------------------------------------------------------------ inverse pole figure
def test_triangle_frame():
    cubic = Lattice(CUBIC)
    assert np.allclose(inverse_pole_figure.triangle_frame(cubic), orientation_map.standard_frame(cubic))
    hexagonal = Lattice(HEXAGONAL, 1.624)
    rotation = inverse_pole_figure.triangle_frame(hexagonal)
    assert np.allclose(rotation, np.eye(3))                   # c in the centre, a1 along +X
    for lattice in (cubic, hexagonal):
        corners = inverse_pole_figure.triangle_corners(lattice) @ \
            inverse_pole_figure.triangle_frame(lattice).T
        points = stereo.project(corners)
        assert np.allclose(points[0], 0) and points[1, 0] > 0 and np.isclose(points[1, 1], 0)
        assert points[2, 1] > 0


@pytest.mark.parametrize("indices, reduced", [
    ((0, 1, 2), (0, 1, 2)),            # already inside (on the [001]-[011] edge)
    ((1, 0, 0), (0, 0, 1)),            # corners
    ((1, 1, 0), (0, 1, 1)),
    ((1, 1, 1), (-1, 1, 1)),
    ((1, 2, 3), (-1, 2, 3)),           # interior
    ((3, -1, -2), (-1, 2, 3)),
    ((2, 2, 4), (-2, 2, 4)),           # a common factor is kept
])
def test_cubic_axis_is_reduced_into_the_standard_triangle(indices, reduced):
    lattice = Lattice(CUBIC)
    assert inverse_pole_figure.reduce_loading(lattice, Loading(indices)).indices == reduced
    assert inverse_pole_figure.depth(lattice, np.array(reduced, dtype=float)) >= -1e-12


def test_cubic_triangle_rule():
    """w >= v >= -u >= 0: the absolute values of the indices in ascending order, the first one negative."""
    lattice = Lattice(CUBIC)
    rng = np.random.default_rng(3)
    for indices in rng.integers(-9, 10, size=(60, 3)):
        if not indices.any():
            continue
        low, middle, high = sorted(abs(int(i)) for i in indices)
        reduced = inverse_pole_figure.reduce_loading(lattice, Loading(tuple(int(i) for i in indices)))
        assert reduced.indices == (-low, middle, high)


@pytest.mark.parametrize("indices, kind, reduced", [
    ((1, 0, 1), DIRECTION, (1, 0, 1)),             # [2 -1 -1 3], on the [0001]-[2-1-10] edge
    ((0, 1, 0), DIRECTION, (1, 0, 0)),             # [-1 2 -1 0] -> [2 -1 -1 0]
    ((1, 1, 0), DIRECTION, (1, 0, 0)),             # [1 1 -2 0] -> [2 -1 -1 0]
    ((1, 2, 0), DIRECTION, (2, 1, 0)),             # [0 1 -1 0] -> [1 0 -1 0]
    ((0, 0, -1), DIRECTION, (0, 0, 1)),
    ((1, 0, 2), PLANE_NORMAL, (1, 0, 2)),          # normal of (1 0 -1 2), on the [0001]-[10-10] edge
    ((0, 1, 2), PLANE_NORMAL, (1, 0, 2)),          # (0 1 -1 2) -> (1 0 -1 2)
    ((1, 1, 0), PLANE_NORMAL, (2, -1, 0)),         # (1 1 -2 0) -> (2 -1 -1 0)
])
def test_hexagonal_axis_is_reduced_into_the_standard_triangle(indices, kind, reduced):
    lattice = Lattice(HEXAGONAL, 1.624)
    loading = inverse_pole_figure.reduce_loading(lattice, Loading(indices, kind))
    assert loading.indices == reduced and loading.kind == kind
    assert inverse_pole_figure.depth(lattice, load_axis(lattice, loading)) >= -1e-12


@pytest.mark.parametrize("lattice", [Lattice(CUBIC), Lattice(HEXAGONAL, 1.856)])
def test_all_equivalent_directions_share_one_point_of_the_triangle(lattice):
    rng = np.random.default_rng(7)
    operators = symmetry.point_group(lattice)
    for vector in rng.normal(size=(25, 3)):
        vector = vector / np.linalg.norm(vector)
        reduced = inverse_pole_figure.reduce_vector(lattice, vector)
        assert inverse_pole_figure.depth(lattice, reduced) >= 0          # inside the triangle
        assert any(np.allclose(operator @ vector, reduced) for operator in operators)
        point = inverse_pole_figure.triangle_point(lattice, vector)
        assert np.allclose(stereo.inverse_project(point),
                           inverse_pole_figure.triangle_frame(lattice) @ reduced)
        for operator in operators:                                       # includes -vector
            assert np.allclose(inverse_pole_figure.triangle_point(lattice, operator @ vector), point)
    # exactly one image of a general direction lies inside the triangle
    inside = [inverse_pole_figure.depth(lattice, operator @ vector) > 0 for operator in operators]
    assert sum(inside) == 1


def test_tension_and_compression_are_the_same_point_of_the_inverse_pole_figure():
    for structure, indices, c_over_a in (("fcc", (1, 2, 3), 1.0), ("hcp", (3, 1, 2), 1.624)):
        points = []
        for sense in ("tension", "compression"):
            analysis = analyse(structure, Loading(indices, sense=sense), c_over_a=c_over_a)
            points.append(inverse_pole_figure.triangle_point(analysis.lattice, analysis.force))
            points.append(inverse_pole_figure.triangle_point(analysis.lattice, analysis.axis))
        assert np.allclose(points, points[0])
    # the Schmid factors of the reduced axis are those of the entered one
    lattice = Lattice(CUBIC)
    entered = Loading((3, -1, -2))
    reduced = inverse_pole_figure.reduce_loading(lattice, entered)
    assert sorted(round(r.m, 12) for r in analyse("fcc", entered).results) == \
        sorted(round(r.m, 12) for r in analyse("fcc", reduced).results)


# ------------------------------------------------------------------ export
@pytest.mark.parametrize("delimiter, decimal", [("\t", "."), (";", ","), (",", ".")])
def test_export_round_trip(delimiter, decimal):
    analysis = analyse("fcc", Loading((0, 1, 2)))
    text = export.to_text(analysis, delimiter, decimal)
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    meta = [r for r in rows if r[0].startswith("#")]
    body = [r for r in rows if not r[0].startswith("#")]
    assert any("Loading axis" in r[0] and "[0 1 2]" in r[0] for r in meta)
    assert any("Loading sense: tension" in r[0] for r in meta)
    assert any("Force" in r[0] and "[0 1 2]" in r[0] for r in meta)
    assert tuple(body[0]) == export.HEADERS
    assert len(body) == 13
    first = body[1]
    # tension: plane normal and slip direction in the hemisphere of the force [0 1 2] ...
    assert first[0] == "1" and first[2] == "(1 1 1)" and first[3] == "[-1 0 1]"
    # ... compression: in the hemisphere of the force [0 -1 -2]
    pushed = export.to_text(analyse("fcc", Loading((0, 1, 2), sense="compression")), delimiter, decimal)
    pushed = list(csv.reader(io.StringIO(pushed), delimiter=delimiter))
    assert any("Force" in r[0] and "[0 -1 -2]" in r[0] for r in pushed)
    assert pushed[len(meta) + 1][2:4] == ["(-1 -1 -1)", "[1 0 -1]"]
    assert float(first[8].replace(decimal, ".")) == pytest.approx(0.4899)
    assert float(first[4].replace(decimal, ".")) == pytest.approx(39.23)
    assert first[11] == "yes" and body[3][11] == ""
    assert export.to_text(analysis, metadata=False).startswith("Rank\t")


def test_export_hexagonal_uses_four_indices():
    analysis = analyse("hcp", Loading((0, 0, 1)), c_over_a=1.624)
    text = export.to_text(analysis)
    assert "c/a: 1.624" in text
    assert "(1 1 -2 2)" in text and "inf" in text
