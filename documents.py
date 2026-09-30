"""PDF upload, PyMuPDF text extraction, and simple chunking. No RAG in this phase."""

from __future__ import annotations

from pathlib import Path

import fitz

from config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    DEMO_DIR,
    DEMO_PDF_NAME,
    DOCUMENTS_DIR,
    IMAGES_DIR,
    SENSORS_DIR,
    ensure_folders,
)

EXPECTED_FILES = [
    {"name": "pump_manual.pdf", "kind": "PDF", "role": "Machine manual"},
    {"name": "maintenance_history.pdf", "kind": "PDF", "role": "Maintenance history"},
    {"name": "inspection_procedure.pdf", "kind": "PDF", "role": "Inspection procedure"},
    {"name": "inspection.jpg", "kind": "Image", "role": "Inspection photo"},
    {"name": "sensor_data.csv", "kind": "CSV", "role": "Sensor history"},
]


def _search_roots() -> list[Path]:
    ensure_folders()
    return [DOCUMENTS_DIR, IMAGES_DIR, SENSORS_DIR, DEMO_DIR]


def find_file(filename: str) -> Path | None:
    for folder in _search_roots():
        path = folder / filename
        if path.exists() and path.is_file():
            return path
    return None


def list_documents() -> list[dict]:
    rows = []
    for item in EXPECTED_FILES:
        path = find_file(item["name"])
        rows.append(
            {
                **item,
                "present": path is not None,
                "path": str(path) if path else "",
                "size_kb": round(path.stat().st_size / 1024, 1) if path else 0,
            }
        )
    extra_names = {item["name"] for item in EXPECTED_FILES}
    for folder in (DOCUMENTS_DIR, IMAGES_DIR, SENSORS_DIR):
        for path in sorted(folder.glob("*")):
            if not path.is_file() or path.name in extra_names or path.name.startswith("."):
                continue
            kind = (
                "PDF"
                if path.suffix.lower() == ".pdf"
                else "Image"
                if path.suffix.lower() in {".jpg", ".jpeg", ".png"}
                else "File"
            )
            rows.append(
                {
                    "name": path.name,
                    "kind": kind,
                    "role": "Uploaded file",
                    "present": True,
                    "path": str(path),
                    "size_kb": round(path.stat().st_size / 1024, 1),
                }
            )
    return rows


def save_upload(filename: str, data: bytes) -> Path:
    ensure_folders()
    suffix = Path(filename).suffix.lower()
    folder = IMAGES_DIR if suffix in {".jpg", ".jpeg", ".png"} else DOCUMENTS_DIR
    if suffix == ".csv":
        folder = SENSORS_DIR
    target = folder / Path(filename).name
    target.write_bytes(data)
    return target


def save_pdf(filename: str, data: bytes) -> Path:
    """Store a PDF under data/documents/."""
    ensure_folders()
    name = Path(filename).name
    if Path(name).suffix.lower() != ".pdf":
        raise ValueError("Only PDF files can be saved here.")
    target = DOCUMENTS_DIR / name
    target.write_bytes(data)
    return target


def demo_pdf_path() -> Path:
    return DEMO_DIR / DEMO_PDF_NAME


def _write_demo_pdf(path: Path, pages: list[str]) -> None:
    doc = fitz.open()
    for text in pages:
        page = doc.new_page(width=595, height=842)
        page.insert_textbox(
            fitz.Rect(54, 54, 541, 788),
            text.strip(),
            fontsize=11,
            fontname="helv",
            align=0,
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path, deflate=True)
    doc.close()


