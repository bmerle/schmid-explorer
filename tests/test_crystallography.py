# SPDX-License-Identifier: GPL-3.0-or-later
"""Lattice, index conversions, symmetry families and slip-system enumeration."""

import numpy as np
import pytest

from schmid_explorer.core.lattice import (
    CUBIC, HEXAGONAL, Lattice, canonical, indices_tex, mb_direction_to_miller,
    mb_plane_to_miller, miller_to_mb_direction, miller_to_mb_plane, reduce_indices,
)
from schmid_explorer.core.slip_systems import BCC, FCC, HCP, slip_systems
from schmid_explorer.core.symmetry import (
    cubic_operators, equivalent_directions, equivalent_planes, hexagonal_operators,
)


def test_index_helpers():
    assert reduce_indices((2, -4, 6)) == (1, -2, 3)
    assert canonical((-2, 2, 0)) == (1, -1, 0)
    assert canonical((0, -1, 1)) == (0, 1, -1)
    assert indices_tex((1, -1, 0), "[]") == r"$[1\bar{1}0]$"


def test_miller_bravais_round_trip():
    assert mb_direction_to_miller((2, -1, -1, 0)) == (1, 0, 0)
    assert mb_direction_to_miller((-1, -1, 2, 3)) == (-1, -1, 1)
    assert miller_to_mb_direction((1, 0, 0)) == (2, -1, -1, 0)
    assert miller_to_mb_direction((0, 0, 1)) == (0, 0, 0, 1)
    assert miller_to_mb_direction((1, 1, 1)) == (1, 1, -2, 3)
    assert miller_to_mb_plane((1, 0, 1)) == (1, 0, -1, 1)
    assert mb_plane_to_miller((1, 1, -2, 2)) == (1, 1, 2)
    for uvw in [(1, 0, 0), (1, 1, 0), (2, 1, 3), (1, -1, 4)]:
        assert mb_direction_to_miller(miller_to_mb_direction(uvw)) == uvw
    with pytest.raises(ValueError):
        mb_direction_to_miller((1, 1, 1, 0))


def test_hexagonal_metric():
    lattice = Lattice(HEXAGONAL, 1.6)
    a1 = lattice.direct[:, 0]
    a2 = lattice.direct[:, 1]
    c = lattice.direct[:, 2]
    assert np.isclose(np.linalg.norm(a1), 1) and np.isclose(np.linalg.norm(a2), 1)
    assert np.isclose(np.degrees(np.arccos(a1 @ a2)), 120)
    assert np.isclose(np.linalg.norm(c), 1.6)
    # direction [0001] is normal to the basal plane; [10-10] is normal to (10-10)
    assert np.allclose(lattice.direction_vector((0, 0, 1)), lattice.plane_normal((0, 0, 1)))
    assert np.allclose(lattice.direction_vector(mb_direction_to_miller((1, 0, -1, 0))),
                       lattice.plane_normal((1, 0, 0)))
    # textbook angle between (0001) and (10-11): tan = (c/a) / cos(30 deg)
    angle = np.arccos(lattice.plane_normal((0, 0, 1)) @ lattice.plane_normal((1, 0, 1)))
    assert np.isclose(np.tan(angle), 1.6 / (np.sqrt(3) / 2))
    # real-valued indices invert the conversions
    assert np.allclose(lattice.direction_from_vector(lattice.direct @ [1, 2, 3]), [1, 2, 3])
    assert np.allclose(lattice.plane_from_vector(lattice.reciprocal @ [1, 2, 3]), [1, 2, 3])


def test_point_groups():
    for operators, order in ((cubic_operators(), 48), (hexagonal_operators(), 24)):
        assert len(operators) == order
        for op in operators:
            assert np.allclose(op @ op.T, np.eye(3))


@pytest.mark.parametrize("seed, planes, directions", [
    ((1, 0, 0), 3, 3), ((1, 1, 0), 6, 6), ((1, 1, 1), 4, 4), ((1, 1, 2), 12, 12),
    ((1, 2, 3), 24, 24),
])
def test_cubic_family_sizes(seed, planes, directions):
    lattice = Lattice(CUBIC)
    assert len(equivalent_planes(lattice, seed)) == planes
    assert len(equivalent_directions(lattice, seed)) == directions


def test_hexagonal_family_sizes():
    lattice = Lattice(HEXAGONAL, 1.624)
    plane = lambda hkil: len(equivalent_planes(lattice, mb_plane_to_miller(hkil)))
    direction = lambda uvtw: len(equivalent_directions(lattice, mb_direction_to_miller(uvtw)))
    assert plane((0, 0, 0, 1)) == 1
    assert plane((1, 0, -1, 0)) == 3
    assert plane((1, 0, -1, 1)) == 6
    assert plane((1, 1, -2, 2)) == 6
    assert direction((2, -1, -1, 0)) == 3
    assert direction((1, 1, -2, 3)) == 6
    assert direction((0, 0, 0, 1)) == 1


@pytest.mark.parametrize("structure, c_over_a, expected", [
    (FCC, 1.0, {"fcc_111_110": 12}),
    (BCC, 1.0, {"bcc_110_111": 12, "bcc_112_111": 12, "bcc_123_111": 24}),
    (HCP, 1.624, {"hcp_basal_a": 3, "hcp_prism_a": 3, "hcp_pyr1_a": 6,
                  "hcp_pyr1_ca": 12, "hcp_pyr2_ca": 6}),
    (HCP, 1.856, {"hcp_basal_a": 3, "hcp_prism_a": 3, "hcp_pyr1_a": 6,
                  "hcp_pyr1_ca": 12, "hcp_pyr2_ca": 6}),
])
def test_slip_system_counts_and_orthogonality(structure, c_over_a, expected):
    lattice = structure.lattice(c_over_a)
    assert {f.key for f in structure.families} == set(expected)
    for family in structure.families:
        systems = slip_systems(lattice, family)
        assert len(systems) == expected[family.key]
        assert len({(s.plane, s.direction) for s in systems}) == len(systems)
        for s in systems:
            # the slip direction lies in the slip plane (Cartesian check of the integer test)
            assert abs(lattice.plane_normal(s.plane) @ lattice.direction_vector(s.direction)) < 1e-12
