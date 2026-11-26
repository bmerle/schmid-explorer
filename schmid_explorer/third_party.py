# SPDX-License-Identifier: GPL-3.0-or-later
"""Licence of the program and of the third-party software it is built on (plain data).

One list for the help window, the PDF documentation and `packaging/collect_licenses.py`,
which copies the licence texts into the folder of the Windows executable.
"""

from __future__ import annotations

from dataclasses import dataclass

LICENCE_NAME = "GNU General Public License, version 3 or (at your option) any later version"
LICENCE_ID = "GPL-3.0-or-later"
LICENCE_URL = "https://www.gnu.org/licenses/gpl-3.0.html"
COPYRIGHT = "Copyright (C) 2026 Benoit Merle, University of Kassel"
NOTICE = (
    "This program is free software: you can redistribute it and/or modify it under the terms of the "
    "GNU General Public License as published by the Free Software Foundation, either version 3 of the "
    "License, or (at your option) any later version.",
    "This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without "
    "even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU "
    "General Public License for more details.",
)

RUNTIME = "runtime"          # imported by the program; part of the Windows executable
BUILD = "build"              # needed to test, document or package the program; not part of it
REFERENCE = "reference"      # no code used


@dataclass(frozen=True)
class Component:
    name: str
    use: str                 # what the program uses it for
    licence: str             # SPDX expression where one exists
    url: str
    role: str = RUNTIME
    distributions: tuple = ()        # names of the installed Python distributions (for the licence texts)
    note: str = ""


COMPONENTS = (
    Component("Python", "interpreter and standard library", "PSF-2.0", "https://www.python.org",
              note="The Windows build of Python contains OpenSSL (Apache-2.0), libffi (MIT), Expat (MIT), "
                   "bzip2 (bzip2-1.0.6), XZ Utils (0BSD), zlib (Zlib), mpdecimal (BSD-2-Clause) and the "
                   "Microsoft Visual C++ runtime (system library)."),
    Component("Qt 6", "graphical user interface", "LGPL-3.0-only", "https://www.qt.io",
              note="Used as dynamically linked libraries under the LGPL; they can be replaced in the "
                   "folder of the executable. Qt contains third-party code, see "
                   "https://doc.qt.io/qt-6/licenses-used-in-qt.html. Source code: "
                   "https://download.qt.io/official_releases/qt/"),
    Component("PySide6 and Shiboken6 (Qt for Python)", "Python binding of Qt",
              "LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only", "https://www.qt.io/qt-for-python",
              distributions=("PySide6", "PySide6_Essentials", "shiboken6"),
              note="Source code: https://download.qt.io/official_releases/QtForPython/"),
    Component("NumPy", "all calculations", "BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0",
              "https://numpy.org", distributions=("numpy",)),
    Component("Matplotlib", "all figures and the equations of the help window",
              "Matplotlib licence (PSF-based, BSD-compatible)", "https://matplotlib.org",
              distributions=("matplotlib",),
              note="Contains the fonts DejaVu (Bitstream Vera and DejaVu licences), STIX (STIX font "
                   "licence) and Computer Modern (BaKoMa fonts licence)."),
    Component("ContourPy", "contour lines of the orientation map (Matplotlib)", "BSD-3-Clause",
              "https://github.com/contourpy/contourpy", distributions=("contourpy",)),
    Component("cycler", "used by Matplotlib", "BSD-3-Clause", "https://github.com/matplotlib/cycler",
              distributions=("cycler",)),
    Component("kiwisolver", "used by Matplotlib", "BSD-3-Clause", "https://github.com/nucleic/kiwi",
              distributions=("kiwisolver",)),
    Component("fontTools", "fonts in exported PDF figures (Matplotlib)", "MIT",
              "https://github.com/fonttools/fonttools", distributions=("fonttools",)),
    Component("Pillow", "image handling of Matplotlib", "MIT-CMU", "https://python-pillow.github.io",
              distributions=("pillow",)),
    Component("pyparsing", "equation layout of Matplotlib", "MIT", "https://github.com/pyparsing/pyparsing",
              distributions=("pyparsing",)),
    Component("packaging", "used by Matplotlib", "Apache-2.0 OR BSD-2-Clause",
              "https://github.com/pypa/packaging", distributions=("packaging",)),
    Component("python-dateutil", "used by Matplotlib", "Apache-2.0 OR BSD-3-Clause",
              "https://github.com/dateutil/dateutil", distributions=("python-dateutil",)),
    Component("six", "used by python-dateutil", "MIT", "https://github.com/benjaminp/six",
              distributions=("six",)),
    Component("pywin32", "Windows system interface (executable only)", "PSF-2.0",
              "https://github.com/mhammond/pywin32", distributions=("pywin32",)),
    Component("PyInstaller", "builds the Windows executable; its bootloader starts the program",
              "GPL-2.0-or-later WITH Bootloader-exception", "https://pyinstaller.org", role=BUILD,
              distributions=("pyinstaller",),
              note="The exception allows the bootloader to be distributed with programs under any licence."),
    Component("ReportLab", "creates the PDF documentation", "BSD-3-Clause", "https://www.reportlab.com",
              role=BUILD, distributions=("reportlab",)),
    Component("pytest", "runs the test suite", "MIT", "https://pytest.org", role=BUILD,
              distributions=("pytest",)),
    Component("pycotem (F. Mompiou)", "independent check of the calculation: the tests recalculate the "
              "Schmid factors with its formulation; no code of pycotem is part of the program",
              "GPL-3.0", "https://github.com/mompiou/pycotem", role=REFERENCE),
)


def components(role: str) -> list:
    return [component for component in COMPONENTS if component.role == role]
