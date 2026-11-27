# SPDX-License-Identifier: GPL-3.0-or-later
"""Schmid factors: reference values from the lecture notebooks and physical checks."""

from math import inf

import numpy as np
import pytest

from schmid_explorer.core.lattice import canonical, mb_direction_to_miller
from schmid_explorer.core.schmid import (
    COMPRESSION, PLANE_NORMAL, TENSION, Loading, analyse, force_direction, force_loading,
    force_sign, force_tex, force_text, load_axis, load_axis_tex, schmid_factor,
)

# Output of data/fcc_schmid.ipynb for the loading axis [0 1 2]:
# plane, direction, phi (deg), lambda (deg), Schmid factor
FCC_012 = [
    ((1, 1, 1), (-1, 0, 1), 39.23, 50.77, 0.4899),
    ((-1, 1, 1), (1, 0, 1), 39.23, 50.77, 0.4899),
    ((1, 1, -1), (0, -1, -1), 104.96, 161.57, 0.2449),
    ((1, -1, 1), (0, 1, 1), 75.04, 18.43, 0.2449),
    ((1, 1, 1), (-1, 1, 0), 39.23, 71.57, 0.2449),
    ((1, 1, 1), (0, -1, 1), 39.23, 71.57, 0.2449),
    ((-1, 1, 1), (1, 1, 0), 39.23, 71.57, 0.2449),
    ((-1, 1, 1), (0, -1, 1), 39.23, 71.57, 0.2449),
    ((1, 1, -1), (-1, 0, -1), 104.96, 129.23, 0.1633),
    ((1, -1, 1), (-1, 0, 1), 75.04, 50.77, 0.1633),
    ((1, 1, -1), (1, -1, 0), 104.96, 108.43, 0.0816),
    ((1, -1, 1), (1, 1, 0), 75.04, 71.57, 0.0816),
]

# Output of data/bcc_schmid.ipynb for the loading axis [0 1 2]
BCC_012 = [
    ((1, 0, 1), (-1, 1, 1), 50.77, 39.23, 0.4899),
    ((1, 0, -1), (-1, -1, -1), 129.23, 140.77, 0.4899),
    ((0, 1, 1), (-1, -1, 1), 18.43, 75.04, 0.2449),
    ((0, 1, 1), (1, -1, 1), 18.43, 75.04, 0.2449),
    ((1, 1, 0), (-1, 1, 1), 71.57, 39.23, 0.2449),
    ((1, -1, 0), (-1, -1, -1), 108.43, 140.77, 0.2449),
    ((0, 1, -1), (-1, -1, -1), 108.43, 140.77, 0.2449),
    ((0, 1, -1), (1, -1, -1), 108.43, 140.77, 0.2449),
    ((1, 0, 1), (-1, -1, 1), 50.77, 75.04, 0.1633),
    ((1, 0, -1), (-1, 1, -1), 129.23, 104.96, 0.1633),
    ((1, 1, 0), (1, -1, 1), 71.57, 75.04, 0.0816),
    ((1, -1, 0), (1, 1, -1), 108.43, 104.96, 0.0816),
]


def _acute(angle):
    return min(angle, 180.0 - angle)


@pytest.mark.parametrize("structure, families, reference", [
    ("fcc", ["fcc_111_110"], FCC_012),
    ("bcc", ["bcc_110_111"], BCC_012),
])
def test_notebook_reference_values(structure, families, reference):
    analysis = analyse(structure, Loading((0, 1, 2)), families)
    assert len(analysis.results) == len(reference) == 12
    for plane, direction, phi, lam, m in reference:
        result = analysis.find(canonical(plane), canonical(direction))
        assert result is not None
        assert result.m == pytest.approx(m, abs=5e-5)
        assert result.theta_deg == pytest.approx(_acute(phi), abs=5e-3)
        assert result.lambda_deg == pytest.approx(_acute(lam), abs=5e-3)
    # ranked list: highest Schmid factor first
    ms = [round(r.m, 9) for r in analysis.results]
    assert ms == sorted(ms, reverse=True)
    assert [r.rank for r in analysis.results] == list(range(1, 13))


