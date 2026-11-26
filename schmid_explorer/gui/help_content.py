# SPDX-License-Identifier: GPL-3.0-or-later
"""Text of the help window: the most important points of the documentation, topic by topic.

Text only - no formulas are evaluated here. The numbers and tables of the examples are
calculated with `core` when the help is opened, and the figures are drawn by `plotting`,
so that the help always shows what the program calculates.

Markup understood by the help window in addition to the HTML subset of Qt:
    <equation>mathtext</equation>          a displayed equation
    <figure name="..." width="..."/>       a figure of `FIGURES` (width in pixels)
"""

from __future__ import annotations

from dataclasses import dataclass

from matplotlib.figure import Figure

from .. import APP_NAME, AUTHOR, WEBSITE, __version__, third_party
from ..core import stereo
from ..core.lattice import mb_direction_to_miller
from ..core.schmid import COMPRESSION, Loading, analyse, force_sign, force_text
from ..core.slip_systems import HCP_C_OVER_A, STRUCTURES, slip_systems
from ..plotting.ipf_plot import draw_ipf
from ..plotting.pillar_plot import PillarOptions, draw_pillar, suggested_view
from ..plotting.stereo_plot import StereoOptions, draw_stereo
from ..plotting.style import Selection
from .text import pretty


@dataclass(frozen=True)
class Topic:
    title: str
    html: str


# --------------------------------------------------------------------------- figures
def _example():
    """The start state of the program: fcc pulled along [012], system with the highest Schmid factor."""
    analysis = analyse("fcc", Loading((0, 1, 2)))
    best = analysis.results[0]
    rotation, _ = stereo.sample_frame(analysis.lattice, analysis.axis, sign=force_sign(analysis.loading.sense))
    return analysis, rotation, Selection(plane=best.plane_key, direction=best.direction_key)


def _pillar_figure() -> Figure:
    analysis, rotation, selection = _example()
    fig = Figure(figsize=(4.2, 4.7))
    view = suggested_view(analysis, rotation, selection)
    draw_pillar(fig, analysis, rotation, selection, PillarOptions(view=view))
    return fig


def _stereo_figure() -> Figure:
    analysis, rotation, selection = _example()
    fig = Figure(figsize=(4.7, 4.7))
    draw_stereo(fig, analysis, rotation, selection, StereoOptions(circle_45=True))
    return fig


def _ipf_figure() -> Figure:
    fig = Figure(figsize=(3.2, 1.5))
    draw_ipf(fig, analyse("fcc", Loading((1, 2, 3))))
    return fig


FIGURES = {"pillar": _pillar_figure, "stereo": _stereo_figure, "ipf": _ipf_figure}


# --------------------------------------------------------------------------- helpers
def _table(header, rows) -> str:
    head = "".join(f"<th>{cell}</th>" for cell in header)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f'<table cellspacing="0" cellpadding="5"><tr>{head}</tr>{body}</table>'


def _list(items, numbered: bool = False) -> str:
    tag = "ol" if numbered else "ul"
    return f"<{tag}>" + "".join(f"<li>{item}</li>" for item in items) + f"</{tag}>"


def _system(analysis, result) -> str:
    lattice = analysis.lattice
    return pretty(lattice.plane_text(result.plane)) + pretty(lattice.direction_text(result.direction))


# --------------------------------------------------------------------------- topics
def topics() -> list:
    """All help topics, in the order of the list in the help window."""
    fcc012 = analyse("fcc", Loading((0, 1, 2)))
    fcc012_compression = analyse("fcc", Loading((0, 1, 2), sense=COMPRESSION))
    best = fcc012.results[0]
    best_compression = fcc012_compression.find(best.plane_key, best.direction_key)
    force_compression = pretty(force_text(fcc012_compression.lattice, fcc012_compression.loading))
    axis012 = pretty("[012]")
    return [
        Topic("Quick start", _quick_start(axis012, force_compression)),
        Topic("Schmid's law", _schmid_law(fcc012, best)),
        Topic("Indices and angles", _indices(fcc012, best)),
        Topic("Glide systems", _glide_systems()),
        Topic("Tension and compression", _sense(fcc012, best, fcc012_compression, best_compression,
                                                 force_compression)),
        Topic("Stereographic projection", _projection(axis012, force_compression)),
        Topic("Single and multiple slip", _multiplicity()),
        Topic("Inverse pole figure", _inverse_pole_figure()),
        Topic("Critical resolved shear stress", _crss()),
        Topic("The program window", _window()),
        Topic("Copying and exporting", _export()),
        Topic("Examples to try", _examples(fcc012, best)),
        Topic("Limits of the model", _limits()),
        Topic("References", _references()),
        Topic("Licence and acknowledgements", licence_html()),
    ]


