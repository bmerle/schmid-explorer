# SPDX-License-Identifier: GPL-3.0-or-later
"""Cross-check against the formulation used in pycotem/stereoproj (F. Mompiou).

pycotem is not imported (its module starts a GUI). The functions below re-state the
formulas of its Schmid calculation - general triclinic structure matrix, family
generation by index permutation, hexagonal directions entered as the u, v, w of
[uvtw] and converted with U = 2u + v, V = 2v + u, signed Schmid factor - which are
independent of the symmetry-operator approach of schmid_explorer.core.
pycotem lists +b and -b separately with signed m; the duplicates are merged here.
"""

from itertools import permutations

import numpy as np
import pytest

from schmid_explorer.core.lattice import canonical
from schmid_explorer.core.schmid import Loading, analyse, load_axis


def structure_matrices(a, b, c, alpha, beta, gamma):
    alpha, beta, gamma = np.radians([alpha, beta, gamma])
    V = a * b * c * np.sqrt(1 - np.cos(alpha) ** 2 - np.cos(beta) ** 2 - np.cos(gamma) ** 2
                            + 2 * np.cos(alpha) * np.cos(beta) * np.cos(gamma))
    D = np.array([
        [a, b * np.cos(gamma), c * np.cos(beta)],
        [0, b * np.sin(gamma), c * (np.cos(alpha) - np.cos(beta) * np.cos(gamma)) / np.sin(gamma)],
        [0, 0, V / (a * b * np.sin(gamma))],
    ])
    return D, np.linalg.inv(D).T


def family_cubic(p):
    members = set()
    for perm in permutations(p):
        for flip in (None, 0, 1, 2):
            v = list(perm)
            if flip is not None:
                v[flip] = -v[flip]
            members.add(tuple(v))
    return members


def family_hexagonal(p):
    p1, p2, p3 = p
    i = -p1 - p2
    first_two = [(p1, p2), (p2, p1), (i, p2), (p1, i), (p2, i), (i, p1)]
    return {(a, b, s * p3) for a, b in first_two for s in (1, -1)}


def reference_schmid(D, Dstar, plane_seed, direction_seed, axis, hexagonal):
    family = family_hexagonal if hexagonal else family_cubic
    table = {}
    for n in family(plane_seed):
        for b in family(direction_seed):
            b3 = (2 * b[0] + b[1], 2 * b[1] + b[0], b[2]) if hexagonal else b
            if abs(np.dot(n, b3)) > 1e-4:
                continue
            nc = Dstar @ np.array(n, float)
            bc = D @ np.array(b3, float)
            m = (nc @ axis / np.linalg.norm(nc)) * (bc @ axis / np.linalg.norm(bc))
            key = (canonical(n), canonical(b3))
            assert abs(table.setdefault(key, abs(m)) - abs(m)) < 1e-12
    return table


# plane seed, direction seed as typed into pycotem (hexagonal: u, v, w of [uvtw])
CASES = [
    ("fcc", 1.0, "fcc_111_110", (1, 1, 1), (1, 1, 0)),
    ("bcc", 1.0, "bcc_110_111", (1, 1, 0), (1, 1, 1)),
    ("bcc", 1.0, "bcc_112_111", (1, 1, 2), (1, 1, 1)),
    ("bcc", 1.0, "bcc_123_111", (1, 2, 3), (1, 1, 1)),
    ("hcp", 1.5925, "hcp_basal_a", (0, 0, 1), (2, -1, 0)),
    ("hcp", 1.5925, "hcp_prism_a", (1, 0, 0), (2, -1, 0)),
    ("hcp", 1.5925, "hcp_pyr1_a", (1, 0, 1), (2, -1, 0)),
    ("hcp", 1.5925, "hcp_pyr1_ca", (1, 0, 1), (1, 1, 3)),
    ("hcp", 1.5925, "hcp_pyr2_ca", (1, 1, 2), (1, 1, 3)),
]

AXES = [(0, 0, 1), (0, 1, 2), (1, 2, 3), (1, 1, 1), (-3, 5, 7), (2, 1, 0)]


@pytest.mark.parametrize("structure, c_over_a, family, plane_seed, direction_seed", CASES)
def test_against_pycotem_formulation(structure, c_over_a, family, plane_seed, direction_seed):
    hexagonal = structure == "hcp"
    if hexagonal:
        D, Dstar = structure_matrices(3.232, 3.232, 3.232 * c_over_a, 90, 90, 120)   # Zr
    else:
        D, Dstar = structure_matrices(4.0496, 4.0496, 4.0496, 90, 90, 90)            # Al
    for indices in AXES:
        loading = Loading(indices)
        analysis = analyse(structure, loading, [family], c_over_a=c_over_a)
        axis = D @ np.array(indices, float)
        axis = axis / np.linalg.norm(axis)
        assert np.allclose(axis, load_axis(analysis.lattice, loading))
        reference = reference_schmid(D, Dstar, plane_seed, direction_seed, axis, hexagonal)
        ours = {(r.plane_key, r.direction_key): r.m for r in analysis.results}
        assert set(ours) == set(reference)
        for key, m in reference.items():
            assert ours[key] == pytest.approx(m, abs=1e-12)
