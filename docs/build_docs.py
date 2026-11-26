# SPDX-License-Identifier: GPL-3.0-or-later
"""Build the documentation:  python docs/build_docs.py

Creates docs/SchmidExplorer_Documentation.pdf. Every number in the tables and every figure
is calculated by the program itself while the document is built, so the documentation
describes the current state of the code. Rebuild it after every change of the program.

Option:  --no-screenshots   skip the screenshots of the running program (no display needed;
                            existing screenshot files in docs/figures are then reused).
"""

from __future__ import annotations

import hashlib
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import matplotlib  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.lib.utils import ImageReader  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    BaseDocTemplate, Frame, Image, KeepTogether, PageBreak, PageTemplate, Paragraph, Preformatted,
    Spacer, Table, TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents  # noqa: E402

import doc_figures  # noqa: E402
from schmid_explorer import APP_NAME, AUTHOR, WEBSITE, __version__, third_party  # noqa: E402
from schmid_explorer.core import inverse_pole_figure  # noqa: E402
from schmid_explorer.core.export import to_text  # noqa: E402
from schmid_explorer.core.lattice import mb_direction_to_miller  # noqa: E402
from schmid_explorer.core.schmid import COMPRESSION, Loading, analyse, force_text  # noqa: E402
from schmid_explorer.core.slip_systems import HCP_C_OVER_A, STRUCTURES, slip_systems  # noqa: E402
from schmid_explorer.gui.text import pretty  # noqa: E402

FIGURES = HERE / "figures"
PDF = HERE / "SchmidExplorer_Documentation.pdf"
WIDTH = A4[0] - 4.0 * cm                      # width of the text block
ACCENT = colors.HexColor("#9b0a45")
TAU_C = 'τ<sub size="6.5">CRSS</sub>'
SIGMA_Y = 'σ<sub size="6.5">y</sub>'
RESULT_COLUMNS = {                            # relative widths (cm) of the columns of a results table
    "Rank": 1.0, "Slip family": 2.9, "Plane": 1.6, "Direction": 1.75, "θ (°)": 1.1, "λ (°)": 1.1,
    "cos θ": 1.25, "cos λ": 1.25, "<i>m</i>": 1.25, "CRSS": 1.1, "Yield stress": 1.25, "Activated first": 1.75,
}


# --------------------------------------------------------------------------- fonts and styles
def register_fonts():
    folder = Path(matplotlib.get_data_path()) / "fonts" / "ttf"      # DejaVu: Greek, overbars, ⟨ ⟩
    for name, file in (("Body", "DejaVuSans.ttf"), ("Body-Bold", "DejaVuSans-Bold.ttf"),
                       ("Body-Italic", "DejaVuSans-Oblique.ttf"),
                       ("Body-BoldItalic", "DejaVuSans-BoldOblique.ttf"), ("Mono", "DejaVuSansMono.ttf")):
        pdfmetrics.registerFont(TTFont(name, str(folder / file)))
    pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-Bold", italic="Body-Italic",
                                  boldItalic="Body-BoldItalic")


def styles() -> dict:
    body = ParagraphStyle("Body", fontName="Body", fontSize=9.3, leading=13.4, alignment=TA_JUSTIFY,
                          spaceAfter=5)
    return {
        "body": body,
        "title": ParagraphStyle("Title", fontName="Body-Bold", fontSize=26, leading=32, textColor=ACCENT),
        "subtitle": ParagraphStyle("Subtitle", fontName="Body", fontSize=13, leading=18, spaceAfter=4),
        "h1": ParagraphStyle("H1", fontName="Body-Bold", fontSize=15, leading=19, spaceBefore=14,
                             spaceAfter=7, textColor=ACCENT, keepWithNext=True),
        "h2": ParagraphStyle("H2", fontName="Body-Bold", fontSize=11, leading=14, spaceBefore=9,
                             spaceAfter=4, keepWithNext=True),
        "bullet": ParagraphStyle("Bullet", parent=body, leftIndent=14, bulletIndent=3, spaceAfter=2.5),
        "caption": ParagraphStyle("Caption", fontName="Body-Italic", fontSize=8.2, leading=11,
                                  alignment=TA_CENTER, spaceBefore=3, spaceAfter=9),
        "cell": ParagraphStyle("Cell", fontName="Body", fontSize=8, leading=10.5),
        "box": ParagraphStyle("Box", fontName="Body", fontSize=8.8, leading=12.6),
        "code": ParagraphStyle("Code", fontName="Mono", fontSize=5.7, leading=7.4),
        "toc1": ParagraphStyle("TOC1", fontName="Body-Bold", fontSize=9.5, leading=15),
        "toc2": ParagraphStyle("TOC2", fontName="Body", fontSize=9, leading=13, leftIndent=14),
    }


class Document(BaseDocTemplate):
    """A4 document with running header, page numbers and a table of contents."""

    def __init__(self, path):
        super().__init__(str(path), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                         topMargin=2.1 * cm, bottomMargin=2.0 * cm,
                         title=f"{APP_NAME} – documentation", author=AUTHOR)
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="text",
                      leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates(PageTemplate(id="page", frames=[frame], onPage=self._decorate))

    def _decorate(self, canvas, _doc):
        if canvas.getPageNumber() == 1:
            return
        canvas.saveState()
        canvas.setFont("Body", 7.5)
        canvas.setFillColor(colors.HexColor("#5d646f"))
        top = A4[1] - 1.35 * cm
        canvas.drawString(2 * cm, top, f"{APP_NAME} {__version__} – user guide and theory")
        canvas.drawRightString(A4[0] - 2 * cm, top, "Schmid factor and activation of glide systems")
        canvas.setStrokeColor(colors.HexColor("#b5bac2"))
        canvas.setLineWidth(0.4)
        canvas.line(2 * cm, top - 4, A4[0] - 2 * cm, top - 4)
        canvas.drawCentredString(A4[0] / 2, 1.2 * cm, str(canvas.getPageNumber()))
        canvas.restoreState()

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name in ("H1", "H2"):
            level = 0 if flowable.style.name == "H1" else 1
            key = "sec-" + hashlib.md5(flowable.getPlainText().encode()).hexdigest()[:10]
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(flowable.getPlainText(), key, level=level)
            self.notify("TOCEntry", (level, flowable.getPlainText(), self.page, key))


# --------------------------------------------------------------------------- building blocks
class Builder:
    """Collects the flowables and keeps the numbering of sections, figures and equations."""

    def __init__(self, figures: dict):
        self.figures = figures
        self.s = styles()
        self.story = []
        self._section = [0, 0]
        self._numbers = {"fig": {}, "eq": {}, "tab": {}}

    # ---- numbering
    def _number(self, kind: str, key: str) -> int:
        return self._numbers[kind].setdefault(key, len(self._numbers[kind]) + 1)

    def fig(self, key: str) -> str:
        return f"Figure {self._number('fig', key)}"

    def eq(self, key: str) -> str:
        return f"({self._number('eq', key)})"

    def tab(self, key: str) -> str:
        return f"Table {self._number('tab', key)}"

    # ---- text
    def add(self, *flowables):
        self.story.extend(flowables)

    def h1(self, text: str):
        self._section = [self._section[0] + 1, 0]
        self.add(Paragraph(f"{self._section[0]}  {text}", self.s["h1"]))

    def h2(self, text: str):
        self._section[1] += 1
        self.add(Paragraph(f"{self._section[0]}.{self._section[1]}  {text}", self.s["h2"]))

    def p(self, text: str):
        self.add(Paragraph(text, self.s["body"]))

    def bullets(self, items, numbered: bool = False):
        for number, item in enumerate(items, start=1):
            self.add(Paragraph(item, self.s["bullet"], bulletText=f"{number}." if numbered else "•"))
        self.add(Spacer(1, 3))

    def box(self, title: str, text: str):
        """Tinted box for the exercises."""
        paragraph = Paragraph(f'<font name="Body-Bold" color="#9b0a45">{title}</font>  {text}', self.s["box"])
        table = Table([[paragraph]], colWidths=[WIDTH])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f6eef1")),
            ("LINEBEFORE", (0, 0), (0, -1), 2.2, ACCENT),
            ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        self.add(Spacer(1, 2), table, Spacer(1, 8))

    # ---- equations (matplotlib mathtext, no LaTeX installation needed)
    def equation(self, tex, key: str = None, fontsize: float = 11.5):
        """Numbered display equation; a list of strings gives several lines under one number."""
        images = []
        for line in ([tex] if isinstance(tex, str) else tex):
            line = line.replace(r"\frac", r"\dfrac")                       # full-size fractions
            name = "eq_" + hashlib.md5(f"{line}{fontsize}".encode()).hexdigest()[:12]
            path = FIGURES / f"{name}.png"
            fig = Figure(figsize=(0.1, 0.1))
            fig.text(0, 0, f"${line}$", fontsize=fontsize, math_fontfamily="cm")
            fig.savefig(path, dpi=300, bbox_inches="tight", pad_inches=0.03, transparent=True)
            width, height = ImageReader(str(path)).getSize()
            if images:
                images.append(Spacer(1, 5))
            images.append(Image(str(path), width * 72.0 / 300.0, height * 72.0 / 300.0))
        label = Paragraph(self.eq(key) if key else "", self.s["cell"])
        table = Table([[images, label]], colWidths=[WIDTH - 1.2 * cm, 1.2 * cm])
        table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (0, 0), "CENTER"), ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        self.add(table)

    # ---- figures
    def _image(self, name: str, width: float) -> Image:
        path = self.figures[name]
        pixel_width, pixel_height = ImageReader(str(path)).getSize()
        return Image(str(path), width, width * pixel_height / pixel_width)

    def figure(self, key: str, names, caption: str, width: float = None, frame: bool = False):
        """One image or several images side by side, with a numbered caption."""
        names = [names] if isinstance(names, str) else list(names)
        total = width or WIDTH
        each = total / len(names)
        table = Table([[self._image(name, each - 4) for name in names]], colWidths=[each] * len(names))
        style = [("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                 ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                 ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
        if frame:
            style.append(("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#b5bac2")))
        table.setStyle(TableStyle(style))
        text = Paragraph(f'<font name="Body-BoldItalic">{self.fig(key)}.</font> {caption}', self.s["caption"])
        self.add(KeepTogether([Spacer(1, 4), table, text]))

    # ---- tables
    def table(self, key: str, header, rows, caption: str, widths=None, bold_rows=(), compact: bool = False):
        cell, padding = self.s["cell"], 5
        if compact:                                                        # for tables with many columns
            cell, padding = ParagraphStyle("CellCompact", parent=cell, fontSize=7.3, leading=9.6), 3
        data = [[Paragraph(f'<font name="Body-Bold">{h}</font>', cell) for h in header]]
        for index, row in enumerate(rows):
            wrap = '<font name="Body-Bold">{}</font>' if index in bold_rows else "{}"
            data.append([Paragraph(wrap.format(value), cell) for value in row])
        table = Table(data, colWidths=widths, repeatRows=1, hAlign="CENTER")
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9ebee")),
            ("LINEBELOW", (0, 0), (-1, 0), 0.7, colors.HexColor("#4c535d")),
            ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#c9cdd3")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
            ("LEFTPADDING", (0, 0), (-1, -1), padding), ("RIGHTPADDING", (0, 0), (-1, -1), padding),
        ]
        table.setStyle(TableStyle(style))
        text = Paragraph(f'<font name="Body-BoldItalic">{self.tab(key)}.</font> {caption}', self.s["caption"])
        self.add(KeepTogether([Spacer(1, 4), table, text]))

    def results_table(self, key: str, analysis, caption: str, rows: int = None, family: bool = False,
                      crss: bool = False):
        """Ranked slip systems exactly as the program lists them."""
        lattice = analysis.lattice
        header = ["Rank"] + (["Slip family"] if family else []) + ["Plane", "Direction", "θ (°)", "λ (°)",
                                                                   "cos θ", "cos λ", "<i>m</i>"]
        header += (["CRSS", "Yield stress"] if crss else []) + ["Activated first"]
        body, bold = [], []
        for index, r in enumerate(analysis.results[:rows]):
            line = [str(r.rank)]
            if family:
                line.append(pretty(f"{r.system.family.name}"))
            line += [pretty(lattice.plane_text(r.plane)), pretty(lattice.direction_text(r.direction)),
                     f"{r.theta_deg:.2f}", f"{r.lambda_deg:.2f}", f"{r.cos_theta:.4f}",
                     f"{r.cos_lambda:.4f}", f"{r.m:.4f}"]
            if crss:
                line += [f"{r.crss:g}", f"{r.yield_stress:.4g}"]
            line.append("yes" if r.primary else "")
            body.append(line)
            if r.primary:
                bold.append(index)
        shown = len(body)
        if shown < len(analysis.results):
            caption += f" Only the first {shown} of {len(analysis.results)} systems are listed."
        widths = [RESULT_COLUMNS[name] for name in header]                 # no header word is broken
        scale = min(1.25, WIDTH / (sum(widths) * cm))
        self.table(key, header, body, caption, widths=[w * scale * cm for w in widths], bold_rows=bold,
                   compact=family or crss)