def _quick_start(axis012, force_compression) -> str:
    return (
        f"<h2>{APP_NAME}</h2>"
        "<p>A small column cut out of one grain of a metal is a single crystal. When it is compressed or "
        "pulled it does not deform uniformly: it shears along a few crystallographic planes, and slip steps "
        "appear on its surface. Which planes and directions become active depends only on how the crystal "
        "lattice is oriented with respect to the loading axis. The rule is Schmid's law, and the quantity "
        "that decides is the Schmid factor <i>m</i>.</p>"
        "<p>The program lists all glide systems of an fcc, bcc or hcp crystal with their Schmid factors, "
        "shows the glide planes in a stereographic projection centred on the direction of the force and "
        "sketches the selected glide plane and slip direction in the pillar.</p>"
        "<h3>A first experiment</h3>"
        + _list([
            f"The program starts with an fcc crystal loaded in tension along {axis012}.",
            "Read the table at the bottom: all 12 glide systems are listed, the one with the highest Schmid "
            "factor first. Systems that are activated first are printed in bold.",
            "Look at the stereographic projection. Its centre is the direction of the force. Each coloured "
            "circle is the pole of a glide plane; its colour is the highest Schmid factor on that plane. "
            "Click one of the circles: the plane is drawn into the pillar, and its glide directions appear "
            "as squares.",
            "Click one of the squares (or a row of the table). The slip direction <b>b</b> is added to the "
            "pillar sketch together with the angles θ and λ.",
            "Move the <i>Slip step</i> slider below the pillar to see how the crystal shears on this system.",
            f"Switch from <i>Tension</i> to <i>Compression</i>: the force is reversed and now points along "
            f"{force_compression}, into the pillar. The Schmid factors stay; the projection is redrawn "
            "around the new force direction, and the indices of all planes and slip directions change sign.",
            "Change the indices of the loading axis, or choose <i>Pick on orientation map…</i>, and observe "
            "how the ranking changes. The star in the small inverse pole figure shows where the loading "
            "axis lies in the standard triangle of the crystal.",
        ], numbered=True)
        + "<p>The topics in the list on the left explain the theory, the conventions and the window.</p>")


def _schmid_law(fcc012, best) -> str:
    return (
        "<h2>Schmid's law</h2>"
        "<p>A pillar with the cross-section <i>A</i> is loaded by the force <i>F</i> along its axis. The "
        "applied normal stress is σ = <i>F</i> / <i>A</i>. Plastic deformation happens by dislocation glide: "
        "a dislocation moves on a glide plane (unit normal <b>n</b>) and shifts the crystal by its Burgers "
        "vector <b>b</b>, which lies in this plane. Only the shear stress that acts on this plane and in "
        "this direction drives it. Two projections give this resolved shear stress:</p>"
        + _list([
            "The glide plane is inclined. With θ the angle between the force and the plane normal <b>n</b>, "
            "the plane cuts the pillar in an ellipse of the area <i>A</i> / cos θ.",
            "Only the part of the force along the glide direction counts. With λ the angle between the force "
            "and <b>b</b>, this part is <i>F</i> cos λ.",
        ])
        + r"<equation>\tau = \frac{F\cos\lambda}{A/\cos\theta} = \sigma\,\cos\theta\,\cos\lambda = m\,\sigma,"
          r"\qquad m = \cos\theta\,\cos\lambda</equation>"
        "<p>The geometric factor <i>m</i> is the <b>Schmid factor</b>. Schmid's law states that a glide "
        "system starts to operate when its resolved shear stress reaches a critical value, the critical "
        "resolved shear stress τ<sub>CRSS</sub>, which is a property of the material and of the type of "
        "glide system. The crystal therefore yields at the applied stress</p>"
        r"<equation>\sigma_y = \frac{\tau_{\mathrm{CRSS}}}{m}</equation>"
        "<p>The larger the Schmid factor, the smaller the stress that is needed: among glide systems of the "
        "same type, <b>the system with the highest Schmid factor is activated first</b>.</p>"
        "<p>Because <b>b</b> lies in the glide plane, the two angles are not independent: θ + λ ≥ 90°. "
        "Hence</p>"
        r"<equation>m \leq \cos\theta\,\sin\theta = \frac{1}{2}\sin 2\theta \leq \frac{1}{2}</equation>"
        "<p>The Schmid factor never exceeds 0.5. The maximum is reached when the loading axis, the plane "
        "normal and the glide direction lie in one plane and θ = λ = 45°. It is zero when the loading axis "
        "lies in the glide plane (θ = 90°) or is perpendicular to the glide direction (λ = 90°).</p>"
        '<figure name="pillar" width="330"/>'
        f"<p><i>fcc pillar pulled along {pretty('[012]')}, glide system {_system(fcc012, best)}: "
        f"θ = {best.theta_deg:.1f}°, λ = {best.lambda_deg:.1f}°, m = {best.m:.4f}.</i></p>")


