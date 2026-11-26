# SPDX-License-Identifier: GPL-3.0-or-later
"""Settings panel: crystal, loading axis, slip families and display options."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..core.lattice import (
    CUBIC, mb_direction_to_miller, mb_plane_to_miller, miller_to_mb_direction, miller_to_mb_plane,
)
from ..core.schmid import COMPRESSION, DIRECTION, PLANE_NORMAL, TENSION
from ..core.slip_systems import HCP_C_OVER_A, STRUCTURES, slip_systems
from ..plotting.stereo_plot import StereoOptions
from .figure_panel import IpfPanel
from .qt import Qt, QtWidgets, Signal
from .text import pretty

CUSTOM = "custom"
CUBIC_PRESETS = [(0, 0, 1), (0, 1, 1), (1, 1, 1), (0, 1, 2), (1, 1, 2), (1, 2, 3), (1, 4, 9)]
HEX_PRESETS = [(0, 0, 0, 1), (2, -1, -1, 0), (1, 0, -1, 0), (2, -1, -1, 3), (1, 0, -1, 1),
               (1, 0, -1, 2), (2, -1, -1, 2)]              # Miller-Bravais directions


@dataclass(frozen=True)
class Inputs:
    """Everything the user has set; the main window turns it into an analysis."""

    structure: str
    c_over_a: float
    indices: tuple                 # loading axis, three Miller indices
    kind: str                      # DIRECTION or PLANE_NORMAL
    sense: str                     # COMPRESSION or TENSION
    family_keys: tuple
    crss: dict
    use_crss: bool
    azimuth: float                 # rotation of the projection about the loading axis (deg)
    stereo: StereoOptions = field(default_factory=StereoOptions)

    @property
    def valid(self) -> bool:
        return any(i != 0 for i in self.indices)


class SettingsPanel(QtWidgets.QWidget):
    changed = Signal()
    pickRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._updating = False
        self._family_rows = {}          # family key -> (check box, CRSS spin box)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self._crystal_group())
        layout.addWidget(self._loading_group())
        layout.addWidget(self._family_group())
        layout.addWidget(self._view_group())
        layout.addStretch(1)

        self._structure_changed(emit=False)

    # ------------------------------------------------------------------ construction
    def _crystal_group(self):
        group = QtWidgets.QGroupBox("Crystal")
        form = QtWidgets.QFormLayout(group)
        self.structure = QtWidgets.QComboBox()
        for key, structure in STRUCTURES.items():
            self.structure.addItem(structure.name, key)
        self.structure.currentIndexChanged.connect(lambda *_: self._structure_changed())
        form.addRow("Structure", self.structure)

        self.material = QtWidgets.QComboBox()
        for name, value in HCP_C_OVER_A.items():
            self.material.addItem(f"{name}  (c/a = {value:.3f})", value)
        self.material.addItem(CUSTOM, None)
        self.material.currentIndexChanged.connect(self._material_changed)
        self.c_over_a = QtWidgets.QDoubleSpinBox()
        self.c_over_a.setRange(1.0, 2.5)
        self.c_over_a.setDecimals(3)
        self.c_over_a.setSingleStep(0.005)
        self.c_over_a.setValue(1.633)
        self.c_over_a.setKeyboardTracking(False)
        self.c_over_a.valueChanged.connect(self._c_over_a_changed)
        self.material_label = QtWidgets.QLabel("Material")
        self.c_over_a_label = QtWidgets.QLabel("Axial ratio c/a")
        form.addRow(self.material_label, self.material)
        form.addRow(self.c_over_a_label, self.c_over_a)
        return group

    def _loading_group(self):
        group = QtWidgets.QGroupBox("Loading axis = normal of the pillar top face")
        layout = QtWidgets.QVBoxLayout(group)

        self.kind = QtWidgets.QComboBox()
        self.kind.addItem("crystal direction [uvtw]", DIRECTION)
        self.kind.addItem("normal of the plane (hkil)", PLANE_NORMAL)
        self.kind.setToolTip("In hexagonal crystals the direction [uvtw] is in general not\n"
                             "perpendicular to the plane (uvtw). Choose how the axis is given.")
        self.kind.currentIndexChanged.connect(self._kind_changed)
        self.kind_label = QtWidgets.QLabel("Given as")
        kind_row = QtWidgets.QHBoxLayout()
        kind_row.addWidget(self.kind_label)
        kind_row.addWidget(self.kind, 1)
        layout.addLayout(kind_row)

        grid = QtWidgets.QGridLayout()
        self.index_labels, self.index_spins = [], []
        for column in range(4):
            label = QtWidgets.QLabel()
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            spin = QtWidgets.QSpinBox()
            spin.setRange(-99, 99)
            spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
            spin.setKeyboardTracking(False)
            spin.valueChanged.connect(self._index_changed)
            grid.addWidget(label, 0, column)
            grid.addWidget(spin, 1, column)
            self.index_labels.append(label)
            self.index_spins.append(spin)
        self.index_spins[2].setReadOnly(True)
        self.index_spins[2].setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.index_spins[2].setToolTip("Third Miller–Bravais index: −(first + second), set automatically.")
        layout.addLayout(grid)

        self.axis_echo = QtWidgets.QLabel()
        self.axis_echo.setWordWrap(True)
        layout.addWidget(self.axis_echo)

        row = QtWidgets.QHBoxLayout()
        self.presets = QtWidgets.QComboBox()
        self.presets.activated.connect(self._preset_chosen)
        self.pick = QtWidgets.QPushButton("Pick on orientation map…")
        self.pick.setToolTip("Open a map of the highest Schmid factor for every loading axis\n"
                             "and choose the axis with a mouse click.")
        self.pick.clicked.connect(self.pickRequested.emit)
        row.addWidget(self.presets)
        row.addWidget(self.pick, 1)
        layout.addLayout(row)

        sense = QtWidgets.QHBoxLayout()
        self.tension = QtWidgets.QRadioButton("Tension")
        self.compression = QtWidgets.QRadioButton("Compression")
        self.tension.setChecked(True)
        tip = ("Sense of the force F on the top face. The sample axis z and the centre of the\n"
               "stereographic projection always point along F.\n"
               "Tension: F pulls along the loading axis, z points up, out of the top face.\n"
               "Compression: F pushes against the loading axis, z points down, into the pillar;\n"
               "the x-y-z frame is turned accordingly (x is reversed, y stays).\n"
               "Plane normals n and slip directions b point into the hemisphere of F, so that\n"
               "their indices change sign when the loading is reversed.")
        self.tension.setToolTip(tip)
        self.compression.setToolTip(tip)
        self.compression.toggled.connect(lambda *_: self._echo_axis())
        self.compression.toggled.connect(self._emit)
        sense.addWidget(QtWidgets.QLabel("Loading"))
        sense.addWidget(self.tension)
        sense.addWidget(self.compression)
        sense.addStretch(1)
        layout.addLayout(sense)

        self.ipf = IpfPanel()                       # drawn by the main window from the analysis
        layout.addWidget(self.ipf)
        return group

    def _family_group(self):
        group = QtWidgets.QGroupBox("Slip families")
        layout = QtWidgets.QVBoxLayout(group)
        self.family_grid = QtWidgets.QGridLayout()
        layout.addLayout(self.family_grid)
        self.use_crss = QtWidgets.QCheckBox("Rank by yield stress  (CRSS / m)")
        self.use_crss.setToolTip(
            "Give every slip family its own critical resolved shear stress (CRSS),\n"
            "in any unit, e.g. MPa or relative to the easiest family. The system with\n"
            "the lowest yield stress CRSS / m is then activated first.")
        self.use_crss.toggled.connect(self._use_crss_changed)
        layout.addWidget(self.use_crss)
        return group

    def _view_group(self):
        group = QtWidgets.QGroupBox("Display")
        layout = QtWidgets.QVBoxLayout(group)
        row = QtWidgets.QHBoxLayout()
        self.azimuth = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.azimuth.setRange(-180, 180)
        self.azimuth_spin = QtWidgets.QSpinBox()
        self.azimuth_spin.setRange(-180, 180)
        self.azimuth_spin.setSuffix("°")
        self.azimuth.valueChanged.connect(self.azimuth_spin.setValue)
        self.azimuth_spin.valueChanged.connect(self.azimuth.setValue)
        self.azimuth.valueChanged.connect(self._emit)
        tip = "Rotate the crystal about the loading axis (pillar and projection turn together)."
        self.azimuth.setToolTip(tip)
        label = QtWidgets.QLabel("Rotation about axis")
        label.setToolTip(tip)
        row.addWidget(label)
        row.addWidget(self.azimuth, 1)
        row.addWidget(self.azimuth_spin)
        layout.addLayout(row)

        self.show_labels = self._check("Index labels", True)
        self.show_reference = self._check("Reference directions (low-index poles)", True)
        self.show_traces = self._check("Traces (great circles) of all glide planes", False)
        self.show_circle = self._check("45° circle around the loading axis", False)
        self.show_net = self._check("Wulff net", False)
        for box in (self.show_labels, self.show_reference, self.show_traces, self.show_circle,
                    self.show_net):
            layout.addWidget(box)
        return group

    def _check(self, text: str, checked: bool):
        box = QtWidgets.QCheckBox(text)
        box.setChecked(checked)
        box.toggled.connect(self._emit)
        return box

    # ------------------------------------------------------------------ reactions
    def _emit(self, *_):
        if not self._updating:
            self.changed.emit()

    def _structure_key(self) -> str:
        return self.structure.currentData()

    def _hexagonal(self) -> bool:
        return STRUCTURES[self._structure_key()].lattice_system != CUBIC

    def _structure_changed(self, emit: bool = True):
        self._updating = True
        structure = STRUCTURES[self._structure_key()]
        hexagonal = self._hexagonal()
        for widget in (self.material, self.material_label, self.c_over_a, self.c_over_a_label,
                       self.kind, self.kind_label, self.index_labels[2], self.index_spins[2]):
            widget.setVisible(hexagonal)

        # slip families of this structure
        while self.family_grid.count():
            item = self.family_grid.takeAt(0)
            if item.widget() is not None:
                item.widget().hide()
                item.widget().deleteLater()
        self._family_rows = {}
        header = QtWidgets.QLabel("CRSS")
        header.setToolTip("Critical resolved shear stress of the slip family")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.family_grid.addWidget(header, 0, 1)
        lattice = structure.lattice(self.c_over_a.value())
        for row, family in enumerate(structure.families, start=1):
            count = len(slip_systems(lattice, family))
            box = QtWidgets.QCheckBox(pretty(f"{family.name}  {family.label}  ({count})"))
            box.setChecked(family.default_on)
            box.setToolTip(f"{count} slip systems, Burgers vector {pretty(family.burgers)}")
            box.toggled.connect(self._emit)
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(0.01, 99999.0)
            spin.setDecimals(2)
            spin.setValue(1.0)
            spin.setKeyboardTracking(False)
            spin.setFixedWidth(96)
            spin.setEnabled(self.use_crss.isChecked())
            spin.valueChanged.connect(self._emit)
            self.family_grid.addWidget(box, row, 0)
            self.family_grid.addWidget(spin, row, 1)
            self._family_rows[family.key] = (box, spin)
        self.family_grid.setColumnStretch(0, 1)

        # presets and a sensible start axis
        self.presets.clear()
        self.presets.addItem("Presets")
        if hexagonal:
            for uvtw in HEX_PRESETS:
                self.presets.addItem(pretty("[" + " ".join(map(str, uvtw)) + "]"), uvtw)
            self.kind.setCurrentIndex(0)
            self._set_spins((2, -1, -1, 3))
        else:
            for uvw in CUBIC_PRESETS:
                self.presets.addItem(pretty("[" + " ".join(map(str, uvw)) + "]"), uvw)
            self._set_spins((0, 1, 0, 2))
        self._label_indices()
        self._updating = False
        if emit:
            self.changed.emit()

    def _label_indices(self):
        if not self._hexagonal():
            names = ("u", "v", "", "w")
        elif self.kind.currentData() == DIRECTION:
            names = ("u", "v", "t", "w")
        else:
            names = ("h", "k", "i", "l")
        for label, name in zip(self.index_labels, names):
            label.setText(name)
        self._echo_axis()

    def _echo_axis(self):
        indices = self._indices()
        if not any(indices):
            self.axis_echo.setText("<span style='color:#b00020'>Enter at least one non-zero index.</span>")
            return
        # the axis belongs to the pillar; the force on the top face is reversed in compression
        sign = 1 if self.tension.isChecked() else -1
        action = "pulls out of the pillar" if sign > 0 else "pushes into the pillar"

        def bracket(values, signed=1, form="[{}]"):
            return pretty(form.format(" ".join(str(signed * value) for value in values)))

        if not self._hexagonal():
            text = "Loading axis (top-face normal) " + bracket(indices)
            force = "∥ " + bracket(indices, sign)
        else:
            four = tuple(spin.value() for spin in self.index_spins)
            if self.kind.currentData() == DIRECTION:
                text = ("Loading axis (top-face normal) " + bracket(four)
                        + "  =  three-index " + bracket(indices))
                force = "∥ " + bracket(four, sign)
            else:
                text = "Loading axis (top-face normal) ⟂ " + bracket(four, form="({})")
                force = "⟂ " + bracket(four, sign, "({})")
        self.axis_echo.setText(f"{text}<br>Force on the top face: <i>F</i> ∥ <i>z</i> {force}, {action}")

    def _set_spins(self, values):
        for spin, value in zip(self.index_spins, values):
            spin.blockSignals(True)
            spin.setValue(int(value))
            spin.blockSignals(False)

    def _index_changed(self, *_):
        if self._hexagonal():                       # third index follows from the first two
            first, second = self.index_spins[0].value(), self.index_spins[1].value()
            self.index_spins[2].blockSignals(True)
            self.index_spins[2].setValue(-(first + second))
            self.index_spins[2].blockSignals(False)
        self._echo_axis()
        self._emit()

    def _kind_changed(self, *_):
        self._label_indices()
        self._emit()

    def _preset_chosen(self, index: int):
        values = self.presets.itemData(index)
        self.presets.setCurrentIndex(0)
        if values is None:
            return
        if self._hexagonal():
            self._updating = True
            self.kind.setCurrentIndex(0)
            self._updating = False
            self._set_spins(values)
        else:
            self._set_spins((values[0], values[1], 0, values[2]))
        self._label_indices()
        self._emit()

    def _material_changed(self, *_):
        value = self.material.currentData()
        if value is not None:
            self.c_over_a.blockSignals(True)
            self.c_over_a.setValue(value)
            self.c_over_a.blockSignals(False)
        self._emit()

    def _c_over_a_changed(self, value: float):
        match = self.material.count() - 1           # "custom"
        for index in range(self.material.count() - 1):
            if abs(self.material.itemData(index) - value) < 5e-4:
                match = index
        self.material.blockSignals(True)
        self.material.setCurrentIndex(match)
        self.material.blockSignals(False)
        self._emit()

    def _use_crss_changed(self, checked: bool):
        for _, spin in self._family_rows.values():
            spin.setEnabled(checked)
        self._emit()

    # ------------------------------------------------------------------ interface
    def _indices(self) -> tuple:
        values = tuple(spin.value() for spin in self.index_spins)
        if not self._hexagonal():
            return (values[0], values[1], values[3])
        if not any(values):
            return (0, 0, 0)
        if self.kind.currentData() == DIRECTION:
            return mb_direction_to_miller(values)
        return mb_plane_to_miller(values)

    def inputs(self) -> Inputs:
        hexagonal = self._hexagonal()
        checked = tuple(key for key, (box, _) in self._family_rows.items() if box.isChecked())
        return Inputs(
            structure=self._structure_key(),
            c_over_a=self.c_over_a.value() if hexagonal else 1.0,
            indices=self._indices(),
            kind=self.kind.currentData() if hexagonal else DIRECTION,
            sense=COMPRESSION if self.compression.isChecked() else TENSION,
            family_keys=checked,
            crss={key: spin.value() for key, (_, spin) in self._family_rows.items()},
            use_crss=self.use_crss.isChecked(),
            azimuth=float(self.azimuth.value()),
            stereo=StereoOptions(
                traces=self.show_traces.isChecked(),
                reference_poles=self.show_reference.isChecked(),
                wulff_net=self.show_net.isChecked(),
                circle_45=self.show_circle.isChecked(),
                labels=self.show_labels.isChecked(),
            ),
        )

    def set_axis(self, indices):
        """Set the loading axis from three Miller indices (kind as currently selected)."""
        if not self._hexagonal():
            values = (indices[0], indices[1], 0, indices[2])
        elif self.kind.currentData() == DIRECTION:
            values = miller_to_mb_direction(indices)
        else:
            values = miller_to_mb_plane(indices)
        self._set_spins(values)
        self._echo_axis()
        self._emit()

    def set_structure(self, key: str):
        self.structure.setCurrentIndex(self.structure.findData(key))

    def set_tension(self, tension: bool):
        (self.tension if tension else self.compression).setChecked(True)

    def set_family(self, key: str, checked: bool = True, crss: float = None):
        box, spin = self._family_rows[key]
        box.setChecked(checked)
        if crss is not None:
            spin.setValue(crss)
