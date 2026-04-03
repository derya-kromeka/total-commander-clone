from pathlib import Path

import pypdfium2 as pdfium
import pdfplumber
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output" / "pdf"
TMP_DIR = ROOT / "tmp" / "pdfs"
PDF_PATH = OUTPUT_DIR / "total-commander-clone-summary.pdf"
PNG_PATH = TMP_DIR / "total-commander-clone-summary-page-1.png"


CONTENT = {
    "title": "Total Commander Clone",
    "subtitle": "One-page repo summary",
    "what_it_is": (
        "A PyQt5 desktop file manager with a classic dual-pane layout. "
        "The app adds keyboard-driven file operations, bookmarks, batch renaming, "
        "and a library/tag browser on top of local filesystem navigation."
    ),
    "who_its_for": (
        "Primary persona: people who work with many local folders and want a "
        "faster, two-pane alternative to the native file explorer."
    ),
    "features": [
        "Browse left and right folders side by side, then copy or move items between panes.",
        "Use keyboard shortcuts and toolbar actions for rename, delete, refresh, and new folder.",
        "Batch rename files from the active folder with a dedicated dialog.",
        "Save bookmarks and recent paths, with sidebar panels for quick navigation.",
        "Tag library folders and switch a pane into Library Browser mode for filtered browsing.",
        "Toggle hidden files, mirror the active folder to the other pane, and swap pane paths.",
        "Open folders in the native system explorer and integrate with the Windows shell clipboard.",
    ],
    "architecture": [
        "UI shell: `main.py` starts `QApplication`, loads theme/font/settings, and opens `FileManagerApp`.",
        "Main window: `file_manager_app.py` assembles menus, toolbar, status bar, dual panels, bookmarks, and library views.",
        "File browsing: `file_panel.py` provides each pane's address bar, table model, sorting, filtering, drag/drop, and navigation.",
        "Operations layer: `file_operations.py` handles copy/move/delete/rename actions triggered by the UI.",
        "Persistence: `settings_manager.py` reads and writes `settings.json` and `state.json` for window state, panel history, bookmarks, libraries, and tags.",
        "Library metadata: `library_manager.py` stores roots/tags and uses hidden `.tcc_library_root.json` marker files for discovery.",
        "External services/API server: Not found in repo.",
    ],
    "run_steps": [
        "Install Python 3 and the packages in `requirements.txt` (`PyQt5`, `send2trash`).",
        "Windows: run `scripts\\run.bat`, which checks Python/pip, installs requirements, and launches `main.py`.",
        "macOS/Linux: run `bash scripts/install.sh`, then `bash scripts/run.sh`.",
        "Packaged build option: `TotalCommanderClone.spec` is present for PyInstaller builds.",
    ],
}


def wrap_text(text, font_name, font_size, width):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        trial = word if not current else f"{current} {word}"
        if stringWidth(trial, font_name, font_size) <= width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_wrapped(c, text, x, y, width, font_name, font_size, leading, color=colors.black):
    c.setFont(font_name, font_size)
    c.setFillColor(color)
    lines = wrap_text(text, font_name, font_size, width)
    for line in lines:
        c.drawString(x, y, line)
        y -= leading
    return y


def estimate_height(base_font):
    page_w, page_h = A4
    margin = 16 * mm
    content_w = page_w - (2 * margin)
    section_gap = 6
    height = margin
    height += 20
    height += 14
    height += section_gap

    def para_height(text, size):
        lines = wrap_text(text, "Helvetica", size, content_w)
        return len(lines) * (size + 2)

    def bullets_height(items, size):
        total = 0
        bullet_w = 10
        for item in items:
            lines = wrap_text(item, "Helvetica", size, content_w - bullet_w)
            total += len(lines) * (size + 2)
            total += 2
        return total

    sections = [
        ("What it is", para_height(CONTENT["what_it_is"], base_font)),
        ("Who it's for", para_height(CONTENT["who_its_for"], base_font)),
        ("What it does", bullets_height(CONTENT["features"], base_font)),
        ("How it works", bullets_height(CONTENT["architecture"], base_font - 0.3)),
        ("How to run", bullets_height(CONTENT["run_steps"], base_font)),
    ]

    for _, block_h in sections:
        height += 12
        height += 4
        height += block_h
        height += section_gap
    return height