def _indices(fcc012, best) -> str:
    return (
        "<h2>From crystallographic indices to the angles</h2>"
        "<p>Three unit vectors are needed: the plane normal <b>n</b>, the slip direction <b>b</b> and the "
        "direction <b>f</b> of the force on the flat top face of the pillar:</p>"
        r"<equation>\cos\theta = \hat{\mathbf{n}}\cdot\hat{\mathbf{f}}, \qquad "
        r"\cos\lambda = \hat{\mathbf{b}}\cdot\hat{\mathbf{f}}</equation>"
        "<p><b>Cubic crystals.</b> The direction [<i>uvw</i>] is the vector (<i>u</i>, <i>v</i>, <i>w</i>), and "
        "the normal of the plane (<i>hkl</i>) is the vector (<i>h</i>, <i>k</i>, <i>l</i>). For a force "
        "along [<i>uvw</i>] and the plane (<i>hkl</i>):</p>"
        r"<equation>\cos\theta = \frac{h\,u + k\,v + l\,w}{\sqrt{h^2+k^2+l^2}\;\sqrt{u^2+v^2+w^2}}</equation>"
        f"<p>Example: fcc, tension along {pretty('[012]')}, glide system {_system(fcc012, best)}: "
        f"cos θ = {best.cos_theta:.4f}, cos λ = {best.cos_lambda:.4f}, <i>m</i> = {best.m:.4f}. This is the "
        "first row of the table at program start.</p>"
        "<p><b>Hexagonal crystals.</b> The lattice vectors are neither equally long nor perpendicular, so "
        "indices are first converted into Cartesian vectors with the structure matrix <b>D</b>, whose "
        "columns are the lattice vectors, and its reciprocal <b>D</b>*:</p>"
        r"<equation>\mathbf{f} \parallel \mathbf{D}\,[u\;v\;w]^{T}, \qquad "
        r"\mathbf{n} \parallel \mathbf{D}^{*}\,(h\;k\;l)^{T}, \qquad "
        r"\mathbf{D}^{*} = \left(\mathbf{D}^{-1}\right)^{T}</equation>"
        "<p>Only angles are needed, so the hexagonal crystal is fully described by its axial ratio "
        "<i>c</i>/<i>a</i>. It can be typed in or set by choosing a material.</p>"
        "<p><b>Four indices.</b> Hexagonal directions [<i>uvtw</i>] and planes (<i>hkil</i>) are written "
        "with four Miller–Bravais indices; the third one is redundant, <i>t</i> = −(<i>u</i> + <i>v</i>) and "
        "<i>i</i> = −(<i>h</i> + <i>k</i>), and is filled in by the program. Internally three indices are "
        "used:</p>"
        r"<equation>[uvtw] \rightarrow [UVW]: \quad U = u - t, \;\; V = v - t, \;\; W = w \qquad\qquad "
        r"(hkil) \rightarrow (hkl)</equation>"
        "<p><b>Caution:</b> in a hexagonal crystal the direction [<i>uvtw</i>] is in general not "
        "perpendicular to the plane (<i>hkil</i>) with the same indices. The loading axis can therefore be "
        "entered in two ways (<i>Given as</i>): as a crystal direction, or as the plane of the flat top "
        "face of the pillar, whose normal is then the loading axis.</p>")


def _glide_systems() -> str:
    rows = []
    for structure in STRUCTURES.values():
        lattice = structure.lattice(1.633)
        for family in structure.families:
            rows.append([structure.key, pretty(family.name), pretty(family.label), pretty(family.burgers),
                         str(len(slip_systems(lattice, family))), "on" if family.default_on else "off"])
    ratios = ", ".join(f"{name} {value:.3f}" for name, value in HCP_C_OVER_A.items())
    return (
        "<h2>Glide systems of fcc, bcc and hcp crystals</h2>"
        "<p>A glide system is the combination of a glide plane and a glide direction lying in it. "
        "Dislocations glide most easily on densely packed planes, and their Burgers vector is the shortest "
        "lattice translation, along a close-packed direction. Symmetry-equivalent systems form a slip "
        "family, written as {plane}⟨direction⟩.</p>"
        + _table(["Structure", "Slip family", "Planes and directions", "Burgers vector", "Systems",
                  "At start"], rows)
        + "<p>A plane and its opposite, or a direction and its opposite, count once.</p>"
        + _list([
            "<b>fcc</b> (Al, Cu, Ni, Au, austenitic steels): 4 planes {111} × 3 directions ⟨110⟩ = 12 systems.",
            "<b>bcc</b> (α-Fe, W, Mo, Ta, Nb): the Burgers vector is a/2 ⟨111⟩. Slip is observed on {110}, "
            "{112} and {123} planes; the last two families can be added with their check boxes.",
            "<b>hcp</b> (Mg, Ti, Zr, Zn, Co, Be): the short Burgers vector ⟨a⟩ lies in the basal plane and can "
            "glide on the basal plane, the prismatic planes and the pyramidal planes of the first kind. None "
            "of these produces a strain along the c-axis; this requires the long Burgers vector ⟨c+a⟩ on "
            "pyramidal planes.",
        ])
        + "<p>The inclination of the pyramidal planes, and with it the Schmid factors, depends on the axial "
        f"ratio. Values offered by the program: {ratios}.</p>"
        "<h3>How the program finds the systems</h3>"
        + _list([
            "All symmetry operations of the crystal (48 for the cubic point group, 24 for the hexagonal one) "
            "are applied to one plane and one direction of the family. A plane (<i>hkl</i>) is paired with a "
            "direction [<i>UVW</i>] if the direction lies in the plane: <i>hU</i> + <i>kV</i> + <i>lW</i> = 0.",
            "The list is sorted by decreasing Schmid factor. All systems whose Schmid factor equals the "
            "highest one are marked as <i>activated first</i>.",
        ]))