@pytest.mark.parametrize("sense", [COMPRESSION, TENSION])
def test_sign_convention(sense):
    """n and b (slip of the part carrying the top face) both point into the hemisphere of the force."""
    analysis = analyse("bcc", Loading((1, 2, 3), sense=sense),
                       ["bcc_110_111", "bcc_112_111", "bcc_123_111"])
    assert len(analysis.results) == 48
    sign = force_sign(sense)
    assert np.allclose(analysis.force, sign * analysis.axis)
    for r in analysis.results:
        assert r.n @ analysis.force >= -1e-12 and r.b @ analysis.force >= -1e-12
        assert r.cos_theta == pytest.approx(r.n @ analysis.force)
        assert r.cos_lambda == pytest.approx(r.b @ analysis.force)
        # the product does not depend on the sign of the axis it is referred to
        assert schmid_factor(r.n, r.b, analysis.force) == pytest.approx(r.m)
        assert schmid_factor(r.n, r.b, analysis.axis) == pytest.approx(r.m)
        assert 0 <= r.theta_deg <= 90 and 0 <= r.lambda_deg <= 90
        assert 0 <= r.m <= 0.5 + 1e-12
        assert abs(r.n @ r.b) < 1e-12
        # the signed indices describe the same plane / slip line as the keys
        assert canonical(r.plane) == r.plane_key and canonical(r.direction) == r.direction_key
        assert np.allclose(analysis.lattice.plane_normal(r.plane), r.n)
        assert np.allclose(analysis.lattice.direction_vector(r.direction), r.b)


@pytest.mark.parametrize("axis, count, m", [
    ((0, 0, 1), 8, 1 / np.sqrt(6)),
    ((1, 1, 1), 6, np.sqrt(2 / 3) / 3),
    ((0, 1, 1), 4, 1 / np.sqrt(6)),
    ((1, 1, 2), 2, 0.4082),
    ((0, 1, 2), 2, 0.4899),
    ((1, 2, 3), 1, 0.4666),
    ((-1, 4, 9), 1, None),
])
def test_number_of_primary_systems_fcc(axis, count, m):
    """1 system inside the standard triangle, 2/4/6/8 on its borders and corners."""
    analysis = analyse("fcc", Loading(axis))
    assert len(analysis.primary) == count
    if m is not None:
        assert analysis.primary[0].m == pytest.approx(m, abs=5e-5)
    assert ("single slip" in analysis.summary()) == (count == 1)


@pytest.mark.parametrize("structure, axis, c_over_a", [
    ("fcc", (1, 2, 3), 1.633), ("fcc", (0, 0, 1), 1.633), ("bcc", (0, 1, 2), 1.633),
    ("hcp", (0, 0, 1), 1.624), ("hcp", (2, 1, 3), 1.587),
])
def test_loading_sense_reverses_every_normal_and_slip_direction(structure, axis, c_over_a):
    """Tension -> compression: same systems, angles and Schmid factors, every n and b reversed."""
    compression = analyse(structure, Loading(axis, sense=COMPRESSION), c_over_a=c_over_a)
    tension = analyse(structure, Loading(axis, sense=TENSION), c_over_a=c_over_a)
    assert len(compression.results) == len(tension.results) > 0
    assert np.allclose(compression.axis, tension.axis) and np.allclose(compression.force, -tension.force)
    for c, t in zip(compression.results, tension.results):
        assert (c.plane_key, c.direction_key) == (t.plane_key, t.direction_key)
        assert (c.m, c.theta_deg, c.lambda_deg, c.primary) == (t.m, t.theta_deg, t.lambda_deg, t.primary)
        if t.cos_theta > 0:                         # a normal perpendicular to the force keeps its sign
            assert c.plane == tuple(-i for i in t.plane) and np.allclose(c.n, -t.n)
        if t.cos_lambda > 0:
            assert c.direction == tuple(-i for i in t.direction) and np.allclose(c.b, -t.b)
        # the part carrying the top face moves outwards in tension and inwards in compression
        assert t.b @ tension.axis >= -1e-12 and c.b @ compression.axis <= 1e-12


def test_default_sense_is_tension():
    loading = Loading((0, 1, 2))
    assert loading.sense == TENSION
    best = analyse("fcc", loading).results[0]
    assert (best.plane, best.direction) == ((1, 1, 1), (-1, 0, 1))
    pushed = analyse("fcc", Loading((0, 1, 2), sense=COMPRESSION)).results[0]
    assert (pushed.plane, pushed.direction) == ((-1, -1, -1), (1, 0, -1))