def render_pdf():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    page_w, page_h = A4
    margin = 16 * mm
    content_w = page_w - (2 * margin)

    font_size = 8.8
    while estimate_height(font_size) > page_h - (2 * mm) and font_size > 6.8:
        font_size -= 0.2

    c = canvas.Canvas(str(PDF_PATH), pagesize=A4)
    c.setTitle("Total Commander Clone Summary")
    c.setAuthor("OpenAI Codex")
    c.setSubject("One-page application summary based on repository evidence")

    c.setFillColor(colors.HexColor("#0f172a"))
    c.setFont("Helvetica-Bold", 18)
    y = page_h - margin
    c.drawString(margin, y, CONTENT["title"])

    c.setFillColor(colors.HexColor("#475569"))
    c.setFont("Helvetica", 9)
    y -= 14
    c.drawString(margin, y, CONTENT["subtitle"])

    c.setStrokeColor(colors.HexColor("#cbd5e1"))
    y -= 8
    c.line(margin, y, page_w - margin, y)
    y -= 10

    def heading(text, current_y):
        c.setFillColor(colors.HexColor("#0f172a"))
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin, current_y, text)
        return current_y - 4

    def paragraph(text, current_y):
        return draw_wrapped(
            c,
            text,
            margin,
            current_y - 10,
            content_w,
            "Helvetica",
            font_size,
            font_size + 2,
            colors.HexColor("#111827"),
        ) - 6

    def bullet_list(items, current_y, size):
        bullet_x = margin
        text_x = margin + 10
        for item in items:
            c.setFillColor(colors.HexColor("#2563eb"))
            c.setFont("Helvetica-Bold", size)
            c.drawString(bullet_x, current_y - 10, "-")
            current_y = draw_wrapped(
                c,
                item,
                text_x,
                current_y - 10,
                content_w - 10,
                "Helvetica",
                size,
                size + 2,
                colors.HexColor("#111827"),
            ) - 2
        return current_y - 4

    y = heading("What it is", y)
    y = paragraph(CONTENT["what_it_is"], y)

    y = heading("Who it's for", y)
    y = paragraph(CONTENT["who_its_for"], y)

    y = heading("What it does", y)
    y = bullet_list(CONTENT["features"], y, font_size)

    y = heading("How it works", y)
    y = bullet_list(CONTENT["architecture"], y, font_size - 0.3)

    y = heading("How to run", y)
    y = bullet_list(CONTENT["run_steps"], y, font_size)

    c.setStrokeColor(colors.HexColor("#e2e8f0"))
    c.line(margin, 12 * mm, page_w - margin, 12 * mm)
    c.setFont("Helvetica", 7.5)
    c.setFillColor(colors.HexColor("#64748b"))
    c.drawString(
        margin,
        8.5 * mm,
        "Source basis: repository files only. Missing items are labeled 'Not found in repo' when applicable.",
    )

    c.showPage()
    c.save()


def render_preview():
    pdf = pdfium.PdfDocument(str(PDF_PATH))
    page = pdf[0]
    bitmap = page.render(scale=2.0).to_pil()
    bitmap.save(PNG_PATH)


def extract_text_check():
    with pdfplumber.open(str(PDF_PATH)) as pdf:
        page = pdf.pages[0]
        return page.extract_text() or ""


if __name__ == "__main__":
    render_pdf()
    render_preview()
    extracted = extract_text_check()
    print(f"PDF: {PDF_PATH}")
    print(f"Preview: {PNG_PATH}")
    print(f"Text length: {len(extracted)}")