def _sense(fcc012, best, fcc012_compression, best_compression, force_compression) -> str:
    return (
        "<h2>Tension and compression: the sign convention</h2>"
        "<p>The pillar stands on its substrate, and the force acts on its flat top face. Everything is "
        "described <b>as seen from the force</b>, with four vectors:</p>"
        + _list([
            "<b>l, the loading axis:</b> the outward normal of the flat top face. Its indices are the ones "
            "that are entered. It belongs to the pillar and does not depend on the sense of the load.",
            f"<b>f, the direction of the force</b> on the top face: <b>f</b> = +<b>l</b> in tension (the force "
            f"pulls out of the pillar) and <b>f</b> = −<b>l</b> in compression (the force pushes into the "
            f"pillar). For the loading axis {pretty('[012]')} a tensile force acts along {pretty('[012]')} "
            f"and a compressive force along {force_compression}.",
            "<b>n, the normal of the glide plane:</b> of the two opposite normals the one that lies in the "
            "hemisphere of the force (<b>n</b>·<b>f</b> ≥ 0).",
            "<b>b, the slip direction:</b> the direction in which the part of the pillar that carries the top "
            "face is displaced with respect to the part on the substrate. The loaded part gives way to the "
            "force, therefore <b>b</b>·<b>f</b> ≥ 0.",
        ])
        + "<p>With this convention both cosines are positive, θ and λ lie between 0° and 90°, and "
        "0 ≤ <i>m</i> ≤ 0.5.</p>"
        "<p><b>The coordinate system follows the force.</b> The sample axis z is the direction of the force: "
        "it points upwards, out of the top face, in tension and downwards, into the pillar, in compression. "
        "When the sense is changed, the frame turns by half a turn about y: y stays, x and z are "
        "reversed.</p>"
        "<p><b>What changes with the sense of the load?</b> Schmid's law does not distinguish between "
        "tension and compression: the angles, the Schmid factors and the ranking stay the same. What "
        "changes is the sense of the shear, and with it the description: <b>the force, every plane normal "
        "and every slip direction are reversed.</b> The system that is activated first in the fcc pillar "
        f"with the loading axis {pretty('[012]')} is {_system(fcc012, best)} in tension and "
        f"{_system(fcc012_compression, best_compression)} in compression: the same glide plane and the same "
        "line of slip, sheared in the opposite sense.</p>"
        "<p>In the pillar sketch the top face is always at the top. The force arrow points upwards in "
        "tension and downwards in compression, and so do <b>n</b> and <b>b</b>.</p>")


