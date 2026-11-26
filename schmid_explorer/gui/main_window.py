# SPDX-License-Identifier: GPL-3.0-or-later
"""Main window: wires the settings, the two figures and the table together."""

from __future__ import annotations

from .. import APP_NAME, AUTHOR, WEBSITE, __version__, third_party
from ..core import stereo
from ..core.export import to_text
from ..core.schmid import Loading, analyse, force_sign
from ..plotting.style import Selection
from .figure_panel import PillarPanel, StereoPanel
from .help_window import HelpWindow
from .orientation_dialog import OrientationDialog
from .qt import BINDING, QAction, Qt, QtCore, QtGui, QtWidgets
from .settings_panel import SettingsPanel
from .systems_table import SystemsTable
from .text import pretty

LICENCE_TOPIC = "Licence and acknowledgements"


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} – Schmid factor and glide systems of a single-crystal pillar")
        self.analysis = None
        self.rotation = None
        self.selection = Selection()
        self._geometry_key = None
        self.map_dialog = None
        self.help_window = None

        self.settings = SettingsPanel()
        self.pillar = PillarPanel()
        self.stereo = StereoPanel()
        self.table = SystemsTable()

        scroll = QtWidgets.QScrollArea()
        scroll.setWidget(self.settings)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(400)
        scroll.setMaximumWidth(460)

        figures = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        figures.addWidget(self.pillar)
        figures.addWidget(self.stereo)
        figures.setSizes([520, 620])

        right = QtWidgets.QSplitter(Qt.Orientation.Vertical)
        right.addWidget(figures)
        right.addWidget(self._table_box())
        right.setSizes([620, 300])
        right.setStretchFactor(0, 3)
        right.setStretchFactor(1, 1)

        central = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        central.addWidget(scroll)
        central.addWidget(right)
        central.setStretchFactor(1, 1)
        self.setCentralWidget(central)
        self._build_menus()
        self.statusBar()

        self.settings.changed.connect(self.recalculate)
        self.settings.pickRequested.connect(self.show_map)
        self.stereo.planeClicked.connect(lambda key: self.select(Selection(plane=tuple(key))))
        self.stereo.directionClicked.connect(
            lambda key: self.select(Selection(plane=self.selection.plane, direction=tuple(key))))
        self.stereo.backgroundClicked.connect(lambda: self.select(Selection()))
        self.table.systemSelected.connect(
            lambda plane, direction: self.select(Selection(plane=plane, direction=direction)))
        for panel in (self.pillar, self.stereo, self.settings.ipf):
            panel.message.connect(self._status)

        self.resize(1500, 940)
        self.recalculate()

    # ------------------------------------------------------------------ construction
    def _table_box(self):
        box = QtWidgets.QWidget()
        self.summary = QtWidgets.QLabel()
        font = self.summary.font()
        font.setBold(True)
        self.summary.setFont(font)
        self.selected_info = QtWidgets.QLabel()
        self.selected_info.setStyleSheet("color: #1b4f9c;")

        self.decimal = QtWidgets.QComboBox()
        self.decimal.addItem("Decimal point  1.23", ".")
        self.decimal.addItem("Decimal comma  1,23", ",")
        self.decimal.setToolTip("Decimal separator of the copied / exported numbers\n"
                                "(choose the one your spreadsheet program expects).")
        if str(QtCore.QLocale.system().decimalPoint()) == ",":
            self.decimal.setCurrentIndex(1)
        self.with_header = QtWidgets.QCheckBox("with settings header")
        self.with_header.setChecked(True)
        self.with_header.setToolTip("Put the crystal, loading axis and slip families above the table.")
        copy = QtWidgets.QPushButton("Copy table")
        copy.setToolTip("Copy the table to the clipboard (tab-separated, pastes into Excel)")
        copy.clicked.connect(self.copy_table)
        export = QtWidgets.QPushButton("Export CSV…")
        export.clicked.connect(lambda: self.export_table())

        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.summary, 1)
        row.addWidget(self.decimal)
        row.addWidget(self.with_header)
        row.addWidget(copy)
        row.addWidget(export)
        layout = QtWidgets.QVBoxLayout(box)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addLayout(row)
        layout.addWidget(self.selected_info)
        layout.addWidget(self.table, 1)
        return box

    def _build_menus(self):
        def action(menu, text, slot, shortcut=None):
            item = QAction(text, self)
            if shortcut:
                item.setShortcut(QtGui.QKeySequence(shortcut))
            item.triggered.connect(lambda *_: slot())
            menu.addAction(item)
            return item

        file_menu = self.menuBar().addMenu("&File")
        action(file_menu, "Copy table", self.copy_table, "Ctrl+Shift+C")
        action(file_menu, "Export table as CSV…", self.export_table, "Ctrl+E")
        file_menu.addSeparator()
        action(file_menu, "Copy pillar sketch", self.pillar.copy_image)
        action(file_menu, "Save pillar sketch…", self.pillar.save_image)
        action(file_menu, "Copy stereographic projection", self.stereo.copy_image)
        action(file_menu, "Save stereographic projection…", self.stereo.save_image)
        action(file_menu, "Copy inverse pole figure", self.settings.ipf.copy_image)
        action(file_menu, "Save inverse pole figure…", self.settings.ipf.save_image)
        file_menu.addSeparator()
        action(file_menu, "Quit", self.close, "Ctrl+Q")

        view_menu = self.menuBar().addMenu("&View")
        action(view_menu, "Orientation map…", self.show_map, "Ctrl+M")
        action(view_menu, "Reset pillar view", self.pillar.reset_view, "Ctrl+R")
        action(view_menu, "Clear selection", lambda: self.select(Selection()), "Esc")

        help_menu = self.menuBar().addMenu("&Help")
        action(help_menu, f"{APP_NAME} help", self.show_help, "F1")
        action(help_menu, "Licence and acknowledgements", lambda: self.show_help(LICENCE_TOPIC))
        help_menu.addSeparator()
        action(help_menu, f"About {APP_NAME}", self.about)

    # ------------------------------------------------------------------ calculation
    def recalculate(self):
        inputs = self.settings.inputs()
        if not inputs.valid:
            self._status("The loading axis needs at least one non-zero index.")
            return
        loading = Loading(inputs.indices, inputs.kind, inputs.sense)
        self.analysis = analyse(inputs.structure, loading, inputs.family_keys, inputs.c_over_a,
                                inputs.crss, inputs.use_crss)
        self.rotation, _ = stereo.sample_frame(self.analysis.lattice, self.analysis.axis,
                                               inputs.azimuth, force_sign(loading.sense))

        previous = self.selection
        if self.selection.plane not in self.analysis.plane_keys():
            self.selection = Selection()
        elif self.selection.direction is not None and \
                self.analysis.find(self.selection.plane, self.selection.direction) is None:
            self.selection = Selection(plane=self.selection.plane)
        geometry_key = (inputs.structure, inputs.c_over_a, inputs.indices, inputs.kind)
        reoriented = geometry_key != self._geometry_key
        self._geometry_key = geometry_key

        self.table.show_analysis(self.analysis, self.selection)
        self.settings.ipf.show_analysis(self.analysis)
        self._draw(selection_changed=reoriented or self.selection != previous,
                   plane_changed=reoriented or self.selection.plane != previous.plane)
        self.summary.setText(self.analysis.summary())
        self._describe_selection()
        if self.map_dialog is not None and self.map_dialog.isVisible():
            self.map_dialog.show_analysis(self.analysis)
        self.statusBar().clearMessage()

    def _draw(self, selection_changed: bool, plane_changed: bool):
        inputs = self.settings.inputs()
        self.stereo.show_analysis(self.analysis, self.rotation, self.selection, inputs.stereo)
        self.pillar.show_analysis(self.analysis, self.rotation, self.selection,
                                  labels=inputs.stereo.labels, selection_changed=selection_changed,
                                  plane_changed=plane_changed)

    def select(self, selection: Selection):
        if self.analysis is None or selection == self.selection:
            return
        if selection.plane is None:
            selection = Selection()
        plane_changed = selection.plane != self.selection.plane
        self.selection = selection
        self.table.set_selection(selection)
        self._draw(selection_changed=True, plane_changed=plane_changed)
        self._describe_selection()

    def _describe_selection(self):
        lattice = self.analysis.lattice
        result = self.analysis.find(self.selection.plane, self.selection.direction)
        if result is not None:
            text = (f"Selected: {pretty(lattice.plane_text(result.plane))}"
                    f"{pretty(lattice.direction_text(result.direction))}   "
                    f"θ = {result.theta_deg:.1f}°,  λ = {result.lambda_deg:.1f}°,  "
                    f"m = {result.m:.4f}  →  τ = {result.m:.3f} σ")
        elif self.selection.plane is not None:
            best = self.analysis.best_on_plane(self.selection.plane)
            text = (f"Selected plane {pretty(lattice.plane_text(best.plane))}:  θ = {best.theta_deg:.1f}°"
                    " – now choose one of its glide directions (■ or table row).")
        else:
            text = "No glide system selected – click a pole in the projection or a row of the table."
        self.selected_info.setText(text)

    # ------------------------------------------------------------------ actions
    def show_map(self):
        if self.analysis is None:
            return
        if self.map_dialog is None:
            self.map_dialog = OrientationDialog(self)
            self.map_dialog.axisPicked.connect(self.settings.set_axis)
            self.map_dialog.panel.message.connect(self._status)
        self.map_dialog.show_analysis(self.analysis)
        self.map_dialog.show()
        self.map_dialog.raise_()

    def table_text(self, delimiter: str) -> str:
        return to_text(self.analysis, delimiter=delimiter, decimal=self.decimal.currentData(),
                       metadata=self.with_header.isChecked())

    def copy_table(self):
        if self.analysis is None:
            return
        QtWidgets.QApplication.clipboard().setText(self.table_text("\t"))
        self._status("Table copied to the clipboard (tab-separated).")

    def export_table(self, path: str = None):
        if self.analysis is None:
            return
        if path is None:
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Export table", "schmid_factors.csv", "CSV file (*.csv);;Text file (*.txt)")
            if not path:
                return
        delimiter = ";" if self.decimal.currentData() == "," else ","
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as handle:   # BOM: Excel reads UTF-8
                handle.write(self.table_text(delimiter))
        except OSError as error:
            QtWidgets.QMessageBox.warning(self, "Export table", f"Could not write the file:\n{error}")
            return
        self._status(f"Table exported: {path}")

    def show_help(self, topic: str = None):
        """Open the help window, on the given topic or where it was left."""
        if self.help_window is None:
            self.help_window = HelpWindow(self)
        if topic is not None:
            self.help_window.show_topic(topic)
        self.help_window.show()
        self.help_window.raise_()

    def about(self):
        QtWidgets.QMessageBox.about(
            self, f"About {APP_NAME}",
            f"<b>{APP_NAME} {__version__}</b><br><br>"
            "Teaching tool for Schmid's law: glide systems and Schmid factors of fcc, bcc and "
            "hcp single crystals in a micropillar compression (or tension) test.<br><br>"
            "τ = m · σ,&nbsp;&nbsp; m = cos θ · cos λ<br><br>"
            "The theory, the conventions and examples are explained in the help (F1).<br><br>"
            f"Author: {AUTHOR}<br>"
            f"<a href='https://{WEBSITE}'>{WEBSITE}</a><br><br>"
            f"{third_party.COPYRIGHT}<br>"
            f"Free software under the {third_party.LICENCE_NAME} ({third_party.LICENCE_ID}); it comes "
            "WITHOUT ANY WARRANTY. See Help → Licence and acknowledgements.<br><br>"
            f"<small>Python · NumPy · Matplotlib · {BINDING} (Qt)</small>")

    def _status(self, text: str):
        self.statusBar().showMessage(text, 8000)