def test_force_on_the_top_face():
    """The loading axis is the same in both senses, the force is reversed in compression."""
    lattice = analyse("fcc", Loading((0, 1, 2))).lattice
    compression, tension = Loading((0, 1, 2), sense=COMPRESSION), Loading((0, 1, 2), sense=TENSION)
    assert force_sign(COMPRESSION) == -1 and force_sign(TENSION) == 1
    assert np.allclose(load_axis(lattice, compression), load_axis(lattice, tension))
    assert np.allclose(force_direction(lattice, tension), load_axis(lattice, tension))
    assert np.allclose(force_direction(lattice, compression), -load_axis(lattice, compression))
    assert force_loading(compression).indices == (0, -1, -2)
    assert force_loading(tension).indices == (0, 1, 2)
    assert force_text(lattice, compression) == "[0 -1 -2]" and force_text(lattice, tension) == "[0 1 2]"
    assert load_axis_tex(lattice, compression) == load_axis_tex(lattice, tension)
    assert force_tex(lattice, tension, "F") == load_axis_tex(lattice, tension, "F")
    assert force_tex(lattice, compression, "F") != load_axis_tex(lattice, compression, "F")
    hexagonal = analyse("hcp", Loading((0, 0, 1))).lattice
    basal = Loading((0, 0, 1), kind=PLANE_NORMAL, sense=COMPRESSION)
    assert np.allclose(force_direction(hexagonal, basal), [0, 0, -1])


def test_hcp_c_axis_loading():
    """Load along [0001]: no shear stress on <a> slip, only <c+a> slip can act."""
    analysis = analyse("hcp", Loading((0, 0, 1)), c_over_a=1.624)
    assert len(analysis.results) == 30
    for r in analysis.results:
        if r.system.family.key in ("hcp_basal_a", "hcp_prism_a", "hcp_pyr1_a"):
            assert r.m == 0
        else:
            assert r.m > 0.3
    assert {r.system.family.key for r in analysis.primary} == {"hcp_pyr2_ca"}
    assert len(analysis.primary) == 6
    # analytic value for pyramidal II <c+a>: cos(theta) cos(lambda) with gamma = c/a
    g = 1.624
    expected = (1 / np.sqrt(1 + g * g)) * (g / np.sqrt(1 + g * g))
    assert analysis.primary[0].m == pytest.approx(expected)


def test_hcp_direction_versus_plane_normal():
    """In hcp [uvtw] is in general not normal to (uvtw) - the two inputs differ."""
    lattice = analyse("hcp", Loading((0, 0, 1)), c_over_a=1.624).lattice
    as_direction = load_axis(lattice, Loading(mb_direction_to_miller((1, 0, -1, 1))))
    as_normal = load_axis(lattice, Loading((1, 0, 1), kind=PLANE_NORMAL))
    assert not np.allclose(as_direction, as_normal)
    # within the basal plane and along c they coincide
    assert np.allclose(load_axis(lattice, Loading(mb_direction_to_miller((1, 0, -1, 0)))),
                       load_axis(lattice, Loading((1, 0, 0), kind=PLANE_NORMAL)))


def test_crss_ranking():
    """With a high CRSS for <c+a> slip a slightly inclined crystal yields by basal slip."""
    loading = Loading(mb_direction_to_miller((1, 0, -1, 4)))
    schmid = analyse("hcp", loading, c_over_a=1.624)
    assert schmid.primary[0].system.family.key.endswith("_ca")
    crss = {"hcp_basal_a": 1, "hcp_prism_a": 40, "hcp_pyr1_a": 40,
            "hcp_pyr1_ca": 80, "hcp_pyr2_ca": 80}
    ranked = analyse("hcp", loading, c_over_a=1.624, crss=crss, use_crss=True)
    assert ranked.primary[0].system.family.key == "hcp_basal_a"
    stresses = [r.yield_stress for r in ranked.results]
    assert stresses == sorted(stresses)
    for r in ranked.results:
        assert r.yield_stress == (pytest.approx(r.crss / r.m) if r.m > 0 else inf)


def test_no_active_system():
    analysis = analyse("hcp", Loading((0, 0, 1)), ["hcp_basal_a", "hcp_prism_a"])
    assert analysis.primary == []
    assert "No slip system" in analysis.summary()


def test_invalid_loading():
    with pytest.raises(ValueError):
        Loading((0, 0, 0))
