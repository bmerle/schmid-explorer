# SPDX-License-Identifier: GPL-3.0-or-later
"""Schmid factors of the slip systems of a single crystal under uniaxial load.

Schmid's law
------------
A uniaxial stress sigma along the unit vector l resolves on the slip system
(plane normal n, slip direction b) into the shear stress

    tau = m * sigma,        m = cos(theta) * cos(lambda) = (n.l) * (b.l)

with theta the angle between l and n, lambda the angle between l and b.

Vectors and sign convention
---------------------------
l : loading axis = outward normal of the top face of the sample (the indices entered
    by the user). It belongs to the sample and does not depend on the loading sense.
f : direction of the force acting on the top face: f = +l in tension (the force pulls
    the top face outwards), f = -l in compression (it pushes into the sample).
    "Compression along [0 1 2]" is a force along [0 -1 -2]. f is the z axis of the
    sample frame and the centre of the stereographic projection (see `stereo`).
n : glide-plane normal. (h k l) and (-h -k -l) are the same plane; of its two normals
    the one in the hemisphere of the force is used (n.f >= 0).
b : slip direction = direction in which the part of the sample carrying the loaded top
    face is displaced relative to the rest. This part follows the force (b.f >= 0),
    which is the sense in which the system is driven.

Everything is thus referred to the force: theta = angle(f, n) and lambda = angle(f, b)
lie between 0 and 90 degrees, and m = cos(theta) cos(lambda) = (n.f)(b.f), with
0 <= m <= 0.5, gives the magnitude of the resolved shear stress, tau = m |sigma|.

Reversing the load reverses f and with it both n and b: the glide systems, their
angles and their Schmid factors are the same in tension and in compression, the
indices of every plane and of every slip direction change their sign, e.g. fcc with
l = [0 1 2]: (1 1 1)[-1 0 1] in tension, (-1 -1 -1)[1 0 -1] in compression.

Activation
----------
A slip system starts to glide when tau reaches its critical resolved shear stress
tau_CRSS, i.e. at the applied stress  sigma_y = tau_CRSS / m.  With equal tau_CRSS for
all systems the one with the highest m is activated first; with family-specific
tau_CRSS the one with the lowest sigma_y.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import acos, degrees, inf

import numpy as np

from .lattice import Lattice, canonical
from .slip_systems import STRUCTURES, CrystalStructure, SlipSystem, slip_systems

COMPRESSION = "compression"
TENSION = "tension"
DIRECTION = "direction"        # load axis given as crystal direction [uvw]
PLANE_NORMAL = "plane_normal"  # load axis given as normal of the plane (hkl)

_ZERO = 1e-12


@dataclass(frozen=True)
class Loading:
    """Loading axis in crystal coordinates (three Miller indices) and loading sense."""

    indices: tuple
    kind: str = DIRECTION
    sense: str = TENSION

    def __post_init__(self):
        if not any(int(i) != 0 for i in self.indices):
            raise ValueError("the loading axis must not be the zero vector")
        if self.kind not in (DIRECTION, PLANE_NORMAL):
            raise ValueError(f"unknown kind {self.kind!r}")
        if self.sense not in (COMPRESSION, TENSION):
            raise ValueError(f"unknown loading sense {self.sense!r}")


def load_axis(lattice: Lattice, loading: Loading) -> np.ndarray:
    """Unit vector l of the loading axis (outward normal of the top face), crystal Cartesian frame."""
    if loading.kind == DIRECTION:
        return lattice.direction_vector(loading.indices)
    return lattice.plane_normal(loading.indices)


def load_axis_text(lattice: Lattice, loading: Loading) -> str:
    if loading.kind == DIRECTION:
        return lattice.direction_text(loading.indices)
    return "normal of " + lattice.plane_text(loading.indices)


def load_axis_tex(lattice: Lattice, loading: Loading, symbol: str = "") -> str:
    """Indices of the loading axis; with a symbol e.g. 'z || [012]' or 'z perp (0001)'."""
    if loading.kind == DIRECTION:
        relation, indices = r"$\parallel$ ", lattice.direction_tex(loading.indices)
    else:
        relation, indices = r"$\perp$", lattice.plane_tex(loading.indices)
    if symbol:
        return f"${symbol}$ " + relation + indices
    return indices if loading.kind == DIRECTION else relation + indices


def force_sign(sense: str) -> int:
    """+1 in tension, -1 in compression: the force on the top face is  f = force_sign * l."""
    return 1 if sense == TENSION else -1


def force_loading(loading: Loading) -> Loading:
    """The loading with its indices signed along the force acting on the top face.

    [uvw] in tension (the force pulls along the outward normal of the top face) and
    [-u -v -w] in compression (the force pushes into the sample).
    """
    sign = force_sign(loading.sense)
    return Loading(tuple(sign * int(i) for i in loading.indices), loading.kind, loading.sense)


def force_direction(lattice: Lattice, loading: Loading) -> np.ndarray:
    """Unit vector f of the force acting on the top face, crystal Cartesian frame."""
    return force_sign(loading.sense) * load_axis(lattice, loading)


def force_text(lattice: Lattice, loading: Loading) -> str:
    return load_axis_text(lattice, force_loading(loading))


def force_tex(lattice: Lattice, loading: Loading, symbol: str = "") -> str:
    return load_axis_tex(lattice, force_loading(loading), symbol)


def schmid_factor(n, b, l) -> float:
    """(n.l)(b.l) for unit vectors n (plane normal), b (slip direction), l (loading axis).

    The product does not change when l is reversed. It is positive if n and b point
    into the same hemisphere about l, as they do in the results of `analyse`.
    """
    return float(np.dot(n, l) * np.dot(b, l))


@dataclass(frozen=True, eq=False)
class SystemResult:
    """Schmid analysis of one slip system."""

    rank: int
    system: SlipSystem
    plane: tuple          # three Miller indices, signed so that n.f >= 0
    direction: tuple      # three Miller indices, signed so that b.f >= 0
    n: np.ndarray         # unit plane normal, crystal Cartesian frame
    b: np.ndarray         # unit slip direction of the part carrying the top face, crystal Cartesian frame
    cos_theta: float      # n.f
    cos_lambda: float     # b.f
    m: float
    crss: float
    yield_stress: float   # crss / m (inf for m = 0)
    primary: bool         # belongs to the systems that are activated first

    @property
    def theta_deg(self) -> float:
        return degrees(acos(min(1.0, max(-1.0, self.cos_theta))))

    @property
    def lambda_deg(self) -> float:
        return degrees(acos(min(1.0, max(-1.0, self.cos_lambda))))

    @property
    def plane_key(self) -> tuple:
        return self.system.plane

    @property
    def direction_key(self) -> tuple:
        return self.system.direction


@dataclass(eq=False)
class Analysis:
    """Complete result for one crystal, loading axis and set of slip families."""

    structure: CrystalStructure
    lattice: Lattice
    loading: Loading
    axis: np.ndarray                 # unit loading axis l, crystal Cartesian frame
    family_keys: tuple
    crss: dict                       # family key -> critical resolved shear stress
    use_crss: bool                   # rank by yield stress instead of Schmid factor
    results: list = field(default_factory=list)   # sorted, most favourable first

    @property
    def force(self) -> np.ndarray:
        """Unit vector f of the force on the top face: +axis in tension, -axis in compression."""
        return force_sign(self.loading.sense) * self.axis

    @property
    def primary(self) -> list:
        return [r for r in self.results if r.primary]

    def plane_keys(self) -> list:
        """Glide planes in order of their most favourable slip system."""
        keys = []
        for result in self.results:
            if result.plane_key not in keys:
                keys.append(result.plane_key)
        return keys

    def on_plane(self, plane_key) -> list:
        """Results of all slip systems sharing one glide plane, best first."""
        return [r for r in self.results if r.plane_key == plane_key]

    def best_on_plane(self, plane_key) -> SystemResult:
        return max(self.on_plane(plane_key), key=lambda r: r.m)

    def find(self, plane_key, direction_key):
        for result in self.results:
            if result.plane_key == plane_key and result.direction_key == direction_key:
                return result
        return None

    def summary(self) -> str:
        """One-line statement on which systems are activated first."""
        primary = self.primary
        if not primary:
            return "No slip system carries a resolved shear stress (all m = 0)."
        count = len(primary)
        mode = "single slip" if count == 1 else "multiple slip"
        best = primary[0]
        text = (f"{count} slip system{'s' if count > 1 else ''} activated first "
                f"({mode}): m = {best.m:.4f}")
        if self.use_crss:
            text += f", yield stress = {best.yield_stress:.4g} (units of CRSS)"
        return text


def analyse(structure_key: str, loading: Loading, family_keys=None, c_over_a: float = 1.633,
            crss=None, use_crss: bool = False, tolerance: float = 1e-6) -> Analysis:
    """Schmid factors of all slip systems of the selected families, ranked.

    Parameters
    ----------
    structure_key : 'fcc', 'bcc' or 'hcp'
    loading       : loading axis (three Miller indices) and loading sense
    family_keys   : slip families to include (default: the structure's default set)
    c_over_a      : axial ratio, used for hcp only
    crss          : {family key: tau_CRSS}; families not listed get tau_CRSS = 1
    use_crss      : rank by yield stress tau_CRSS / m instead of by m
    tolerance     : systems within this tolerance of the best one count as tied
    """
    structure = STRUCTURES[structure_key]
    lattice = structure.lattice(c_over_a)
    if family_keys is None:
        family_keys = [f.key for f in structure.families if f.default_on]
    family_keys = tuple(f.key for f in structure.families if f.key in family_keys)
    crss = {key: float((crss or {}).get(key, 1.0)) for key in family_keys}
    axis = load_axis(lattice, loading)
    force = force_sign(loading.sense) * axis

    rows = []
    for key in family_keys:
        for system in slip_systems(lattice, structure.family(key)):
            rows.append(_evaluate(lattice, system, force, crss[key]))

    if use_crss:
        rows.sort(key=lambda r: (r["yield_stress"], -r["m"], r["system"].family.key,
                                 [-i for i in r["system"].plane],
                                 [-i for i in r["system"].direction]))
        best = min((r["yield_stress"] for r in rows), default=inf)
        for r in rows:
            r["primary"] = r["m"] > tolerance and r["yield_stress"] <= best * (1 + tolerance)
    else:
        rows.sort(key=lambda r: (-round(r["m"], 9), r["system"].family.key,
                                 [-i for i in r["system"].plane],
                                 [-i for i in r["system"].direction]))
        best = max((r["m"] for r in rows), default=0.0)
        for r in rows:
            r["primary"] = r["m"] > tolerance and r["m"] >= best - tolerance

    results = [SystemResult(rank=i + 1, **row) for i, row in enumerate(rows)]
    return Analysis(structure, lattice, loading, axis, family_keys, crss, use_crss, results)


def _evaluate(lattice: Lattice, system: SlipSystem, force: np.ndarray, crss: float) -> dict:
    """One slip system; `force` = unit vector f of the force on the top face."""
    plane, n = _towards(force, system.plane, lattice.plane_normal(system.plane))
    direction, b = _towards(force, system.direction, lattice.direction_vector(system.direction))
    cos_theta = _snap(np.dot(n, force))
    cos_lambda = _snap(np.dot(b, force))
    m = cos_theta * cos_lambda
    return dict(system=system, plane=plane, direction=direction, n=n, b=b,
                cos_theta=cos_theta, cos_lambda=cos_lambda, m=m, crss=crss,
                yield_stress=crss / m if m > _ZERO else inf)


def _towards(force, indices, vector):
    """Flip indices and vector so that the vector points into the hemisphere of the force."""
    if np.dot(vector, force) < -_ZERO:
        return tuple(-i for i in indices), -vector
    return tuple(indices), vector


def _snap(value) -> float:
    value = float(value)
    return 0.0 if abs(value) < _ZERO else value


__all__ = [
    "COMPRESSION", "TENSION", "DIRECTION", "PLANE_NORMAL", "Loading", "SystemResult",
    "Analysis", "analyse", "load_axis", "load_axis_text", "load_axis_tex",
    "force_sign", "force_loading", "force_direction", "force_text", "force_tex",
    "schmid_factor", "canonical",
]