def _projection(axis012, force_compression) -> str:
    return (
        "<h2>The stereographic projection</h2>"
        "<p>The stereographic projection maps every direction onto a point in a circle, without losing "
        "angular information. Imagine a sphere of radius 1 around the crystal, with the axis z pointing to "
        "its north pole and the equatorial plane as projection plane. A direction in the northern half "
        "pierces the sphere in a point, which is connected with the south pole; where this line crosses "
        "the equatorial plane lies the projected point. For a unit vector (<i>x</i>, <i>y</i>, <i>z</i>) "
        "with <i>z</i> ≥ 0, at the angle ρ from the z axis:</p>"
        r"<equation>X = \frac{x}{1+z},\qquad Y = \frac{y}{1+z},\qquad "
        r"r = \sqrt{X^2+Y^2} = \tan\frac{\rho}{2}</equation>"
        "<p>In the program <b>z is the direction of the force</b>. The projection shows the hemisphere "
        "around the force, and its centre is the force itself. By the sign convention every plane normal "
        "and every slip direction lies in this hemisphere: a plane normal appears at the distance "
        "tan(θ/2) from the centre, a slip direction at the distance tan(λ/2).</p>"
        '<figure name="stereo" width="430"/>'
        "<h3>Elements of the projection</h3>"
        + _list([
            f"<b>Centre</b> (⊙): the direction of the force, pointing towards the viewer. Its label is the "
            f"crystal direction of the force: {axis012} for tension and {force_compression} for compression "
            f"along the loading axis {axis012}.",
            "<b>Direction of view:</b> the viewer looks against the force, i.e. from above onto the top face "
            "in tension and from below the pillar in compression.",
            "<b>Poles of the glide planes</b> (circles): the plane normals <b>n</b>, coloured by the highest "
            "Schmid factor of the systems on this plane. A red ring marks the planes of the systems that are "
            "activated first.",
            "<b>Slip directions</b> (squares): shown for the selected plane, each coloured by the Schmid "
            "factor of this plane–direction pair. They lie on the trace of their plane.",
            "<b>Trace of a plane:</b> the arc of all directions that lie in the plane, each 90° away from "
            "the pole.",
            "<b>Primitive circle</b> (outer circle): everything perpendicular to the force (θ = 90° or "
            "λ = 90°, <i>m</i> = 0).",
            "<b>45° circle</b> (optional): a system has a high Schmid factor if its pole and its slip "
            "direction lie close to this circle, on one line with the centre and on opposite sides of it.",
            "<b>Orientation:</b> x and y of the projection are the sample axes drawn in the pillar sketch. "
            "The slider <i>Rotation about axis</i> turns the crystal about the loading axis; this changes "
            "neither the angles nor the Schmid factors.",
        ])
        + "<p><b>From tension to compression:</b> the projection for compression is the projection for "
        "tension mirrored top to bottom, with all indices of opposite sign. The distances from the centre, "
        "i.e. the angles θ and λ, are the same.</p>")


def _multiplicity() -> str:
    bcc_keys = [family.key for family in STRUCTURES["bcc"].families]
    axes = [(0, 0, 1), (0, 1, 1), (1, 1, 1), (0, 1, 2), (1, 1, 2), (1, 2, 2), (1, 2, 3)]
    where = ["corner", "corner", "corner", "edge [001]–[011]", "edge [001]–[111]", "edge [011]–[111]",
             "inside"]
    rows = []
    for axis, position in zip(axes, where):
        fcc = analyse("fcc", Loading(axis))
        bcc = analyse("bcc", Loading(axis), family_keys=bcc_keys)
        rows.append(["[" + "".join(map(str, axis)) + "]", position, str(len(fcc.primary)),
                     f"{fcc.results[0].m:.4f}", str(len(bcc.primary)), f"{bcc.results[0].m:.4f}"])
    return (
        "<h2>Single slip, multiple slip and the orientation map</h2>"
        "<p>For most loading directions one glide system has a higher Schmid factor than all others: the "
        "crystal deforms by single slip. For loading directions of high symmetry several systems are "
        "equivalent and share the highest Schmid factor: they are activated together (multiple slip).</p>"
        "<p>Because of the symmetry of the crystal it is sufficient to consider one standard triangle of "
        f"loading directions; for cubic crystals it has the corners [001], [011] and {pretty('[-111]')} "
        "(which is equivalent to [111]).</p>"
        + _table(["Loading axis", "Position in the standard triangle", "fcc: systems activated first",
                  "fcc: highest <i>m</i>", "bcc (48 systems): activated first", "bcc: highest <i>m</i>"],
                 rows)
        + "<p>Inside the triangle an fcc crystal deforms by single slip, on its edges two systems are "
        "equivalent, and in the corners four ([011]), six ([111]) or eight ([001]) systems. [111] is the "
        "hardest orientation of an fcc crystal.</p>"
        "<p><b>Orientation map</b> (<i>Pick on orientation map…</i> or Ctrl+M): a standard projection of the "
        "crystal with [001], respectively [0001], in the centre. Every point of the disc is a possible "
        "loading direction; the colour shows the highest Schmid factor of the active slip families (or, "
        "with <i>Rank by yield stress</i>, the lowest yield stress). A click makes the nearest direction "
        "with small indices the loading axis; <i>Largest index</i> limits the size of these indices.</p>")


