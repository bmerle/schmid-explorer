# SPDX-License-Identifier: GPL-3.0-or-later
"""Single import point for the Qt binding (PySide6, with PyQt5 as fallback).

Every GUI module imports Qt names from here, so that the binding can be exchanged in
one place. Importing this module also selects the matching matplotlib backend.
"""

from __future__ import annotations

import os

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QAction

    BINDING = "PySide6"
    os.environ["QT_API"] = "pyside6"
except ImportError:                                     # pragma: no cover - fallback
    from PyQt5 import QtCore, QtGui, QtWidgets
    from PyQt5.QtCore import Qt
    from PyQt5.QtCore import pyqtSignal as Signal
    from PyQt5.QtWidgets import QAction

    BINDING = "PyQt5"
    os.environ["QT_API"] = "pyqt5"

import matplotlib

matplotlib.use("QtAgg")

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

__all__ = ["BINDING", "QtCore", "QtGui", "QtWidgets", "Qt", "Signal", "QAction",
           "FigureCanvas", "Figure"]