def ensure_demo_pdfs() -> list[Path]:
    """Create missing synthetic demo PDFs. Not real plant documents."""
    ensure_folders()
    specs = {
        "pump_manual.pdf": [
            """PUMP-204  CENTRIFUGAL PROCESS PUMP
Unit 2 - Cooling Water  |  Maintenance Department

1. Purpose
This synthetic demo manual describes daily inspection and basic care for PUMP-204.
It is not a real plant document.

2. Machine data
- Tag: PUMP-204
- Type: horizontal centrifugal, single stage
- Service: cooling-water circulation
- Driver: 18.5 kW induction motor

3. Safety
Isolate electrical supply before opening the coupling guard.
Do not run the pump with the discharge valve fully closed for a long period.
""",
            """4. What to inspect on PUMP-204
Complete this list during a walk-around inspection:

- Coupling guard in place and bolts tight
- Mechanical seal: no heavy leak, no steam, no burnt smell
- Bearing housings: feel for unusual heat; listen for growl or knock
- Baseplate and foundation bolts: no loose nuts, no cracked grout
- Suction and discharge valves: correct position, no leaked packing
- Pressure gauges: suction and discharge readings stable
- Motor fan cover: not blocked; no burnt insulation smell
- Oil level sight glass (if fitted): level between min and max

5. Abnormal sensor readings (demo limits)
Treat these as attention items, not an automatic trip:
- Vibration above 7.0 mm/s
- Bearing / casing temperature above 70 C
- Discharge pressure below 3.5 bar or above 6.5 bar
- Flow below 200 L/min
- Motor current above 28 A

If vibration and temperature rise together with falling flow, inspect the seal,
bearings, and suction strainer first.
""",
            """6. Daily checks
- Record vibration, temperature, pressure, flow, and motor current
- Look for new oil stains under the pump
- Confirm the inspection photo is taken from the drive-end seal area

7. Weekly checks
- Clean the strainer if flow is falling
- Recheck coupling alignment if vibration has stepped up
- Review the last maintenance history for seal or bearing work

8. Demo note
This file is pump_manual.pdf for the INDUSAI student prototype.
Related demo files: maintenance_history.pdf, inspection_procedure.pdf,
inspection.jpg, sensor_data.csv.
""",
        ],
        "maintenance_history.pdf": [
            """PUMP-204 MAINTENANCE HISTORY (SYNTHETIC)
This is a demo record. It is not a real plant log.

2026-06-12  Mechanical seal replaced (drive end).
Reason: visible weepage during walk-around.
Work: new seal kit, alignment check, 30-minute run test.
Result: leak stopped. Vibration 3.1 mm/s after work.

2026-08-03  Suction strainer cleaned.
Reason: flow had drifted down during summer load.
Result: flow returned to the normal band.

2026-09-01  Quarterly visual inspection.
Notes: coupling guard in place. No new oil stains at that date.
Next due: weekly vibration and temperature log.
""",
            """Open items for PUMP-204 (demo)
- Recheck seal area after any vibration step-up above 7.0 mm/s
- Compare current vibration with the 3.1 mm/s post-seal baseline
- If temperature and vibration rise together, inspect bearings and strainer first

Related files: pump_manual.pdf, inspection_procedure.pdf, sensor_data.csv.
""",
        ],
        "inspection_procedure.pdf": [
            """PUMP-204 INSPECTION PROCEDURE (SYNTHETIC)
Walk-around checklist. Not a certified OEM procedure.

Before start
1. Confirm electrical isolation if a guard must be opened.
2. Look from the drive-end seal area (same view as inspection.jpg).

During run (from a safe distance)
3. Coupling guard present and bolts tight.
4. Mechanical seal: no heavy leak, steam, or burnt smell.
5. Bearing housings: unusual heat or growl.
6. Baseplate bolts and grout: no looseness or cracks.
7. Record vibration, temperature, pressure, flow, motor current.

Attention limits (demo only)
- Vibration above 7.0 mm/s
- Temperature above 70 C
- Pressure below 3.5 bar or above 6.5 bar
- Flow below 200 L/min
- Motor current above 28 A
""",
            """If several limits are broken at once
Inspect seal, bearings, and suction strainer before asking for a work order.
Photograph the seal area. Save sensor_data.csv with the investigation.

This file is inspection_procedure.pdf for the INDUSAI student prototype.
""",
        ],
    }
    created = []
    for name, pages in specs.items():
        path = DEMO_DIR / name
        if not path.exists():
            _write_demo_pdf(path, pages)
        created.append(path)
    return created


def copy_demo_pdfs() -> list[Path]:
    """Copy demo PDFs into data/documents/."""
    ensure_demo_pdfs()
    saved = []
    for name in ("pump_manual.pdf", "maintenance_history.pdf", "inspection_procedure.pdf"):
        source = DEMO_DIR / name
        if source.exists():
            saved.append(save_pdf(name, source.read_bytes()))
    return saved


def extract_pdf_text(pdf_path: str | Path) -> dict:
    """Read text from every page of a PDF with PyMuPDF."""
    path = Path(pdf_path)
    doc = fitz.open(path)
    try:
        pages = []
        parts = []
        for index, page in enumerate(doc, start=1):
            text = page.get_text("text") or ""
            pages.append({"page_number": index, "text": text})
            parts.append(text)
        return {
            "filename": path.name,
            "page_count": doc.page_count,
            "text": "\n\n".join(parts).strip(),
            "pages": pages,
        }
    finally:
        doc.close()


def split_into_chunks(
    text: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[str]:
    """Split extracted text into overlapping character chunks."""
    size = CHUNK_SIZE if chunk_size is None else chunk_size
    gap = CHUNK_OVERLAP if overlap is None else overlap
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return []
    step = max(size - gap, 1)
    chunks = []
    start = 0
    n = len(cleaned)
    while start < n:
        end = min(start + size, n)
        if end < n:
            space = cleaned.rfind(" ", start, end)
            if space > start:
                end = space
        piece = cleaned[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        nxt = end - gap
        start = nxt if nxt > start else end
    return chunks


def chunk_pages(filename: str, pages: list[dict]) -> list[dict]:
    """Chunk each PDF page so retrieval can return a page number."""
    records = []
    for page in pages:
        page_no = int(page.get("page_number") or 0)
        for text in split_into_chunks(page.get("text") or ""):
            records.append({"text": text, "filename": filename, "page": page_no})
    return records


def process_pdf(pdf_path: str | Path) -> dict:
    """Extract text and split it into page-aware chunks."""
    extracted = extract_pdf_text(pdf_path)
    records = chunk_pages(extracted["filename"], extracted["pages"])
    return {
        "filename": extracted["filename"],
        "page_count": extracted["page_count"],
        "text": extracted["text"],
        "pages": extracted["pages"],
        "chunks": [item["text"] for item in records],
        "chunk_records": records,
        "saved_path": str(Path(pdf_path).resolve()),
    }