def _inverse_pole_figure() -> str:
    return (
        "<h2>The inverse pole figure</h2>"
        "<p>The small figure below the index fields of the loading axis is an inverse pole figure: it "
        "shows a direction of the sample, here the loading axis, in the frame of the crystal. Only the "
        "standard triangle is drawn, because every direction is equivalent by symmetry to one direction "
        "inside it.</p>"
        '<figure name="ipf" width="400"/>'
        "<p>To find the point, the program applies all symmetry operations <b>R</b> of the crystal to the "
        "loading axis <b>l</b> (48 for cubic, 24 for hexagonal crystals) and keeps the equivalent direction "
        "that lies inside the triangle, i.e. on the inner side of the three planes through two corners "
        "each:</p>"
        r"<equation>\hat{\mathbf{l}}' = \mathbf{R}\,\hat{\mathbf{l}} \quad \mathrm{with} \quad "
        r"\hat{\mathbf{l}}'\cdot\mathbf{e}_k \geq 0 \;\; (k = 1, 2, 3), \qquad "
        r"\mathbf{e}_k = \pm\,\frac{\mathbf{c}_i\times\mathbf{c}_j}{|\mathbf{c}_i\times\mathbf{c}_j|}</equation>"
        f"<p>For cubic crystals the triangle with the corners [001], [011] and {pretty('[-111]')} contains "
        "the directions [<i>uvw</i>] with</p>"
        r"<equation>w \;\geq\; v \;\geq\; -u \;\geq\; 0</equation>"
        "<p>In words: take the absolute values of the three indices, sort them in ascending order and give "
        f"the first one a minus sign. The loading axis [123] is plotted at {pretty('[-123]')}, and so are "
        f"{pretty('[3 -1 -2]')}, {pretty('[-2 3 1]')} and all other directions of the family ⟨123⟩. If the "
        "entered axis lies outside the triangle, the program names the equivalent direction inside it. The "
        "list of Schmid factors is the same for both; only the indices of the glide systems are "
        "exchanged.</p>"
        f"<p>For hexagonal crystals the triangle has the corners [0001], {pretty('[2 -1 -1 0]')} and "
        f"{pretty('[1 0 -1 0]')}: a sector of 30° that reaches from the c-axis, on the left, down to the "
        "basal plane, the arc on the right.</p>"
        "<p>The inversion is one of the symmetry operations, so that <b>l</b> and −<b>l</b> are the same "
        "point: the star does not move when the load is switched between tension and compression.</p>")


def _crss() -> str:
    return (
        "<h2>Critical resolved shear stress of different slip families</h2>"
        "<p>Schmid factors can only be compared directly if all systems have the same critical resolved "
        "shear stress. This holds within one family, but not between families: in magnesium, for instance, "
        "basal glide needs a far lower shear stress than glide on prismatic or pyramidal planes.</p>"
        "<p>If <i>Rank by yield stress</i> is switched on, each family gets its own τ<sub>CRSS</sub>, and "
        "for every system the program calculates the applied stress at which it would start to glide:</p>"
        r"<equation>\sigma_y^{(s)} = \frac{\tau_{\mathrm{CRSS}}^{(s)}}{m^{(s)}}, \qquad "
        r"\sigma_y = \min_{s}\; \sigma_y^{(s)}</equation>"
        "<p>The list is then sorted by increasing yield stress, and the system with the lowest value is "
        "activated first. The values can be entered in any unit (MPa, or relative to the easiest family); "
        "the yield stress is obtained in the same unit.</p>"
        "<p>The program contains no material data: the values must be taken from the literature for the "
        "material, purity and temperature in question.</p>")


def _window() -> str:
    return (
        "<h2>The program window</h2>"
        "<h3>Settings (left)</h3>"
        + _list([
            "<b>Crystal:</b> structure (fcc, bcc, hcp). For hcp a material can be chosen, which sets the "
            "axial ratio c/a, or c/a is typed in directly.",
            "<b>Loading axis:</b> the outward normal of the flat top face of the pillar, as indices "
            "[<i>uvw</i>] or, for hcp, [<i>uvtw</i>]. <i>Presets</i> offers common directions. <i>Tension</i> or "
            "<i>Compression</i> sets the sense of the force. The line below the index fields gives the crystal "
            "direction of the force.",
            "<b>Inverse pole figure:</b> marks the loading axis with a star in the standard triangle of the "
            "crystal.",
            "<b>Slip families:</b> the check boxes decide which families are taken into account. With "
            "<i>Rank by yield stress</i> the CRSS fields become active.",
            "<b>Display:</b> rotation of the crystal about the loading axis and the optional elements of the "
            "projection (index labels, reference directions, traces of all glide planes, 45° circle, Wulff "
            "net).",
        ])
        + "<h3>Pillar sketch</h3>"
        "<p>The black arrow above the pillar is the force on the top face; the grey arrows on the substrate "
        "are the sample axes x and y. A selected plane is drawn in the colour of its Schmid factor with its "
        "normal <b>n</b> and the angle θ; with a selected direction, the slip direction <b>b</b>, the angle λ "
        "and a pair of arrows for the sense of the shear stress are added. The sketch can be turned with "
        "the left mouse button.</p>"
        "<p>With <i>Auto view</i> the program turns the pillar such that the selected plane is seen well. "
        "The view changes only when another plane is selected: it is kept while you switch between the "
        "slip directions of one plane, so that the plane visibly stays the same. <i>Reset view</i> returns "
        "to this view after the pillar has been turned by hand.</p>"
        "<h3>Stereographic projection</h3>"
        "<p>A click on a pole selects the plane; its trace and its slip directions (squares) appear. A "
        "click on a square selects the complete glide system; the two lines from the centre then show θ "
        "and λ. A click on the empty background, or the Esc key, clears the selection. Resting the mouse "
        "on a symbol shows its indices and its angle to the force.</p>"
        "<h3>Table</h3>"
        "<p>All glide systems of the active families with the angles, the two cosines and the Schmid "
        "factor, sorted with the system that is activated first at the top (bold rows). A click on a row "
        "selects this system in both figures; a click on a column header sorts by that column. The line "
        "above the table states how many systems are activated first.</p>")