# --------------------------------------------------------------------------- content
def build_story(figures: dict) -> list:
    d = Builder(figures)
    s = d.s

    def plane(analysis, result) -> str:
        return pretty(analysis.lattice.plane_text(result.plane))

    def direction(analysis, result) -> str:
        return pretty(analysis.lattice.direction_text(result.direction))

    def system(analysis, result) -> str:
        return plane(analysis, result) + direction(analysis, result)

    def in_triangle(structure: str, axis) -> tuple:
        """Indices of the direction of the standard triangle that is equivalent to the loading axis `axis`."""
        analysis = analyse(structure, Loading(axis))
        return inverse_pole_figure.reduce_loading(analysis.lattice, analysis.loading).indices

    fcc012 = analyse("fcc", Loading((0, 1, 2)))                       # tension, as at program start
    fcc012_compression = analyse("fcc", Loading((0, 1, 2), sense=COMPRESSION))
    best, second = fcc012.results[:2]
    best_compression = fcc012_compression.find(best.plane_key, best.direction_key)
    assert (best.plane, best.direction) == ((1, 1, 1), (-1, 0, 1))    # the example written out in the text
    assert (best_compression.plane, best_compression.direction) == ((-1, -1, -1), (1, 0, -1))
    force012 = pretty(force_text(fcc012_compression.lattice, fcc012_compression.loading))   # in compression
    bcc012 = analyse("bcc", Loading((0, 1, 2)))
    bcc_keys = [f.key for f in STRUCTURES["bcc"].families]
    c_over_a = doc_figures.C_OVER_A_MG
    mg_c = analyse("hcp", Loading((0, 0, 1)), c_over_a=c_over_a)
    mg_axis = mb_direction_to_miller((2, -1, -1, 3))
    mg_schmid = analyse("hcp", Loading(mg_axis), c_over_a=c_over_a)
    mg_crss = analyse("hcp", Loading(mg_axis), c_over_a=c_over_a, crss=doc_figures.CRSS_EXAMPLE, use_crss=True)

    # ================================================================= title page
    d.add(Spacer(1, 2.2 * cm), Paragraph(APP_NAME, s["title"]), Spacer(1, 6),
          Paragraph("Schmid factor and activation of glide systems in single-crystal pillars", s["subtitle"]),
          Paragraph(f"User guide and theory  ·  version {__version__}", s["subtitle"]),
          Paragraph(f'<font size="10">{AUTHOR}  ·  {WEBSITE}</font>', s["subtitle"]), Spacer(1, 0.8 * cm))
    d.add(d._image("gui_main_plain", WIDTH))
    d.add(Spacer(1, 0.8 * cm))
    d.p("Schmid Explorer is a teaching tool for students of mechanical engineering and materials science. "
        "A single-crystal pillar is pulled or compressed along a freely chosen crystal direction, the normal "
        "of its flat top face. The program lists all glide systems of the crystal (fcc, bcc or hcp) together "
        "with their Schmid factors, shows the glide planes in a stereographic projection centred on the "
        "direction of the force and sketches the selected glide plane and slip direction in the pillar.")
    d.p("This document explains the theory behind the program, the conventions it uses, the user interface, "
        "and a number of worked examples that can be reproduced with a few clicks.")
    d.add(PageBreak())

    toc = TableOfContents()
    toc.levelStyles = [s["toc1"], s["toc2"]]
    d.add(Paragraph("Contents", ParagraphStyle("TocTitle", parent=s["h1"])), toc, PageBreak())

    # ================================================================= 1
    d.h1("Purpose and quick start")
    d.p("In a micromechanical test a small column is cut out of one grain of a metal, for instance with a "
        "focused ion beam, and then compressed with the flat end of a nanoindenter tip or pulled with a "
        "gripper. Because the pillar is a single crystal, it does not deform uniformly: it shears along a few "
        "crystallographic planes, and sharp slip steps appear on its surface. Which planes and directions "
        "become active depends only on how the crystal lattice is oriented with respect to the loading axis. "
        "The rule that governs this is Schmid's law, and the quantity that decides is the Schmid factor "
        "<i>m</i>.")
    d.p("With Schmid Explorer you can change the crystal structure and the loading direction and immediately "
        "see the consequences. A first experiment takes less than a minute:")
    d.bullets([
        "Start the program (<font name='Mono'>SchmidExplorer.exe</font>, or "
        "<font name='Mono'>python run_schmid_explorer.py</font> from the source folder). It opens with an fcc "
        f"crystal loaded in tension along {pretty('[012]')}.",
        "Read the table at the bottom: all 12 glide systems are listed, the one with the highest Schmid factor "
        "first. Systems that are activated first are printed in bold.",
        "Look at the stereographic projection. Its centre is the direction of the force. Each coloured circle "
        "is the pole of a glide plane; its colour is the highest Schmid factor on that plane. Click one of "
        "the circles: the plane is drawn into the pillar, and its glide directions appear as squares.",
        "Click one of the squares (or a row of the table). The slip direction <b>b</b> is added to the pillar "
        "sketch together with the angles θ and λ.",
        "Move the <i>Slip step</i> slider below the pillar to see how the crystal shears on this system.",
        f"Switch from <i>Tension</i> to <i>Compression</i>: the force is reversed and now points along "
        f"{force012}, into the pillar. The Schmid factors stay; the projection is redrawn around the new "
        "force direction, and the indices of all planes and slip directions change sign.",
        "Change the indices of the loading axis, or choose <i>Pick on orientation map…</i>, and observe how "
        "the ranking changes. The star in the small inverse pole figure below the index fields shows where "
        "the loading axis lies in the standard triangle of the crystal.",
    ], numbered=True)

    # ================================================================= 2
    d.h1("Theory")
    d.h2("Schmid's law")
    d.p(f"A pillar with the cross-section <i>A</i> is loaded by the force <i>F</i> along its axis "
        f"({d.fig('law')}). The applied normal stress is")
    d.equation(r"\sigma = \frac{F}{A}", "sigma")
    d.p("Plastic deformation of a crystal happens by dislocation glide: a dislocation moves on a glide plane "
        "(slip plane) with the unit normal <b>n</b> and shifts the crystal by its Burgers vector <b>b</b>, "
        "which lies in this plane. Only the shear stress that acts <i>on this plane</i> and <i>in this "
        "direction</i> can move the dislocation. It is called the resolved shear stress τ and follows from two "
        "projections:")
    d.bullets([
        "The glide plane is inclined. If θ is the angle between the force and the plane normal "
        "<b>n</b>, the plane cuts the pillar in an ellipse of the area <i>A</i> / cos θ, which is larger than "
        "the cross-section.",
        "Only a part of the force acts along the glide direction. If λ is the angle between the force and the "
        "glide direction <b>b</b>, this component is <i>F</i> cos λ.",
    ])
    d.p("Shear stress is force per area, therefore")
    d.equation(r"\tau \;=\; \frac{F\,\cos\lambda}{A\,/\cos\theta} \;=\; \sigma\,\cos\theta\,\cos\lambda "
               r"\;=\; m\,\sigma \qquad\mathrm{with}\qquad m = \cos\theta\,\cos\lambda", "schmid")
    d.p(f"The geometric factor <i>m</i> is the <b>Schmid factor</b>. Schmid's law states that a glide system "
        f"starts to operate when its resolved shear stress reaches a critical value, the critical resolved "
        f"shear stress {TAU_C}, which is a property of the material and of the type of glide system. The "
        f"crystal therefore yields at the applied stress")
    d.equation(r"\sigma_y = \frac{\tau_{\mathrm{CRSS}}}{m}", "yield")
    d.p(f"The larger the Schmid factor, the smaller the stress that is needed: among glide systems of the same "
        f"type, <b>the system with the highest Schmid factor is activated first</b>.")
    d.figure("law", ["fcc012_pillar", "fcc012_stereo_system"],
             f"Geometry of Schmid's law for an fcc pillar pulled along {pretty('[012]')}. Left: glide plane "
             f"{plane(fcc012, best)} with its normal <b>n</b>, slip direction <b>b</b> = {direction(fcc012, best)}, "
             "the angle θ between the force <i>F</i> and <b>n</b>, the angle λ between <i>F</i> and <b>b</b>, "
             "and the sense of the resolved shear stress τ. Right: the same glide system in the stereographic "
             "projection of the program, whose centre is the direction of the force.")
    d.p("The two angles are not independent. Because <b>b</b> lies in the glide plane, it is perpendicular to "
        "<b>n</b>, and this requires θ + λ ≥ 90°, i.e. cos λ ≤ sin θ. Hence")
    d.equation(r"m \;=\; \cos\theta\,\cos\lambda \;\leq\; \cos\theta\,\sin\theta \;=\; \frac{1}{2}\sin 2\theta "
               r"\;\leq\; \frac{1}{2}", "bound")
    d.p("The Schmid factor can never exceed 0.5. This maximum is reached when the loading axis, the plane "
        "normal and the glide direction lie in one plane and θ = λ = 45°. The Schmid factor is zero when the "
        "loading axis lies in the glide plane (θ = 90°) or is perpendicular to the glide direction (λ = 90°): "
        "such a system feels no shear stress at all, however high the load.")

    d.h2("From crystallographic indices to the angles")
    d.p("Three unit vectors are needed: the plane normal <b>n</b>, the slip direction <b>b</b> and the "
        "direction <b>f</b> of the force on the flat top face of the pillar. The two cosines are scalar "
        "products:")
    d.equation(r"\cos\theta = \hat{\mathbf{n}}\cdot\hat{\mathbf{f}}, \qquad "
               r"\cos\lambda = \hat{\mathbf{b}}\cdot\hat{\mathbf{f}}, \qquad "
               r"m = \left(\hat{\mathbf{n}}\cdot\hat{\mathbf{f}}\right)\,"
               r"\left(\hat{\mathbf{b}}\cdot\hat{\mathbf{f}}\right)", "dot")
    d.p("The signs of <b>n</b> and <b>b</b> are chosen such that both cosines are positive; this sign "
        "convention is explained in the section on tension and compression below. In cubic crystals the "
        "scalar products are particularly simple, because the direction [<i>uvw</i>] is the vector "
        "(<i>u</i>, <i>v</i>, <i>w</i>) and the normal of the plane (<i>hkl</i>) is the vector "
        "(<i>h</i>, <i>k</i>, <i>l</i>). For a force along [<i>uvw</i>] and the plane (<i>hkl</i>):")
    d.equation(r"\cos\theta = \frac{h\,u + k\,v + l\,w}{\sqrt{h^2+k^2+l^2}\;\sqrt{u^2+v^2+w^2}}", "cubic")
    d.p(f"and likewise for cos λ with the indices of the slip direction. <b>Example:</b> fcc, loading axis "
        f"{pretty('[012]')}, tension: the force acts along {pretty('[012]')}. For the glide system "
        f"{system(fcc012, best)}: cos θ = (1·0 + 1·1 + 1·2) / (√3 · √5) = {best.cos_theta:.4f}, "
        f"cos λ = ((−1)·0 + 0·1 + 1·2) / (√2 · √5) = {best.cos_lambda:.4f}, and "
        f"<i>m</i> = {best.m:.4f}. This is the first row of the table the program shows at start.")
    d.p("For a hexagonal crystal the lattice vectors are neither equally long nor perpendicular, so indices "
        "must first be converted into Cartesian vectors. The program does this for both lattices in the same "
        "way, with the structure matrix <b>D</b> whose columns are the lattice vectors:")
    d.equation(r"\mathbf{f} \parallel \mathbf{D}\,[u\;v\;w]^{T}, \qquad \mathbf{n} \parallel \mathbf{D}^{*}\,(h\;k\;l)^{T}, "
               r"\qquad \mathbf{D}^{*} = \left(\mathbf{D}^{-1}\right)^{T}", "matrix")
    d.p("<b>D</b>* contains the reciprocal lattice vectors; the reciprocal vector with the components "
        "(<i>hkl</i>) is always perpendicular to the plane (<i>hkl</i>). For the cubic lattice <b>D</b> is the "
        "unit matrix. For the hexagonal lattice the program uses")
    d.equation(r"\mathbf{a}_1 = a\,(1,\,0,\,0), \qquad \mathbf{a}_2 = a\left(-\frac{1}{2},\,\frac{\sqrt{3}}{2},\,0\right), "
               r"\qquad \mathbf{c} = c\,(0,\,0,\,1)", "hexbasis")
    d.p("Only angles are needed, so the lattice parameter <i>a</i> drops out and the hexagonal crystal is "
        "fully described by its axial ratio <i>c</i>/<i>a</i>.")

    d.h2("Miller–Bravais indices of hexagonal crystals")
    d.p("Hexagonal directions and planes are usually written with four indices, [<i>uvtw</i>] and "
        "(<i>hkil</i>), which refer to the three basal axes <b>a</b><sub size='6.5'>1</sub>, "
        "<b>a</b><sub size='6.5'>2</sub>, <b>a</b><sub size='6.5'>3</sub> = −(<b>a</b><sub size='6.5'>1</sub> + "
        "<b>a</b><sub size='6.5'>2</sub>) and to <b>c</b>. The third index is redundant, <i>t</i> = −(<i>u</i> + "
        "<i>v</i>) and <i>i</i> = −(<i>h</i> + <i>k</i>), but it makes symmetry-equivalent directions and "
        "planes look alike. The program shows and accepts four indices and calculates internally with three "
        "indices [<i>UVW</i>] and (<i>hkl</i>):")
    d.equation([r"[uvtw] \rightarrow [UVW]:\qquad U = u - t,\quad V = v - t,\quad W = w",
                r"[UVW] \rightarrow [uvtw]:\qquad u = \frac{2U - V}{3},\quad v = \frac{2V - U}{3},\quad "
                r"t = -(u+v),\quad w = W"], "mb")
    d.p(f"For planes the third index is simply left out: (<i>hkil</i>) ↔ (<i>hkl</i>). Common factors are "
        f"removed after the conversion. Examples: {pretty('[2 -1 -1 0]')} = [100] is the axis "
        f"<b>a</b><sub size='6.5'>1</sub>, and {pretty('[2 -1 -1 3]')} = [101]. The program shows both forms "
        "below the index fields.")
    d.p("<b>Caution:</b> in a hexagonal crystal the direction [<i>uvtw</i>] is in general <i>not</i> "
        "perpendicular to the plane with the same indices (it is only for the basal plane and for planes "
        "parallel to <b>c</b>). The loading axis can therefore be entered in two ways: as a crystal direction "
        "[<i>uvtw</i>], or as the plane (<i>hkil</i>) of the flat top face of the pillar, whose normal is then "
        "the loading axis.")

    d.h2("Glide systems of fcc, bcc and hcp crystals")
    d.p("A glide system is the combination of a glide plane and a glide direction lying in it. Dislocations "
        "glide most easily on densely packed planes, and their Burgers vector is the shortest lattice "
        "translation, which points along a close-packed direction. Symmetry-equivalent systems form a slip "
        f"family, written as {{plane}}⟨direction⟩. {d.tab('families')} lists the families that are available in "
        f"the program; {d.fig('cubic')} and {d.fig('hcp')} show one plane of every family.")
    rows = []
    for structure in STRUCTURES.values():
        lattice = structure.lattice(1.633)
        for family in structure.families:
            rows.append([structure.key, pretty(family.name), pretty(family.label), pretty(family.burgers),
                         str(len(slip_systems(lattice, family))), "on" if family.default_on else "off"])
    d.table("families", ["Structure", "Slip family", "Planes and directions", "Burgers vector",
                         "Systems", "At start"], rows,
            "Slip families of the program. A plane and its opposite, or a direction and its opposite, count once.",
            widths=[2.1 * cm, 3.4 * cm, 4.0 * cm, 2.8 * cm, 2.0 * cm, 1.7 * cm])
    d.figure("cubic", "cells_cubic",
             "Glide systems of the cubic structures. fcc: each of the four {111} planes contains three ⟨110⟩ "
             "directions. bcc: the glide direction is always a body diagonal ⟨111⟩; planes of the types {110}, "
             "{112} and {123} contain it.")
    d.bullets([
        "<b>fcc</b> (Al, Cu, Ni, Au, austenitic steels): 4 planes {111} × 3 directions ⟨110⟩ = 12 systems.",
        "<b>bcc</b> (α-Fe, W, Mo, Ta, Nb): the Burgers vector is a/2 ⟨111⟩ (4 directions). Slip is observed on "
        "{110} planes (6 planes × 2 directions = 12 systems), on {112} planes (12 × 1 = 12) and on {123} "
        "planes (24 × 1 = 24), which gives 48 systems in total. Only {110}⟨111⟩ is switched on at start, as "
        "in the lecture; the other two families can be added with their check boxes.",
        "<b>hcp</b> (Mg, Ti, Zr, Zn, Co, Be): the short Burgers vector ⟨a⟩ = a/3 " + pretty("<11-20>") + " lies in "
        "the basal plane and can glide on the basal plane (3 systems), on the three prismatic planes (3) and on "
        "the six pyramidal planes of the first kind (6). None of these produces a strain along the c-axis. This "
        "requires the long Burgers vector ⟨c+a⟩ = 1/3 " + pretty("<11-23>") + ", which glides on pyramidal planes "
        "of the first kind (12 systems) and of the second kind (6 systems).",
    ])
    d.figure("hcp", "cells_hcp",
             "Glide systems of the hexagonal close-packed structure, drawn for the ideal axial ratio c/a = 1.633.")
    presets = ",  ".join(f"{name} {value:.3f}" for name, value in HCP_C_OVER_A.items())
    d.p(f"The inclination of the pyramidal planes, and with it the Schmid factors, depends on the axial ratio "
        f"<i>c</i>/<i>a</i>. The program offers the following values and accepts any other: {presets}. Which "
        f"family glides most easily differs from metal to metal (basal glide in Mg, Zn, Cd, Co and Be, "
        f"prismatic glide in Ti and Zr) and is described by different critical resolved shear stresses, see "
        f"the section on the critical resolved shear stress below.")

    d.h2("How the program counts and orients the glide systems")
    d.bullets([
        "The members of a family are generated by applying all symmetry operations of the crystal (48 for the "
        "cubic point group, 24 for the hexagonal one) to one plane and one direction of the family. A plane "
        "(<i>hkl</i>) is paired with a direction [<i>UVW</i>] if the direction lies in the plane, i.e. if "
        "<i>hU</i> + <i>kV</i> + <i>lW</i> = 0. This test is exact because it uses integers only.",
        "A plane has two opposite normals and a glide direction two opposite senses; all four combinations "
        "belong to the same glide system, which is therefore counted once. Which normal and which sense the "
        "program lists follows from the loading and is the subject of the next section.",
        "The list is sorted by decreasing Schmid factor. All systems whose Schmid factor equals the highest one "
        "(within a numerical tolerance of 10<super size='6.5'>−6</super>) are marked as <i>activated first</i>.",
    ])

    d.h2("Tension and compression: the sign convention")
    d.p(f"The pillar stands on its substrate, and the force acts on its flat top face. A glide plane divides "
        f"the pillar into one part that is attached to the substrate and one part that carries the top face "
        f"and with it the force. The program describes every glide system <b>as seen from the force</b>, with "
        f"four vectors ({d.fig('step')}):")
    d.bullets([
        "<b>l</b>, the <b>loading axis</b>: the outward normal of the top face. Its indices are the ones that "
        "are entered. It belongs to the pillar and does not depend on the sense of the load.",
        "<b>f</b>, the <b>direction of the force</b> on the top face: <b>f</b> = +<b>l</b> in tension (the "
        "force pulls out of the pillar) and <b>f</b> = −<b>l</b> in compression (the force pushes into the "
        f"pillar). For the loading axis {pretty('[012]')} a tensile force acts along {pretty('[012]')} and a "
        f"compressive force along {force012}.",
        "<b>n</b>, the <b>normal of the glide plane</b>: of the two opposite normals the one that lies in the "
        "hemisphere of the force (<b>n</b>·<b>f</b> ≥ 0). In tension it points upwards, towards the top "
        "face, in compression downwards, into the pillar. The indices in the table are those of this normal; "
        f"a plane may therefore appear as {pretty('(-1 -1 1)')} instead of the equivalent "
        f"{pretty('(1 1 -1)')}.",
        "<b>b</b>, the <b>slip direction</b>: the direction in which the part of the pillar that carries the "
        "top face is displaced with respect to the part on the substrate. It is parallel to the Burgers "
        "vector of the dislocations that carry the slip. The loaded part gives way to the force, therefore "
        "<b>b</b>·<b>f</b> ≥ 0: <b>b</b> points upwards in tension and downwards in compression.",
    ])
    d.figure("step", ["fcc012_slip", "fcc012_slip_compression"],
             f"Slip step of an fcc pillar with the loading axis {pretty('[012]')}. Left: tension, system "
             f"{system(fcc012, best)}; the force, <b>n</b> and <b>b</b> point upwards. Right: compression, "
             f"system {system(fcc012_compression, best_compression)}; the force, <b>n</b> and <b>b</b> point "
             "downwards, and the axis x on the substrate is reversed. The glide plane is the same.",
             width=0.82 * WIDTH)
    d.p(f"The angle θ is measured between <b>f</b> and <b>n</b>, the angle λ between <b>f</b> and <b>b</b>. "
        f"With this convention both angles lie between 0° and 90°, both cosines in equation {d.eq('dot')} are "
        f"positive, and 0 ≤ <i>m</i> ≤ 0.5.")
    d.p(f"Schmid's law does not distinguish between tension and compression: reversing the force changes "
        f"neither the angles nor the Schmid factors, the ranking or the systems that are activated first. What "
        f"changes is the sense of the shear, and with it the description: <b>the force, every plane normal "
        f"and every slip direction are reversed</b>. The list for compression is the list for tension with "
        f"all indices of opposite sign. The system that is activated first in the fcc pillar with the loading "
        f"axis {pretty('[012]')} is {system(fcc012, best)} in tension and "
        f"{system(fcc012_compression, best_compression)} in compression: the same glide plane and the same "
        f"line of slip, sheared in the opposite sense.")
    d.p("On which side of the glide plane does the moving part lie? Always on the side that carries the top "
        "face. In tension <b>n</b> points towards the top face, and the loaded part is the one into which "
        "<b>n</b> points. In compression <b>n</b> points into the pillar, towards the substrate, and the "
        "loaded part lies on the opposite side of the plane. In both cases <b>b</b> is the displacement of "
        "the loaded part.")
    d.p("<b>The coordinate system follows the force.</b> The sample axes x, y, z of the program are "
        "right-handed, and z always points along the force <b>f</b>:")
    d.bullets([
        "<b>Tension:</b> z points upwards, out of the top face (z = <b>l</b>); x and y lie in the top face.",
        "<b>Compression:</b> z points downwards, into the pillar (z = −<b>l</b>). The axes are turned by half "
        "a turn about y: y stays, x and z are reversed.",
    ])
    d.equation(r"(x,\;y,\;z)_{\mathrm{compression}} \;=\; (-x,\;\;y,\;-z)_{\mathrm{tension}}", "halfturn")
    d.p("Only the axes turn. The crystal keeps its orientation in the pillar when the sense of the load is "
        "changed, and the pillar sketch keeps the top face at the top; it shows the axes x and y on the "
        "substrate and the force arrow with the label <i>F</i> ∥ <i>z</i>.")
    d.p("A plane normal or a slip direction that is exactly perpendicular to the force (θ = 90° or "
        "λ = 90°, <i>m</i> = 0) lies in neither hemisphere. Such a system feels no shear stress and has no "
        "sense of slip; its indices are the same in tension and in compression.")
    d.p("<b>Slip step.</b> The <i>Slip step</i> slider displaces the part of the pillar that carries the top "
        "face by")
    d.equation(r"\mathbf{u} = s\,\hat{\mathbf{b}}", "step")
    d.p(f"where <i>s</i> runs from 0 to 0.9 pillar radii. Because <b>b</b> follows the force, the top face "
        f"moves up by <i>s</i> cos λ in tension, so that the pillar becomes longer, and down by the same "
        f"amount in compression ({d.fig('step')}). In a real pillar the step is produced by many dislocations that leave the "
        "crystal on the same or on neighbouring parallel planes.")

    d.h2("The stereographic projection")
    d.p(f"Directions in space are difficult to draw. The stereographic projection maps every direction onto a "
        f"point in a circle, without losing angular information ({d.fig('principle')}). Imagine a sphere of "
        f"radius 1 around the crystal, with the axis z pointing to its north pole and the equatorial plane as "
        f"projection plane. A direction in the northern half pierces the sphere in a point <i>P</i>. This "
        f"point is connected with the south pole <i>S</i>; where the connecting line crosses the equatorial "
        f"plane lies the projected point <i>P′</i>. For a unit vector (<i>x</i>, <i>y</i>, <i>z</i>) with "
        f"<i>z</i> ≥ 0, at the angle ρ from the z axis:")
    d.equation(r"X = \frac{x}{1+z},\qquad Y = \frac{y}{1+z},\qquad r = \sqrt{X^2+Y^2} = \tan\frac{\rho}{2}", "stereo")
    d.p(f"The z axis itself is projected onto the centre, and all directions perpendicular to it onto the "
        f"circle of radius 1, the primitive circle. The projection is looked at from the north, so that z "
        f"points towards the viewer, x to the right and y upwards.")
    d.p(f"In the program <b>z is the direction of the force</b> (see the previous section). The projection "
        f"therefore shows the hemisphere around the force, and its centre is the force itself. By the sign "
        f"convention every plane normal <b>n</b> and every slip direction <b>b</b> lies in this hemisphere, "
        f"so that one projection contains them all: a plane normal appears at the distance tan(θ/2) from the "
        f"centre, a slip direction at the distance tan(λ/2) ({d.fig('principle')}).")
    d.figure("principle", "stereo_principle",
             "Construction of the stereographic projection. The plane normal <i>P</i> and a slip direction "
             "<i>Q</i> of this plane both lie in the hemisphere around the force and are projected from the "
             "opposite pole <i>S</i>. Here θ = 50° and λ = 40°, i.e. <i>m</i> = 0.49.")
    d.p(f"The elements of the projection are ({d.fig('sense')}):")
    d.bullets([
        "<b>Centre</b> (⊙). The centre is the direction of the force on the top face, which points towards "
        f"the viewer. Its label is the crystal direction of the force: {pretty('[012]')} for tension and "
        f"{force012} for compression along the loading axis {pretty('[012]')}.",
        "<b>Direction of view.</b> The viewer looks against the force. In tension the force points out of "
        "the top face: the projection is what one sees when looking from above onto the top face. In "
        "compression the force points into the pillar: the pillar is seen from below, from the side of the "
        "substrate.",
        "<b>Poles of the glide planes</b> (circles) are the plane normals <b>n</b>, at the distance tan(θ/2) "
        "from the centre.",
        "<b>Slip directions</b> (squares) are shown for the selected plane, at the distance tan(λ/2) from "
        "the centre. They lie on the trace of their plane.",
        "<b>The trace of a plane</b> is a circular arc through two opposite points of the primitive circle. "
        "It contains all directions that lie in the plane, each 90° away from the pole.",
        "<b>The primitive circle</b> (outer circle) contains everything that is perpendicular to the force. "
        "A pole or a slip direction on it (θ = 90° or λ = 90°, <i>m</i> = 0) is marked at both ends.",
        "<b>The 45° circle</b> (optional, radius tan 22.5° = 0.414) marks the ideal position: a system has a "
        "high Schmid factor if its pole <i>and</i> its slip direction lie close to this circle, on one line "
        "with the centre and on opposite sides of it.",
        "<b>Orientation.</b> The x and y axes of the projection are the sample axes that are also drawn in "
        "the pillar sketch. The crystal sits in the pillar such that a reference direction ([100] in cubic "
        f"crystals, {pretty('[2 -1 -1 0]')} in hexagonal ones) appears at the bottom of the projection; the "
        "slider <i>Rotation about axis</i> turns the crystal in the pillar about the loading axis. This "
        "rotation changes neither the angles nor the Schmid factors. Seen from above (tension) the "
        "projection turns counter-clockwise, seen from below (compression) clockwise.",
    ])
    d.p(f"<b>From tension to compression.</b> When the force is reversed, the frame turns by half a turn about "
        f"y (equation {d.eq('halfturn')}), and every plotted vector is replaced by its opposite. A normal with "
        f"the components (<i>x</i>, <i>y</i>, <i>z</i>) in tension therefore has the components "
        f"(<i>x</i>, −<i>y</i>, <i>z</i>) in compression: <b>the projection for compression is the projection "
        f"for tension mirrored top to bottom, with all indices of opposite sign</b> ({d.fig('sense')}). The "
        f"distances from the centre, i.e. the angles θ and λ, are the same.")
    d.figure("sense", ["fcc012_stereo_system", "fcc012_stereo_system_compression"],
             f"The same glide system of an fcc pillar with the loading axis {pretty('[012]')} in tension (left, "
             f"{system(fcc012, best)}, view onto the top face) and in compression (right, "
             f"{system(fcc012_compression, best_compression)}, view from below the pillar). The centre is the "
             "direction of the force in both cases.")

    d.h2("Single slip, multiple slip and the orientation map")
    d.p(f"For most loading directions one glide system has a higher Schmid factor than all others: the crystal "
        f"deforms by single slip. For loading directions of high symmetry several systems are equivalent and "
        f"share the highest Schmid factor: they are activated together (multiple slip). {d.fig('map')} shows the "
        f"highest Schmid factor of an fcc crystal for every loading direction. Because of the cubic symmetry "
        f"the pattern repeats 48 times (24 triangles in the upper half shown); it is sufficient to consider "
        f"one standard triangle with the corners [001], [011] and {pretty('[-111]')} (which is equivalent to "
        f"[111]).")
    axes = [(0, 0, 1), (0, 1, 1), (1, 1, 1), (0, 1, 2), (1, 1, 2), (1, 2, 2), (1, 2, 3)]
    where = ["corner", "corner", "corner", "edge [001]–[011]", "edge [001]–[111]", "edge [011]–[111]", "inside"]
    rows = []
    for axis, position in zip(axes, where):
        fcc = analyse("fcc", Loading(axis))
        bcc = analyse("bcc", Loading(axis), family_keys=bcc_keys)
        rows.append([pretty("[" + "".join(map(str, axis)) + "]"), position, str(len(fcc.primary)),
                     f"{fcc.results[0].m:.4f}", str(len(bcc.primary)), f"{bcc.results[0].m:.4f}",
                     pretty(bcc.results[0].system.family.label)])
    d.figure("map", ["fcc_map", "fcc001_stereo"],
             f"Left: orientation map of an fcc crystal – highest Schmid factor as a function of the loading "
             f"direction, with the standard triangle. Right: loading along [001]; eight glide systems on all "
             f"four {{111}} planes share <i>m</i> = {analyse('fcc', Loading((0, 0, 1))).results[0].m:.4f}.")
    d.table("ties", ["Loading axis", "Position in the standard triangle", "fcc: systems activated first",
                     "fcc: highest <i>m</i>", "bcc (48 systems): activated first", "bcc: highest <i>m</i>",
                     "bcc: family"], rows,
            "Number of glide systems that share the highest Schmid factor, calculated by the program. "
            "For bcc all three families were switched on.",
            widths=[1.7 * cm, 3.4 * cm, 2.6 * cm, 1.9 * cm, 2.7 * cm, 1.9 * cm, 2.3 * cm])
    d.p("Inside the triangle an fcc crystal deforms by single slip, on its edges two systems are equivalent, "
        "and in the corners four ([011]), six ([111]) or eight ([001]) systems. The highest Schmid factor of an "
        "fcc crystal varies between 0.272 for [111], the hardest orientation, and 0.5. In the program the "
        "orientation map is opened with <i>Pick on orientation map…</i>; a click on the map sets the loading "
        "axis.")
    d.box("Try it.", "Open the orientation map for fcc and click close to the middle of the standard triangle. "
          "How many systems are activated first? Now choose the presets [001], [011] and [111] and compare the "
          "number of activated systems and the Schmid factor with the table above. Which orientation needs the "
          "highest stress to yield?")

    d.h2("The inverse pole figure")
    for axis in ((1, 2, 3), (3, -1, -2), (-2, 3, 1)):                 # the examples written out in the text
        assert in_triangle("fcc", axis) == (-1, 2, 3)
    assert in_triangle("hcp", mg_axis) == tuple(mg_axis)              # already inside the triangle
    equivalent = pretty("[-123]")
    d.p(f"The orientation map shows that the loading direction never needs the whole sphere: every direction "
        f"is equivalent by symmetry to one direction of the standard triangle. The program uses this to show "
        f"at a glance where the loading axis lies. The small figure below the index fields of the loading "
        f"axis is an inverse pole figure ({d.fig('ipf')}). A pole figure shows directions of the crystal in "
        f"the frame of the sample, as the stereographic projection of the program does with the normals of "
        f"the glide planes. An inverse pole figure does the opposite: it shows a direction of the sample, here "
        f"the loading axis, in the frame of the crystal. It is again a stereographic projection, with [001] "
        f"or [0001] in the centre, of which only the standard triangle is drawn.")
    d.figure("ipf", ["fcc123_ipf", "mg_2113_ipf"],
             f"Inverse pole figures as the program shows them. Left: fcc crystal with the loading axis [123], "
             f"which is equivalent to {equivalent} inside the standard triangle. Right: magnesium with the "
             f"loading axis {pretty('[2 -1 -1 3]')}, which lies on the edge between [0001] and "
             f"{pretty('[2 -1 -1 0]')}.")
    d.p("To find the point, the program applies all symmetry operations <b>R</b> of the crystal to the "
        "loading axis <b>l</b>. Cubic crystals (point group m3̅m) have 48 of them, hexagonal crystals (6/mmm) "
        "24: rotations, mirror planes and the inversion. Of the equivalent directions <b>R</b> <b>l</b> the "
        "program keeps the one inside the triangle. The triangle is bounded by three planes through the "
        "origin, each of which contains two of its corners <b>c</b><sub size='6.5'>1</sub>, "
        "<b>c</b><sub size='6.5'>2</sub> and <b>c</b><sub size='6.5'>3</sub>. A direction lies in the "
        "triangle if it is on the inner side of all three planes:")
    d.equation(r"\hat{\mathbf{l}}' = \mathbf{R}\,\hat{\mathbf{l}} \quad \mathrm{with} \quad "
               r"\hat{\mathbf{l}}'\cdot\mathbf{e}_k \geq 0 \;\; (k = 1, 2, 3), \qquad "
               r"\mathbf{e}_k = \pm\,\frac{\mathbf{c}_i\times\mathbf{c}_j}{|\mathbf{c}_i\times\mathbf{c}_j|}",
               "triangle")
    d.p("Here <b>e</b><sub size='6.5'><i>k</i></sub> is the normal of the plane through the two other corners, "
        "with the sign for which it points to the side of the corner <b>c</b><sub size='6.5'><i>k</i></sub>. "
        f"For cubic crystals the result is a simple rule. The standard triangle with the corners [001], [011] "
        f"and {pretty('[-111]')} contains the directions [<i>uvw</i>] with")
    d.equation(r"w \;\geq\; v \;\geq\; -u \;\geq\; 0", "cubictriangle")
    d.p(f"In words: take the absolute values of the three indices, sort them in ascending order and give the "
        f"first one a minus sign. The loading axis [123] is therefore plotted at {equivalent}, and so are "
        f"{pretty('[3 -1 -2]')}, {pretty('[-2 3 1]')} and all other directions of the family ⟨123⟩, 48 in "
        f"total. If the entered axis lies outside the triangle, the program names the equivalent direction "
        f"inside it. The two are different directions of the crystal, but the crystal looks the same from "
        f"both: the list of Schmid factors is the same, only the indices of the glide systems are exchanged. "
        f"For hexagonal crystals the triangle has the corners [0001], {pretty('[2 -1 -1 0]')} and "
        f"{pretty('[1 0 -1 0]')}. It is a sector of 30° that reaches from the c-axis, on the left of the "
        f"figure, down to the basal plane, the arc on the right.")
    d.p(f"The position of the star tells what kind of slip to expect. For an fcc crystal, a star inside the "
        f"triangle means single slip, a star on an edge two equivalent systems and a star in a corner four, "
        f"six or eight ({d.tab('ties')}). The inversion is one of the symmetry operations, so that <b>l</b> and "
        f"−<b>l</b> are the same point: the star does not move when the load is switched between tension and "
        f"compression, just as the Schmid factors do not change.")
    d.box("Try it.", f"Enter the loading axes [123], {pretty('[3 -1 -2]')} and {pretty('[-2 3 1]')} one after "
          "the other. The star stays where it is, and so do the Schmid factors in the table. Which glide "
          "system is activated first in each case? Then enter [012] and [112]: on which edge of the triangle "
          "does the star lie, and how many systems are activated first?")

    d.h2("Critical resolved shear stress of different slip families")
    d.p(f"Schmid factors can only be compared directly if all systems have the same critical resolved shear "
        f"stress. This holds within one family, but not between families: in magnesium, for instance, basal "
        f"glide needs a far lower shear stress than glide on prismatic or pyramidal planes. If <i>Rank by yield "
        f"stress</i> is switched on, each family gets its own {TAU_C}, and for every system the program "
        f"calculates the applied stress at which it would start to glide,")
    d.equation(r"\sigma_y^{(s)} = \frac{\tau_{\mathrm{CRSS}}^{(s)}}{m^{(s)}}, \qquad "
               r"\sigma_y = \min_{s}\; \sigma_y^{(s)}", "crss")
    d.p(f"The list is then sorted by increasing {SIGMA_Y}, and the system with the lowest value is activated "
        f"first. The values of {TAU_C} can be entered in any unit (MPa, or relative to the easiest family); the "
        f"yield stress is obtained in the same unit. The program contains no material data: the values must "
        f"be taken from the literature for the material, purity and temperature in question.")

    # ================================================================= 3
    d.h1("The program")
    d.h2("Main window")
    d.figure("gui", "gui_main",
             "Main window: (1) settings, (2) pillar sketch, (3) stereographic projection, (4) summary and export "
             "of the table, (5) ranked table of all glide systems.", frame=True)
    d.p("<b>(1) Settings.</b> All inputs are on the left; every change is calculated and drawn immediately. "
        "If the window is too low to show all settings, as can happen for hcp with its five slip families, "
        "the panel can be scrolled.")
    d.bullets([
        "<b>Crystal:</b> structure (fcc, bcc, hcp). For hcp a material can be chosen, which sets the axial "
        "ratio c/a, or c/a is typed in directly.",
        "<b>Loading axis:</b> the crystal direction of the pillar axis, i.e. the outward normal of the flat "
        "top face of the pillar. Enter the indices [<i>uvw</i>], for hcp [<i>uvtw</i>] (the third index is "
        "filled in automatically). For hcp, <i>Given as</i> switches between a crystal direction and the plane "
        "(<i>hkil</i>) of the top face. <i>Presets</i> offers common directions, <i>Pick on orientation map…</i> "
        "opens the orientation map. <i>Tension</i> or <i>Compression</i> sets the sense of the force on the "
        "top face, and with it the direction of the sample axis z. The line below the index fields repeats "
        "the loading axis and gives the crystal direction of the force, e.g. <i>F</i> ∥ <i>z</i> "
        f"{force012} for compression along {pretty('[012]')}.",
        f"<b>Inverse pole figure:</b> the small figure below the loading axis marks the loading axis with a "
        f"star (★) in the standard triangle of the crystal ({d.fig('ipf')}). If the entered axis lies outside "
        f"the triangle, the equivalent direction inside it is given in a second line. The figure has its own "
        f"buttons <i>Copy image</i> and <i>Save as…</i>.",
        "<b>Slip families:</b> the check boxes decide which families are taken into account; the number of "
        "systems is given in brackets. With <i>Rank by yield stress</i> the CRSS fields become active.",
        "<b>Display:</b> rotation of the crystal about the loading axis and the optional elements of the "
        "projection (index labels, low-index reference directions, traces of all glide planes, 45° circle, "
        "Wulff net with 10° divisions).",
    ])
    d.figure("gui_hcp", "gui_hcp",
             f"Magnesium loaded along {pretty('[2 -1 -1 3]')} with a different critical resolved shear stress for "
             "every slip family and a slip step on the basal system that is activated first.", frame=True)
    d.p("<b>(2) Pillar sketch.</b> The pillar stands on its substrate with the top face at the top, in "
        "tension as in compression; the loading tool is not drawn, so that the top face stays visible. The "
        "black arrow above the pillar is the force on the top face, labelled <i>F</i> ∥ <i>z</i> and with its "
        "crystal direction: it points upwards in tension and downwards in compression. The grey arrows on "
        "the substrate are the sample axes x and y. After a plane has been selected, it is drawn in the "
        "colour of its Schmid factor together with its normal <b>n</b> and the angle θ between <i>F</i> and "
        "<b>n</b>; after a direction has been selected, the slip direction <b>b</b>, the angle λ between "
        "<i>F</i> and <b>b</b> and a pair of arrows for the sense of the shear stress τ are added. In "
        "compression <b>n</b> and <b>b</b> point downwards, like the force. The sketch can be turned with the "
        "left mouse button. With <i>Auto view</i> the program chooses a viewing direction from which the "
        "selected plane is seen well. The view depends on the plane only: it is kept while one switches "
        "between the slip directions of this plane, so that the plane visibly stays the same, and changes "
        "when another plane is selected. <i>Reset view</i> returns to it after the pillar has been turned "
        "by hand.")
    d.p("<b>(3) Stereographic projection.</b> The centre (⊙) is the direction of the force, which points "
        "towards the viewer: the pillar is seen from above in tension and from below in compression. Every "
        "circle is the pole of a glide plane, coloured by the highest Schmid factor of the systems on this "
        "plane; a red ring marks the planes of the systems that are activated first. A click on a pole "
        "selects the plane: its trace and its slip directions (squares, each coloured by the Schmid factor of "
        "this plane–direction pair) appear. A click on a square selects the complete glide system; the two "
        "lines from the centre then show θ and λ. A click on the empty background, or the Esc key, clears "
        "the selection. Resting the mouse on a symbol shows its indices and its angle to the force.")
    d.p("<b>(4) and (5) Table.</b> The table lists all glide systems of the active families with the angles, "
        "the two cosines and the Schmid factor, sorted with the system that is activated first at the top "
        "(bold rows). The column <i>Plane</i> gives the indices of the plane normal in the hemisphere of the "
        "force, the column <i>Direction</i> the slip direction of the part of the pillar that carries the top "
        "face. A click on a row selects this system in both figures; conversely, the plane selected in "
        "the projection is highlighted in the table. A click on a column header sorts by that column. The "
        "line above the table states how many systems are activated first and describes the selected system.")

    d.h2("Orientation map")
    d.p(f"The orientation map ({d.fig('gui_map')}, menu <i>View → Orientation map…</i> or Ctrl+M) is a standard "
        "projection of the crystal: [001], respectively [0001], is in the centre, and every point of the disc "
        "is a possible loading direction. The colour shows the highest Schmid factor of the active slip "
        "families for this direction (or, with <i>Rank by yield stress</i>, the lowest yield stress); the white "
        "lines are contours. The star marks the current loading axis. Moving the mouse over the map shows the "
        "nearest direction with small indices; a click makes it the loading axis. <i>Largest index</i> limits "
        "the size of the indices to which a click is rounded, so that the displayed axis is exactly the one "
        "that is calculated.")

    d.h2("Copying and exporting")
    d.bullets([
        "<b>Figures:</b> every figure (pillar sketch, stereographic projection, inverse pole figure, "
        "orientation map) has the "
        "buttons <i>Copy image</i> (bitmap with 300 dpi to the clipboard, ready to paste into a report or a "
        "presentation) and <i>Save as…</i> (PNG, or the vector formats SVG and PDF). The figure is exported as "
        "it is shown, including the selection and the viewing direction.",
        "<b>Table:</b> <i>Copy table</i> puts the complete list on the clipboard as tab-separated text that can "
        "be pasted directly into a spreadsheet. <i>Export CSV…</i> writes a text file. Choose the decimal "
        "separator that your spreadsheet program expects; with the decimal comma the columns of the CSV file "
        "are separated by semicolons, otherwise by commas. With <i>with settings header</i> the crystal, the "
        "loading axis, the sense and direction of the force, the slip families and the sign convention are "
        "written above the table, so that the file documents itself.",
        "The same commands are in the <i>File</i> menu.",
    ])
    d.figure("gui_map", "gui_map", "Orientation map dialog for the fcc crystal.", width=0.55 * WIDTH, frame=True)
    sample = to_text(fcc012, delimiter=";", decimal=",").splitlines()
    d.add(KeepTogether([
        Paragraph("Beginning of an exported file (fcc, loading axis [012], decimal comma):", s["body"]),
        Preformatted("\n".join(sample[:11]) + "\n…", s["code"])]), Spacer(1, 8))

    d.h2("Help window")
    d.p("The program explains itself: <i>Help → Schmid Explorer help</i> (F1) opens a window with the most "
        "important points of this document, so that the executable can be passed on without it. The topics "
        "are listed on the left: quick start, Schmid's law, indices and angles, glide systems, tension and "
        "compression, stereographic projection, single and multiple slip, inverse pole figure, critical "
        "resolved shear stress, the program window, copying and exporting, examples to try, limits of the "
        "model and references. The equations are typeset and the example figures and tables are calculated "
        "by the program when a topic is opened. The window can stay open beside the main window. "
        "<i>Help → Licence and acknowledgements</i> opens the last topic, with the licence of the program "
        "and the list of the software it is built on.")

    # ================================================================= 4
    d.h1("Worked examples")
    d.h2("fcc crystal pulled and compressed along [012]")
    on_plane = fcc012.on_plane(best.plane_key)                        # the three directions of (111)
    others = " and ".join(direction(fcc012, r) for r in on_plane if r.direction_key != best.direction_key)
    d.p(f"Tension along {pretty('[012]')} is the start state of the program; the orientation is the example "
        f"of the lecture. {d.tab('fcc012')} is the complete list. Two systems, {system(fcc012, best)} and "
        f"{system(fcc012, second)}, share the highest Schmid factor {best.m:.4f}, which is close to the "
        f"maximum of 0.5: the pillar deforms by double slip. The two systems are mirror images of each other "
        f"with respect to the (100) plane, which contains the loading axis. In the projection "
        f"({d.fig('fcc012')}) their poles lie close to the 45° circle. All plane normals and all slip "
        f"directions of the list have a positive component along the force {pretty('[012]')}: the part of "
        f"the pillar that carries the top face moves upwards.")
    d.results_table("fcc012", fcc012, f"fcc, loading axis {pretty('[012]')}, tension: all glide systems "
                    f"{{111}}⟨110⟩.")
    d.figure("fcc012", ["fcc012_stereo", "fcc012_stereo_plane"],
             f"fcc, loading axis {pretty('[012]')}, tension. Left: poles of the four {{111}} planes, coloured "
             f"by their highest Schmid factor. Right: after a click on the pole {plane(fcc012, best)}, the trace "
             "of the plane and its three slip directions appear; each is coloured by its own Schmid factor.")
    d.p(f"Now switch to <i>Compression</i>. The force points along {force012}, and this direction becomes "
        f"the centre of the projection. The table keeps its order and all its numbers, but every index "
        f"changes sign: the first system reads {system(fcc012_compression, best_compression)}. In the pillar "
        f"sketch ({d.fig('fcc012c')}) the force, <b>n</b> and <b>b</b> point downwards, and the part that "
        f"carries the top face slides down along <b>b</b>: the pillar becomes shorter.")
    d.figure("fcc012c", ["fcc012_pillar_compression", "fcc012_stereo_system_compression"],
             f"fcc, loading axis {pretty('[012]')}, compression: the system "
             f"{system(fcc012_compression, best_compression)} in the pillar sketch and in the projection, which "
             f"is centred on the force direction {force012} and shows the pillar from below. Compare with "
             f"{d.fig('law')} for tension.")
    d.box("Try it.", f"In tension, select the plane {plane(fcc012, best)} and compare its three slip "
          f"directions. All three have the same θ, because they share the plane. Why does "
          f"{direction(fcc012, best)} have twice the Schmid factor of {others}? Look at their distances from "
          "the centre. Then switch to compression: what happens to the poles and squares, to the indices in "
          "the table and to the Schmid factors?")

    d.h2("bcc crystal loaded along [012]")
    b = bcc012.results[0]
    d.p(f"Switch the structure to bcc. With the family {{110}}⟨111⟩ the list contains exactly the same Schmid "
        f"factors as for fcc ({d.fig('bcc')}, left). This is no coincidence: the Schmid factor is symmetric in "
        f"<b>n</b> and <b>b</b>, and the bcc family {{110}}⟨111⟩ is obtained from the fcc family {{111}}⟨110⟩ "
        f"by exchanging the roles of plane and direction. The system activated first is now "
        f"{pretty(bcc012.lattice.plane_text(b.plane))}{pretty(bcc012.lattice.direction_text(b.direction))} with "
        f"θ = {b.theta_deg:.2f}° and λ = {b.lambda_deg:.2f}°: the two angles of the fcc case, exchanged.")
    bcc001 = analyse("bcc", Loading((0, 0, 1)), family_keys=bcc_keys)
    bcc001_110 = analyse("bcc", Loading((0, 0, 1)))
    d.p(f"Now tick the families {{112}}⟨111⟩ and {{123}}⟨111⟩: the table grows to 48 systems. For "
        f"{pretty('[012]')} the two {{110}} systems remain in front. For a loading axis [001], however, four "
        f"{{112}}⟨111⟩ systems reach <i>m</i> = {bcc001.results[0].m:.4f}, more than the "
        f"{bcc001_110.results[0].m:.4f} of the best {{110}} systems ({d.fig('bcc')}, right). With many slip "
        f"planes around each ⟨111⟩ direction, a bcc crystal always finds a plane close to the plane of highest "
        f"shear stress (pencil glide), and its highest Schmid factor depends less on the orientation than in "
        f"fcc.")
    d.figure("bcc", ["bcc012_stereo", "bcc001_all_stereo"],
             f"bcc. Left: loading axis {pretty('[012]')}, family {{110}}⟨111⟩, system "
             f"{pretty(bcc012.lattice.plane_text(b.plane))}{pretty(bcc012.lattice.direction_text(b.direction))} selected. "
             "Right: loading axis [001] with all 48 systems; a {112}⟨111⟩ system is selected.")

    d.h2("Magnesium loaded along the c-axis")
    ca = [r for r in mg_c.results if r.m > 1e-9]
    zero = len(mg_c.results) - len(ca)
    d.p(f"Choose hcp, the material Mg (c/a = {c_over_a:.3f}) and the preset [0001]. {d.tab('mgc')} shows the "
        f"result: {zero} of the 30 systems have a Schmid factor of exactly zero. These are all the systems "
        f"with an ⟨a⟩ Burgers vector, which is perpendicular to the c-axis (λ = 90°). Only the "
        f"⟨c+a⟩ systems on the pyramidal planes feel a shear stress: six pyramidal II systems with "
        f"<i>m</i> = {mg_c.results[0].m:.4f}, followed by twelve pyramidal I systems with "
        f"<i>m</i> = {mg_c.results[6].m:.4f} ({d.fig('mgc')}). A magnesium crystal loaded along c is therefore "
        f"in a hard orientation, in tension as in compression: it cannot use its easy basal glide at all.")
    d.results_table("mgc", mg_c, f"Mg (c/a = {c_over_a:.3f}), loading axis [0001], all five slip families.",
                    rows=10, family=True)
    d.figure("mgc", ["mg_c_stereo", "mg_c_pillar"],
             "Mg pulled along [0001]. The poles of the basal plane (centre) and of the prismatic planes "
             "(primitive circle) are dark: their Schmid factor is zero. A pyramidal II ⟨c+a⟩ system is selected.")

    d.h2("Magnesium: the highest Schmid factor does not always win")
    first, crss_first = mg_schmid.results[0], mg_crss.results[0]
    basal = next(r for r in mg_schmid.results if r.system.family.key == "hcp_basal_a")
    ratio = ", ".join(f"{pretty(STRUCTURES['hcp'].family(key).name)} {value:g}"
                      for key, value in doc_figures.CRSS_EXAMPLE.items())
    runner_up = next(r for r in mg_crss.results if r.system.family.key != "hcp_basal_a")
    d.p(f"Set the loading axis to {pretty('[2 -1 -1 3]')}. By the Schmid factor alone, two pyramidal I ⟨c+a⟩ "
        f"systems are in front (<i>m</i> = {first.m:.4f}), ahead of the best basal system "
        f"(<i>m</i> = {basal.m:.4f}). Now switch on <i>Rank by yield stress</i> and enter different critical "
        f"resolved shear stresses, for example the relative values {ratio}. These numbers are only an "
        f"illustration of the fact that basal glide in magnesium is far easier than all other glide modes; "
        f"they are not material data. The ranking changes completely ({d.tab('mgcrss')}): the basal system "
        f"{pretty(mg_crss.lattice.plane_text(crss_first.plane))}{pretty(mg_crss.lattice.direction_text(crss_first.direction))} "
        f"yields at {crss_first.yield_stress:.3g} units, long before the first non-basal system "
        f"({runner_up.yield_stress:.4g} units). The orientation maps in {d.fig('mgmap')} show the same for all "
        f"loading directions.")
    d.results_table("mgcrss", mg_crss,
                    f"Mg, loading axis {pretty('[2 -1 -1 3]')}, ranked by yield stress with the illustrative CRSS "
                    "values given in the text.", rows=6, family=True, crss=True)
    d.box("Try it.", "Compare Mg with Ti (c/a = 1.587) for a loading axis in the basal plane, e.g. "
          f"{pretty('[2 -1 -1 0]')}. Which ⟨a⟩ systems have a non-zero Schmid factor? What must the ratio of the "
          "prismatic to the basal CRSS be for prismatic glide to be activated first?")
    d.figure("mgmap", ["mg_map", "mg_map_crss"],
             "Orientation maps of Mg. Left: highest Schmid factor of all 30 systems. Right: lowest yield stress "
             "with the illustrative CRSS values; the crystal is soft wherever basal glide is possible and hard "
             "close to the c-axis and close to the basal plane.")

    # ================================================================= 5
    d.h1("Structure of the code and validation")
    d.h2("Separation of science and user interface")
    d.p("The calculation is strictly separated from the graphical user interface, so that every formula can "
        "be checked, tested and reused without the GUI:")
    d.table("modules", ["Package", "Content", "Depends on"], [
        ["schmid_explorer/core", "lattice.py (structure matrices, index conversion), symmetry.py (point groups), "
         "slip_systems.py (catalogue of slip families), schmid.py (Schmid factors, ranking, CRSS), stereo.py "
         "(sample frame, projection), pillar.py (pillar geometry, slip step), inverse_pole_figure.py "
         "(standard triangle), orientation_map.py, export.py",
         "NumPy"],
        ["schmid_explorer/plotting", "stereo_plot.py, pillar_plot.py, ipf_plot.py, map_plot.py: the four "
         "figures; used by the program and by this documentation. equation.py: typeset equations of the "
         "help window", "Matplotlib"],
        ["schmid_explorer/gui", "windows, widgets and wiring; contains no formulas. help_content.py holds the "
         "text of the help window, help_window.py shows it", "PySide6 (Qt)"],
        ["schmid_explorer/third_party.py", "licence of the program and list of the third-party software "
         "(data only)", "–"],
        ["tests", "automatic tests (pytest)", "pytest"],
        ["docs", "build_docs.py creates this document; all tables and figures are recalculated", "ReportLab"],
        ["packaging", "recipe of the Windows executable; collect_licenses.py (licence texts of the third-party "
         "software), make_source_zip.py (source archive)", "PyInstaller"],
    ], "Layout of the source code.", widths=[4.5 * cm, 9.9 * cm, 2.6 * cm])
    d.p("The calculation can be used directly from Python:")
    d.add(Preformatted(
        "from schmid_explorer.core.schmid import Loading, analyse\n\n"
        "analysis = analyse(\"fcc\", Loading((0, 1, 2)))\n"
        "for r in analysis.results:\n"
        "    print(r.rank, r.plane, r.direction, round(r.m, 4), r.primary)",
        ParagraphStyle("Code2", parent=s["code"], fontSize=7.5, leading=10)), Spacer(1, 8))

    d.h2("Validation")
    d.p("The test suite (run with <font name='Mono'>python -m pytest</font>) checks the scientific core "
        "against independent results:")
    d.bullets([
        "<b>Lecture notebooks.</b> For fcc and bcc with the loading axis [012] the program reproduces the "
        f"Schmid factors, θ and λ of the lecture notebooks ({d.tab('golden')}). The notebooks do not "
        "distinguish tension from compression; they only choose the sense of each direction such that "
        "<i>m</i> is positive.",
        "<b>Sign convention and frame.</b> For every glide system and both senses of the load: "
        "<b>n</b>·<b>f</b> ≥ 0 and <b>b</b>·<b>f</b> ≥ 0; changing the sense reverses the indices of every "
        "plane and every slip direction and leaves the angles, the Schmid factors and the ranking unchanged. "
        "The sample axis z is the force in both senses, the frame for compression is the frame for tension "
        "turned by half a turn about y, and every pole and slip direction is plotted at the distance "
        "tan(θ/2) or tan(λ/2) from the centre.",
        "<b>Independent formulation.</b> The Schmid factors of cubic and hexagonal crystals (Zr, c/a = 1.5925) "
        "are recalculated in the test with the formulation used by the TEM software pycotem (F. Mompiou): "
        "structure matrix and reciprocal matrix, conversion of four-index directions, signed Schmid factor. "
        "Both routes agree for all systems.",
        "<b>Crystallography.</b> Number of systems of every family; every glide direction lies in its glide "
        "plane; Miller–Bravais conversions are reversible; <i>m</i> never exceeds 0.5; for loading along the "
        "c-axis all ⟨a⟩ systems have <i>m</i> = 0.",
        f"<b>Multiplicity.</b> The number of systems activated first for [001], [111], [011], [012] and [123] "
        f"is 8, 6, 4, 2 and 1 ({d.tab('ties')}).",
        "<b>Geometry and export.</b> Projection and back-projection agree; every point of a trace is "
        "perpendicular to its pole; the two parts of the cut pillar have together the volume of the whole "
        "pillar; exported tables can be read back with both decimal separators.",
        f"<b>Inverse pole figure.</b> All symmetry-equivalent directions of a loading axis, cubic and "
        f"hexagonal, are reduced to one and the same point inside the standard triangle; the integer indices "
        f"of this point agree with the rule of equation {d.eq('cubictriangle')}; tension and compression give "
        f"the same point.",
        "<b>Figures.</b> The pillar sketch is drawn for every glide system of all three structures, in "
        "compression and in tension, with and without a slip step; the stereographic projection is drawn "
        "with all optional elements, the orientation map is drawn, and the star of the inverse pole figure "
        "is at the calculated position inside the triangle.",
        "<b>User interface.</b> A test without display builds the main window, switches structures and "
        "families, selects planes and directions, follows the star of the inverse pole figure through changes "
        "of the loading axis and runs every copy and export command. It checks that the automatic view of "
        "the pillar is the same for all slip directions of a plane and changes with the plane, and it opens "
        "every topic of the help window. The typography of "
        "the indices (overbars for negative indices) is tested separately.",
    ])
    reference = [("0.4899", 2), ("0.2449", 6), ("0.1633", 2), ("0.0816", 2)]
    counts = {name: Counter(f"{r.m:.4f}" for r in analysis.results)
              for name, analysis in (("fcc", fcc012), ("bcc", bcc012))}
    d.table("golden", ["Schmid factor <i>m</i>", "Lecture notebooks: number of systems",
                       "Schmid Explorer, fcc {111}⟨110⟩", "Schmid Explorer, bcc {110}⟨111⟩"],
            [[value, str(number), str(counts["fcc"].get(value, 0)), str(counts["bcc"].get(value, 0))]
             for value, number in reference],
            "Loading axis [012]: Schmid factors of the 12 systems compared with the lecture notebooks.",
            widths=[3.2 * cm, 4.6 * cm, 4.4 * cm, 4.4 * cm])

    # ================================================================= 6
    d.h1("Limits of the model")
    d.p("Schmid Explorer answers one question: which glide systems experience the highest resolved shear "
        "stress, and are therefore expected to become active first, in an ideal uniaxial test? Keep in mind "
        "what it does not contain:")
    d.bullets([
        "<b>Schmid's law only.</b> In bcc metals the motion of screw dislocations also depends on stress "
        "components other than the resolved shear stress (non-Schmid effects) and on the sense of shear on "
        "{112} planes (twinning and anti-twinning sense). Real bcc crystals can therefore behave differently "
        "in tension and compression, which the program does not reproduce.",
        "<b>No deformation twinning.</b> Twinning is an important deformation mode of hcp metals loaded along "
        "the c-axis and of some fcc alloys. It is not a glide system and is not considered.",
        "<b>Only the onset of slip.</b> Work hardening, the interaction of glide systems and the rotation of "
        "the crystal lattice during deformation, which changes the Schmid factors, are not modelled.",
        "<b>Ideal test.</b> The stress is assumed to be uniaxial and homogeneous. Friction at the top face, "
        "the lateral constraint by the loading tool, misalignment, the taper of real pillars, bending and "
        "buckling are neglected.",
        f"<b>No material data.</b> The values of {TAU_C} must be supplied by the user. They depend on "
        "material, purity, temperature and, in micropillars, on the pillar diameter.",
        "<b>The slip step is a sketch.</b> It shows the direction and the sense of the shear, not its amount. "
        "A steep glide plane that leaves the pillar through its bottom face would in reality end in the "
        "substrate; the sketch ignores this and lets the sheared part pass through the substrate.",
    ])

    d.h1("References")
    d.bullets([
        "E. Schmid, W. Boas: <i>Kristallplastizität</i>. Springer, Berlin, 1935.",
        "D. Hull, D. J. Bacon: <i>Introduction to Dislocations</i>, 5th edition. Butterworth-Heinemann, Oxford, 2011.",
        "G. Gottstein: <i>Physical Foundations of Materials Science</i>. Springer, Berlin, 2004.",
        "M. H. Yoo: Slip, twinning, and fracture in hexagonal close-packed metals. "
        "<i>Metallurgical Transactions A</i> 12 (1981) 409–418.",
        "M. D. Uchic, D. M. Dimiduk, J. N. Florando, W. D. Nix: Sample dimensions influence strength and "
        "crystal plasticity. <i>Science</i> 305 (2004) 986–989.",
        "F. Mompiou, R.-X. Xie: pycotem: An open source toolbox for online crystal defect characterization "
        "from TEM imaging and diffraction. <i>Journal of Microscopy</i> 282 (2021) 84–97. (Used here only as "
        "an independent check of the calculation.)",
        "B. Merle: lecture slides <i>Schmid factor</i> and the Jupyter notebooks "
        "<font name='Mono'>fcc_schmid.ipynb</font> and <font name='Mono'>bcc_schmid.ipynb</font>, University of "
        "Kassel. (Notation and reference values for the loading axis [012].)",
    ], numbered=True)

    # ================================================================= 8
    d.h1("Licence and acknowledgements")
    d.p(f"<b>{APP_NAME} {__version__}</b> – {third_party.COPYRIGHT}.")
    for paragraph in third_party.NOTICE:
        d.p(paragraph)
    d.p(f"The licence is the {third_party.LICENCE_NAME} (<font name='Mono'>{third_party.LICENCE_ID}</font>, "
        f"{third_party.LICENCE_URL}); its text is in the file <font name='Mono'>LICENSE</font>. Everybody "
        "may use, study, pass on and change the program; whoever passes it on, changed or unchanged, must "
        "do so under the same licence and make the source code available.")
    d.h2("Third-party software")
    d.p(f"The program is built on the software in {d.tab('runtime')}, with thanks to its authors. All of it "
        f"may be combined in a program under version 3 of the GPL: the permissive licences (BSD, MIT, PSF, "
        f"Zlib, Matplotlib) and the LGPL-3.0 of Qt and PySide6 are compatible with it, and so is the "
        f"Apache-2.0 licence of OpenSSL, which is part of Python and which is not compatible with version 2 "
        f"of the GPL. The same list is shown by <i>Help → Licence and acknowledgements</i>.")

    def licence_rows(role):
        return [[c.name, c.use + (f" <i>{c.note}</i>" if c.note else ""), c.licence]
                for c in third_party.components(role)]

    licence_widths = [3.6 * cm, 9.0 * cm, 4.4 * cm]
    d.table("runtime", ["Software", "Used for", "Licence"], licence_rows(third_party.RUNTIME),
            "Software used by the program; it is part of the Windows executable.", widths=licence_widths,
            compact=True)
    d.table("tools", ["Software", "Used for", "Licence"],
            licence_rows(third_party.BUILD) + licence_rows(third_party.REFERENCE),
            "Tools used to test, document and package the program, and the independent check.",
            widths=licence_widths, compact=True)
    d.h2("Passing the program on")
    d.bullets([
        "<b>Executable.</b> Pass on the complete folder <font name='Mono'>SchmidExplorer</font>. It contains "
        "the licence of the program (<font name='Mono'>LICENSE.txt</font>) and the folder "
        "<font name='Mono'>licenses</font> with the list of the third-party software, its versions and its "
        "licence texts; both are created by <font name='Mono'>packaging/build_exe.ps1</font>.",
        "<b>Source code.</b> The GPL requires that everybody who receives the executable can also get the "
        "source code. The build script therefore writes the archive "
        f"<font name='Mono'>SchmidExplorer-{__version__}-source.zip</font>; offer it at the same place as the "
        "executable, or publish the source code in a public repository and name its address.",
        "<b>Qt and PySide6</b> are used under the LGPL as separate libraries in the folder of the "
        "executable, where they can be replaced by other versions. Their source code is available from the "
        "Qt project at the addresses given in the table.",
        "<b>Lecture material.</b> The folder <font name='Mono'>data</font> (lecture slides, notebooks and a "
        "copy of pycotem) is not part of the program and not part of the source archive.",
    ])
    return d.story


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    register_fonts()
    figures = doc_figures.build_all(FIGURES, screenshots="--no-screenshots" not in argv)
    for name in ("gui_main", "gui_main_plain", "gui_hcp", "gui_map"):      # reused when not re-taken
        figures.setdefault(name, FIGURES / f"{name}.png")
    missing = [str(path) for path in figures.values() if not Path(path).exists()]
    if missing:
        print("Missing figures (run once without --no-screenshots):", *missing, sep="\n  ")
        return 1
    Document(PDF).multiBuild(build_story(figures))
    print(f"written: {PDF}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
