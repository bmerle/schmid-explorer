# SPDX-License-Identifier: GPL-3.0-or-later
"""Text export of the ranked slip-system table (clipboard, CSV)."""

from __future__ import annotations

import csv
import io
from math import isinf

from .schmid import DIRECTION, Analysis, force_text, load_axis_text

HEADERS = (
    "Rank", "Slip family", "Plane", "Direction", "theta (deg)", "lambda (deg)",
    "cos(theta)", "cos(lambda)", "Schmid factor m", "CRSS", "Yield stress CRSS/m",
    "Activated first",
)


def table_rows(analysis: Analysis) -> list:
    """Rows of the result table with native Python values (floats not yet formatted)."""
    lattice = analysis.lattice
    rows = []
    for r in analysis.results:
        rows.append([
            r.rank,
            f"{r.system.family.name} {r.system.family.label}",
            lattice.plane_text(r.plane),
            lattice.direction_text(r.direction),
            round(r.theta_deg, 2),
            round(r.lambda_deg, 2),
            round(r.cos_theta, 4),
            round(r.cos_lambda, 4),
            round(r.m, 4),
            r.crss,
            r.yield_stress,
            "yes" if r.primary else "",
        ])
    return rows


def metadata_lines(analysis: Analysis) -> list:
    """Description of the calculation, written above the exported table."""
    lattice = analysis.lattice
    lines = [
        "Schmid Explorer - slip systems ranked by "
        + ("yield stress CRSS/m" if analysis.use_crss else "Schmid factor"),
        f"Crystal structure: {analysis.structure.name}",
    ]
    if lattice.four_index:
        lines.append(f"c/a: {lattice.c_over_a:g}")
    kind = "direction" if analysis.loading.kind == DIRECTION else "plane normal"
    lines.append(f"Loading axis = outward normal of the pillar top face ({kind}): "
                 f"{load_axis_text(lattice, analysis.loading)}")
    lines.append(f"Loading sense: {analysis.loading.sense}")
    lines.append(f"Force on the top face along: {force_text(lattice, analysis.loading)}")
    lines.append("Plane normal and slip direction (of the part carrying the top face) both point "
                 "into the hemisphere of the force.")
    for key in analysis.family_keys:
        family = analysis.structure.family(key)
        lines.append(f"Slip family: {family.name} {family.label}, CRSS = {analysis.crss[key]:g}")
    lines.append(analysis.summary())
    return lines


def to_text(analysis: Analysis, delimiter: str = "\t", decimal: str = ".",
            metadata: bool = True) -> str:
    """Delimited text of the table; `decimal` is the decimal separator ('.' or ',')."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=delimiter, lineterminator="\n")
    if metadata:
        for line in metadata_lines(analysis):
            writer.writerow(["# " + line])
    writer.writerow(HEADERS)
    for row in table_rows(analysis):
        writer.writerow([_format(value, decimal) for value in row])
    return buffer.getvalue()


def _format(value, decimal: str) -> str:
    if isinstance(value, float):
        if isinf(value):
            return "inf"
        text = f"{value:.4f}".rstrip("0").rstrip(".") if value != int(value) else f"{value:.0f}"
        return text.replace(".", decimal)
    return str(value)