def _export() -> str:
    return (
        "<h2>Copying and exporting</h2>"
        + _list([
            "<b>Figures:</b> every figure (pillar sketch, stereographic projection, inverse pole figure, "
            "orientation map) has the buttons <i>Copy image</i> (bitmap with 300 dpi to the clipboard, ready "
            "to paste into a report or a presentation) and <i>Save as…</i> (PNG, or the vector formats SVG "
            "and PDF). The figure is exported as it is shown, including the selection and the viewing "
            "direction.",
            "<b>Table:</b> <i>Copy table</i> puts the complete list on the clipboard as tab-separated text "
            "that can be pasted directly into a spreadsheet. <i>Export CSV…</i> writes a text file. Choose "
            "the decimal separator that your spreadsheet program expects; with the decimal comma the "
            "columns are separated by semicolons, otherwise by commas.",
            "With <i>with settings header</i> the crystal, the loading axis, the sense and direction of the "
            "force, the slip families and the sign convention are written above the table, so that the "
            "file documents itself.",
            "The same commands are in the <i>File</i> menu.",
        ]))


def _examples(fcc012, best) -> str:
    c_over_a = HCP_C_OVER_A["Mg"]
    mg_c = analyse("hcp", Loading((0, 0, 1)), c_over_a=c_over_a)
    families = sorted({pretty(r.system.family.name) for r in mg_c.primary})
    mg_axis = mb_direction_to_miller((2, -1, -1, 3))
    mg = analyse("hcp", Loading(mg_axis), c_over_a=c_over_a)
    basal = max((r for r in mg.results if r.system.family.key == "hcp_basal_a"), key=lambda r: r.m)
    fcc001 = analyse("fcc", Loading((0, 0, 1)))
    fcc111 = analyse("fcc", Loading((1, 1, 1)))
    return (
        "<h2>Examples to try</h2>"
        f"<h3>fcc crystal along {pretty('[012]')}</h3>"
        f"<p>The start state. {len(fcc012.primary)} systems share the highest Schmid factor {best.m:.4f}, "
        "close to the maximum of 0.5: the pillar deforms by double slip. Select the first row and compare "
        "tension with compression: what happens to the indices, to the pillar sketch and to the "
        "projection?</p>"
        "<h3>bcc crystal along [012]</h3>"
        "<p>Switch the structure to bcc. With the family {110}⟨111⟩ the list contains exactly the same "
        "Schmid factors as for fcc: the bcc family is obtained from the fcc family {111}⟨110⟩ by "
        "exchanging the roles of plane and direction, and the Schmid factor is symmetric in <b>n</b> and "
        "<b>b</b>. Now tick the families {112}⟨111⟩ and {123}⟨111⟩: the table grows to 48 systems.</p>"
        "<h3>High-symmetry orientations of fcc</h3>"
        f"<p>Choose the presets [001], [011] and [111]. For [001], {len(fcc001.primary)} systems share "
        f"<i>m</i> = {fcc001.results[0].m:.4f}; for [111], {len(fcc111.primary)} systems share "
        f"<i>m</i> = {fcc111.results[0].m:.4f}. Which orientation needs the highest stress to yield?</p>"
        "<h3>Magnesium along the c-axis</h3>"
        f"<p>Choose hcp, the material Mg (c/a = {c_over_a:.3f}) and the preset [0001]. All ⟨a⟩ systems "
        "(basal, prismatic, pyramidal ⟨a⟩) have a Schmid factor of exactly zero: their Burgers vector is "
        f"perpendicular to the c-axis. Only ⟨c+a⟩ systems can act ({', '.join(families)}: "
        f"<i>m</i> = {mg_c.results[0].m:.4f}). A magnesium crystal loaded along c is therefore in a hard "
        "orientation.</p>"
        "<h3>Magnesium: the highest Schmid factor does not always win</h3>"
        f"<p>Set the loading axis to {pretty('[2 -1 -1 3]')}. By the Schmid factor alone, a pyramidal "
        f"system is in front (<i>m</i> = {mg.results[0].m:.4f}), ahead of the best basal system "
        f"(<i>m</i> = {basal.m:.4f}). Now switch on <i>Rank by yield stress</i> and give the non-basal "
        "families a much higher CRSS than the basal one (for instance basal 1, prismatic 40, pyramidal 50 "
        "to 80, as an illustration): the basal system is activated first.</p>")


