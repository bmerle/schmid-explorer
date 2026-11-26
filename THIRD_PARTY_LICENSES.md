# Schmid Explorer 1.4.0 – licence and third-party software

Copyright (C) 2026 Benoit Merle, University of Kassel

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

Licence of the program: GNU General Public License, version 3 or (at your option) any later version (`GPL-3.0-or-later`), see the file `LICENSE` or <https://www.gnu.org/licenses/gpl-3.0.html>.

The program is built on the software listed below, with thanks to its authors. The versions are those of the environment in which this list (and, in the folder of the executable, the executable itself) was created.

## Software used by the program (part of the Windows executable)

| Software | Version | Used for | Licence |
|---|---|---|---|
| [Python](https://www.python.org) | 3.13.11 | interpreter and standard library – The Windows build of Python contains OpenSSL (Apache-2.0), libffi (MIT), Expat (MIT), bzip2 (bzip2-1.0.6), XZ Utils (0BSD), zlib (Zlib), mpdecimal (BSD-2-Clause) and the Microsoft Visual C++ runtime (system library). | PSF-2.0 |
| [Qt 6](https://www.qt.io) | 6.12.0 | graphical user interface – Used as dynamically linked libraries under the LGPL; they can be replaced in the folder of the executable. Qt contains third-party code, see https://doc.qt.io/qt-6/licenses-used-in-qt.html. Source code: https://download.qt.io/official_releases/qt/ | LGPL-3.0-only |
| [PySide6 and Shiboken6 (Qt for Python)](https://www.qt.io/qt-for-python) | 6.12.0 | Python binding of Qt – Source code: https://download.qt.io/official_releases/QtForPython/ | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| [NumPy](https://numpy.org) | 2.4.2 | all calculations | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| [Matplotlib](https://matplotlib.org) | 3.10.8 | all figures and the equations of the help window – Contains the fonts DejaVu (Bitstream Vera and DejaVu licences), STIX (STIX font licence) and Computer Modern (BaKoMa fonts licence). | Matplotlib licence (PSF-based, BSD-compatible) |
| [ContourPy](https://github.com/contourpy/contourpy) | 1.3.3 | contour lines of the orientation map (Matplotlib) | BSD-3-Clause |
| [cycler](https://github.com/matplotlib/cycler) | 0.12.1 | used by Matplotlib | BSD-3-Clause |
| [kiwisolver](https://github.com/nucleic/kiwi) | 1.4.9 | used by Matplotlib | BSD-3-Clause |
| [fontTools](https://github.com/fonttools/fonttools) | 4.61.1 | fonts in exported PDF figures (Matplotlib) | MIT |
| [Pillow](https://python-pillow.github.io) | 12.1.1 | image handling of Matplotlib | MIT-CMU |
| [pyparsing](https://github.com/pyparsing/pyparsing) | 3.3.2 | equation layout of Matplotlib | MIT |
| [packaging](https://github.com/pypa/packaging) | 25.0 | used by Matplotlib | Apache-2.0 OR BSD-2-Clause |
| [python-dateutil](https://github.com/dateutil/dateutil) | 2.9.0.post0 | used by Matplotlib | Apache-2.0 OR BSD-3-Clause |
| [six](https://github.com/benjaminp/six) | 1.17.0 | used by python-dateutil | MIT |
| [pywin32](https://github.com/mhammond/pywin32) | 311 | Windows system interface (executable only) | PSF-2.0 |

## Tools used to test, document and package the program

| Software | Version | Used for | Licence |
|---|---|---|---|
| [PyInstaller](https://pyinstaller.org) | 6.19.0 | builds the Windows executable; its bootloader starts the program – The exception allows the bootloader to be distributed with programs under any licence. | GPL-2.0-or-later WITH Bootloader-exception |
| [ReportLab](https://www.reportlab.com) | 5.0.1 | creates the PDF documentation | BSD-3-Clause |
| [pytest](https://pytest.org) | 9.2.0 | runs the test suite | MIT |

## Independent check (no code used)

| Software | Version | Used for | Licence |
|---|---|---|---|
| [pycotem (F. Mompiou)](https://github.com/mompiou/pycotem) |  | independent check of the calculation: the tests recalculate the Schmid factors with its formulation; no code of pycotem is part of the program | GPL-3.0 |

## Why the GNU GPL, version 3 or later

All components above may be combined in a program under the GPL version 3: the permissive licences (BSD, MIT, PSF, Zlib, Matplotlib) and the LGPL-3.0 of Qt and PySide6 are compatible with it, and so is the Apache-2.0 licence (OpenSSL inside Python), which is not compatible with version 2 of the GPL. The exception of PyInstaller allows its bootloader to start programs under any licence.

Qt and PySide6 are used as separate, dynamically linked libraries (LGPL-3.0). Whoever passes the executable on must pass on the folder `licenses` with it and make the source code of the program available under the GPL; the source code of Qt and PySide6 is available at the addresses given above.
