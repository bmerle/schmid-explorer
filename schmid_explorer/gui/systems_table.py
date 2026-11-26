# SPDX-License-Identifier: GPL-3.0-or-later
"""Table of all slip systems, ranked; a row selects glide plane + glide direction."""

from __future__ import annotations

from math import isinf

from ..core.schmid import Analysis
from ..plotting.style import Selection, schmid_colour
from .qt import Qt, QtGui, QtWidgets, Signal
from .text import pretty

COLUMNS = ("Rank", "Slip family", "Plane", "Direction", "θ (°)", "λ (°)", "cos θ", "cos λ",
           "Schmid factor m", "CRSS", "Yield stress", "Activated first")
TOOLTIPS = (
    "Position in the ranking (1 = activated first)",
    "Family of symmetry-equivalent slip systems",
    "Glide plane; of its two normals the one in the hemisphere of the force is given (n · F ≥ 0)",
    "Slip direction b (direction of the Burgers vector): the direction in which the part of the\n"
    "pillar carrying the top face is displaced. It follows the force (b · F ≥ 0)",
    "Angle between the force on the top face and the plane normal n",
    "Angle between the force on the top face and the slip direction b",
    "", "",
    "m = cos θ · cos λ; resolved shear stress τ = m · σ",
    "Critical resolved shear stress of the slip family",
    "Applied stress at which this system starts to glide: CRSS / m",
    "Systems that reach their critical resolved shear stress first",
)
_PLANE, _M, _CRSS, _YIELD = 2, 8, 9, 10
_KEYS = Qt.ItemDataRole.UserRole + 1
_HIGHLIGHT = QtGui.QColor("#ffe9a8")


class _Item(QtWidgets.QTableWidgetItem):
    """Cell that sorts by its numerical value instead of by its text."""

    def __init__(self, text: str, value=None):
        super().__init__(text)
        self.value = text if value is None else value
        self.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

    def __lt__(self, other):
        try:
            return self.value < other.value
        except TypeError:
            return str(self.value) < str(other.value)


class SystemsTable(QtWidgets.QTableWidget):
    systemSelected = Signal(object, object)        # plane key, direction key

    def __init__(self, parent=None):
        super().__init__(0, len(COLUMNS), parent)
        self.setHorizontalHeaderLabels(COLUMNS)
        for column, tip in enumerate(TOOLTIPS):
            self.horizontalHeaderItem(column).setToolTip(tip)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(22)
        self.horizontalHeader().setStretchLastSection(True)
        self.setSortingEnabled(True)
        self._selection = Selection()
        self.itemSelectionChanged.connect(self._row_selected)

    def show_analysis(self, analysis: Analysis, selection: Selection):
        lattice = analysis.lattice
        self.blockSignals(True)
        self.setSortingEnabled(False)
        self.setRowCount(len(analysis.results))
        bold = self.font()
        bold.setBold(True)
        for row, r in enumerate(analysis.results):
            yield_text = "∞" if isinf(r.yield_stress) else f"{r.yield_stress:.4g}"
            cells = [
                _Item(str(r.rank), r.rank),
                _Item(pretty(f"{r.system.family.name}  {r.system.family.label}")),
                _Item(pretty(lattice.plane_text(r.plane))),
                _Item(pretty(lattice.direction_text(r.direction))),
                _Item(f"{r.theta_deg:.2f}", r.theta_deg),
                _Item(f"{r.lambda_deg:.2f}", r.lambda_deg),
                _Item(f"{r.cos_theta:.4f}", r.cos_theta),
                _Item(f"{r.cos_lambda:.4f}", r.cos_lambda),
                _Item(f"{r.m:.4f}", r.m),
                _Item(f"{r.crss:g}", r.crss),
                _Item(yield_text, r.yield_stress),
                _Item("yes" if r.primary else "", 0 if r.primary else 1),
            ]
            cells[0].setData(_KEYS, (r.plane_key, r.direction_key))
            colour = schmid_colour(r.m)
            cells[_M].setBackground(QtGui.QColor.fromRgbF(*colour[:3]))
            luminance = 0.299 * colour[0] + 0.587 * colour[1] + 0.114 * colour[2]
            cells[_M].setForeground(QtGui.QColor("black" if luminance > 0.5 else "white"))
            for column, cell in enumerate(cells):
                if column not in (1,):
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if r.primary:
                    cell.setFont(bold)
                self.setItem(row, column, cell)
        self.setColumnHidden(_CRSS, not analysis.use_crss)
        self.setColumnHidden(_YIELD, not analysis.use_crss)
        self.horizontalHeader().setSortIndicator(0, Qt.SortOrder.AscendingOrder)
        self.setSortingEnabled(True)
        self.resizeColumnsToContents()
        self.blockSignals(False)
        self.set_selection(selection)

    def set_selection(self, selection: Selection):
        """Show the selection made elsewhere: full system = selected row, plane = tinted cells."""
        self._selection = selection
        self.blockSignals(True)
        self.clearSelection()
        for row in range(self.rowCount()):
            plane_key, direction_key = self.item(row, 0).data(_KEYS)
            on_plane = selection.plane is not None and tuple(plane_key) == tuple(selection.plane)
            brush = QtGui.QBrush(_HIGHLIGHT) if on_plane else QtGui.QBrush()
            self.item(row, _PLANE).setBackground(brush)
            if on_plane and selection.direction is not None \
                    and tuple(direction_key) == tuple(selection.direction):
                self.selectRow(row)
                self.scrollToItem(self.item(row, 0))
        self.blockSignals(False)

    def _row_selected(self):
        rows = self.selectionModel().selectedRows()
        if rows:
            plane_key, direction_key = self.item(rows[0].row(), 0).data(_KEYS)
            self.systemSelected.emit(tuple(plane_key), tuple(direction_key))
