# SPDX-License-Identifier: GPL-3.0-or-later
"""Catalogue of slip families for fcc, bcc and hcp crystals and their enumeration.

A slip system is one glide plane together with one glide direction (Burgers vector
direction) lying in that plane. A slip family, e.g. {111}<110>, is the set of all
symmetry-equivalent slip systems.

Enumeration: generate every member of the plane family and of the direction family
(:mod:`symmetry`) and keep the pairs for which the direction lies in the plane,

    h U + k V + l W = 0        (three-index Miller notation, exact integer test).
"""

from __future__ import annotations

from dataclasses import dataclass

from .lattice import (
    CUBIC,
    HEXAGONAL,
    Lattice,
    mb_direction_to_miller,
    mb_plane_to_miller,
)
from .symmetry import equivalent_directions, equivalent_planes


@dataclass(frozen=True)
class SlipFamily:
    key: str
    name: str                # e.g. "basal <a>"
    plane_seed: tuple        # one plane of the family, three Miller indices
    direction_seed: tuple    # one glide direction of the family, three Miller indices
    label: str               # plain text, e.g. "{111}<110>"
    label_tex: str           # mathtext
    burgers: str             # Burgers vector, plain text, e.g. "a/2 <110>"
    default_on: bool = True


@dataclass(frozen=True)
class CrystalStructure:
    key: str
    name: str
    lattice_system: str
    families: tuple

    def family(self, key: str) -> SlipFamily:
        for family in self.families:
            if family.key == key:
                return family
        raise KeyError(key)

    def lattice(self, c_over_a: float = 1.0) -> Lattice:
        if self.lattice_system == CUBIC:
            return Lattice(CUBIC)
        return Lattice(HEXAGONAL, c_over_a)


@dataclass(frozen=True)
class SlipSystem:
    family: SlipFamily
    plane: tuple       # canonical three-index Miller indices
    direction: tuple   # canonical three-index Miller indices


def slip_systems(lattice: Lattice, family: SlipFamily) -> list:
    """All slip systems of one family (each plane / slip-line pair once)."""
    systems = []
    for plane in equivalent_planes(lattice, family.plane_seed):
        for direction in equivalent_directions(lattice, family.direction_seed):
            if sum(p * d for p, d in zip(plane, direction)) == 0:
                systems.append(SlipSystem(family, plane, direction))
    return systems


# --------------------------------------------------------------------------- catalogue
def _hex(plane_hkil, direction_uvtw):
    return mb_plane_to_miller(plane_hkil), mb_direction_to_miller(direction_uvtw)


_A_TEX = r"$\langle 11\bar{2}0\rangle$"
_CA_TEX = r"$\langle 11\bar{2}3\rangle$"

FCC = CrystalStructure(
    key="fcc",
    name="fcc (face-centred cubic)",
    lattice_system=CUBIC,
    families=(
        SlipFamily("fcc_111_110", "octahedral", (1, 1, 1), (1, -1, 0),
                   "{111}<110>", r"$\{111\}\langle 110\rangle$", "a/2 <110>"),
    ),
)

BCC = CrystalStructure(
    key="bcc",
    name="bcc (body-centred cubic)",
    lattice_system=CUBIC,
    families=(
        SlipFamily("bcc_110_111", "{110} slip", (1, 1, 0), (1, -1, 1),
                   "{110}<111>", r"$\{110\}\langle 111\rangle$", "a/2 <111>"),
        SlipFamily("bcc_112_111", "{112} slip", (1, 1, 2), (1, 1, -1),
                   "{112}<111>", r"$\{112\}\langle 111\rangle$", "a/2 <111>",
                   default_on=False),
        SlipFamily("bcc_123_111", "{123} slip", (1, 2, 3), (1, 1, -1),
                   "{123}<111>", r"$\{123\}\langle 111\rangle$", "a/2 <111>",
                   default_on=False),
    ),
)

HCP = CrystalStructure(
    key="hcp",
    name="hcp (hexagonal close-packed)",
    lattice_system=HEXAGONAL,
    families=(
        SlipFamily("hcp_basal_a", "basal <a>",
                   *_hex((0, 0, 0, 1), (2, -1, -1, 0)),
                   "{0001}<11-20>", r"$\{0001\}$" + _A_TEX, "a/3 <11-20>"),
        SlipFamily("hcp_prism_a", "prismatic <a>",
                   *_hex((1, 0, -1, 0), (1, -2, 1, 0)),
                   "{10-10}<11-20>", r"$\{10\bar{1}0\}$" + _A_TEX, "a/3 <11-20>"),
        SlipFamily("hcp_pyr1_a", "pyramidal I <a>",
                   *_hex((1, 0, -1, 1), (1, -2, 1, 0)),
                   "{10-11}<11-20>", r"$\{10\bar{1}1\}$" + _A_TEX, "a/3 <11-20>"),
        SlipFamily("hcp_pyr1_ca", "pyramidal I <c+a>",
                   *_hex((1, 0, -1, 1), (-1, -1, 2, 3)),
                   "{10-11}<11-23>", r"$\{10\bar{1}1\}$" + _CA_TEX, "1/3 <11-23>"),
        SlipFamily("hcp_pyr2_ca", "pyramidal II <c+a>",
                   *_hex((1, 1, -2, 2), (-1, -1, 2, 3)),
                   "{11-22}<11-23>", r"$\{11\bar{2}2\}$" + _CA_TEX, "1/3 <11-23>"),
    ),
)

STRUCTURES = {structure.key: structure for structure in (FCC, BCC, HCP)}

# c/a ratios at room temperature (Hull & Bacon, Introduction to Dislocations, 5th ed.)
HCP_C_OVER_A = {
    "ideal (sphere packing)": 1.633,
    "Mg": 1.624,
    "Ti": 1.587,
    "Zr": 1.593,
    "Zn": 1.856,
    "Be": 1.568,
    "Co": 1.623,
    "Cd": 1.886,
}