def _limits() -> str:
    return (
        "<h2>Limits of the model</h2>"
        "<p>The program answers one question: which glide systems experience the highest resolved shear "
        "stress, and are therefore expected to become active first, in an ideal uniaxial test? It does not "
        "contain:</p>"
        + _list([
            "<b>Schmid's law only.</b> In bcc metals the motion of screw dislocations also depends on stress "
            "components other than the resolved shear stress (non-Schmid effects) and on the sense of shear "
            "on {112} planes. Real bcc crystals can therefore behave differently in tension and "
            "compression, which the program does not reproduce.",
            "<b>No deformation twinning.</b> Twinning is an important deformation mode of hcp metals loaded "
            "along the c-axis and of some fcc alloys. It is not a glide system and is not considered.",
            "<b>Only the onset of slip.</b> Work hardening, the interaction of glide systems and the "
            "rotation of the crystal lattice during deformation are not modelled.",
            "<b>Ideal test.</b> The stress is assumed to be uniaxial and homogeneous. Friction at the top "
            "face, the lateral constraint by the loading tool, misalignment, the taper of real pillars, "
            "bending and buckling are neglected.",
            "<b>No material data.</b> The values of τ<sub>CRSS</sub> must be supplied by the user.",
            "<b>The slip step is a sketch.</b> It shows the direction and the sense of the shear, not its "
            "amount.",
        ]))


def _references() -> str:
    return (
        "<h2>References</h2>"
        + _list([
            "E. Schmid, W. Boas: <i>Kristallplastizität</i>. Springer, Berlin, 1935.",
            "D. Hull, D. J. Bacon: <i>Introduction to Dislocations</i>, 5th edition. Butterworth-Heinemann, "
            "Oxford, 2011.",
            "G. Gottstein: <i>Physical Foundations of Materials Science</i>. Springer, Berlin, 2004.",
            "M. H. Yoo: Slip, twinning, and fracture in hexagonal close-packed metals. <i>Metallurgical "
            "Transactions A</i> 12 (1981) 409–418.",
            "M. D. Uchic, D. M. Dimiduk, J. N. Florando, W. D. Nix: Sample dimensions influence strength and "
            "crystal plasticity. <i>Science</i> 305 (2004) 986–989.",
            "F. Mompiou, R.-X. Xie: pycotem: An open source toolbox for online crystal defect "
            "characterization from TEM imaging and diffraction. <i>Journal of Microscopy</i> 282 (2021) "
            "84–97. (Used here only as an independent check of the calculation.)",
        ], numbered=True))


def licence_html() -> str:
    """Licence of the program and acknowledgement of the software it is built on."""
    def rows(role):
        return [[f'<a href="{c.url}">{c.name}</a>', c.use + (f"<br><i>{c.note}</i>" if c.note else ""),
                 c.licence] for c in third_party.components(role)]

    header = ["Software", "Used for", "Licence"]
    return (
        "<h2>Licence and acknowledgements</h2>"
        f"<p><b>{APP_NAME} {__version__}</b><br>{third_party.COPYRIGHT}<br>"
        f"Author: {AUTHOR}, <a href='https://{WEBSITE}'>{WEBSITE}</a></p>"
        + "".join(f"<p>{paragraph}</p>" for paragraph in third_party.NOTICE)
        + f"<p>Licence: {third_party.LICENCE_NAME} ({third_party.LICENCE_ID}), "
        f"<a href='{third_party.LICENCE_URL}'>{third_party.LICENCE_URL}</a>. The text of the licence is in the "
        "file <i>LICENSE</i> that comes with the program, and the source code may be passed on and changed "
        "under the same licence.</p>"
        "<h3>Software the program is built on</h3>"
        "<p>The program uses the following software, with thanks to its authors. The licence texts are in "
        "the folder <i>licenses</i> next to the executable.</p>"
        + _table(header, rows(third_party.RUNTIME))
        + "<h3>Tools used to test, document and package the program</h3>"
        + _table(header, rows(third_party.BUILD))
        + "<h3>Independent check</h3>"
        + _table(header, rows(third_party.REFERENCE)))
