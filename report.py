"""PDF report generation with ReportLab (Phase 11)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from config import AI_INFERENCE_LABEL, DEMO_MACHINE_ID, REPORTS_DIR, ensure_folders


def list_reports() -> list[dict]:
    ensure_folders()
    rows = []
    for path in sorted(REPORTS_DIR.glob("*.pdf"), key=lambda item: item.stat().st_mtime, reverse=True):
        rows.append(
            {
                "name": path.name,
                "path": str(path),
                "size_kb": round(path.stat().st_size / 1024, 1),
                "modified": Path(path).stat().st_mtime,
            }
        )
    return rows


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "IndusTitle",
            parent=base["Title"],
            fontSize=16,
            textColor=colors.HexColor("#0B0F14"),
            spaceAfter=6,
        ),
        "h": ParagraphStyle(
            "IndusH",
            parent=base["Heading2"],
            fontSize=12,
            textColor=colors.HexColor("#1A1408"),
            spaceBefore=10,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "IndusBody",
            parent=base["BodyText"],
            fontSize=9,
            leading=12,
        ),
        "mute": ParagraphStyle(
            "IndusMute",
            parent=base["BodyText"],
            fontSize=8,
            textColor=colors.HexColor("#5A4318"),
            leading=11,
        ),
    }


def _escape(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _bullets(items: list[str], style) -> ListFlowable | Paragraph:
    clean = [str(item).strip() for item in items if str(item).strip()]
    if not clean:
        return Paragraph("None recorded.", style)
    return ListFlowable(
        [ListItem(Paragraph(_escape(item), style), leftIndent=8) for item in clean],
        bulletType="bullet",
        leftIndent=12,
    )


def _section(story: list, title: str, styles) -> None:
    story.append(Paragraph(title, styles["h"]))


def _sensor_findings(answer: dict | None, evidence: dict | None) -> list[str]:
    items: list[str] = []
    if answer:
        items.extend(str(x) for x in (answer.get("sensor_findings") or []) if str(x).strip())
    sensor = (evidence or {}).get("sensor_summary") or {}
    for row in sensor.get("anomalies") or []:
        items.append(
            f"{row.get('column')}: {row.get('value')} ({row.get('detail')})"
            + (f" @ {row.get('timestamp')}" if row.get("timestamp") else "")
        )
    if not items and sensor.get("note"):
        items.append(str(sensor["note"]))
    if not items and sensor.get("row_count"):
        items.append(
            f"Rows={sensor.get('row_count')}; missing={sensor.get('missing_values', 0)}; "
            "no anomaly flags listed."
        )
    return items


def _image_findings(image_result: dict | None, evidence: dict | None) -> list[str]:
    items: list[str] = []
    vision = image_result
    pack = (evidence or {}).get("image_analysis") or {}
    if vision and vision.get("ok"):
        items.extend(str(x) for x in (vision.get("observations") or []) if str(x).strip())
        for issue in vision.get("possible_issues") or []:
            items.append(f"Possible issue: {issue}")
    elif pack.get("available"):
        items.extend(str(x) for x in (pack.get("observations") or []) if str(x).strip())
        for issue in pack.get("possible_issues") or []:
            items.append(f"Possible issue: {issue}")
    elif pack.get("note"):
        items.append(str(pack["note"]))
    elif vision and not vision.get("ok"):
        items.append(str(vision.get("error") or "Image analysis failed."))
    return items


def _document_evidence(answer: dict | None, evidence: dict | None) -> list[str]:
    items: list[str] = []
    if answer:
        findings = (
            answer.get("evidence_findings")
            or answer.get("document_findings")
            or []
        )
        items.extend(str(x) for x in findings if str(x).strip())
    chunks = (evidence or {}).get("document_chunks") or []
    for chunk in chunks[:12]:
        text = (chunk.get("text") or "")[:160]
        items.append(f"{chunk.get('filename', '')} p.{chunk.get('page', 0)}: {text}")
    return items


def _suggested_inspection(answer: dict | None, image_result: dict | None) -> list[str]:
    items: list[str] = []
    if answer:
        items.extend(str(x) for x in (answer.get("inspection_checks") or []) if str(x).strip())
        items.extend(str(x) for x in (answer.get("recommendations") or []) if str(x).strip())
    if image_result and image_result.get("ok"):
        items.extend(str(x) for x in (image_result.get("suggested_checks") or []) if str(x).strip())
    return items


def _sources(answer: dict | None, evidence: dict | None) -> list[str]:
    items: list[str] = []
    for cite in (answer or {}).get("citations") or []:
        items.append(
            f"{cite.get('filename', '')} p.{cite.get('page', 0)} — {cite.get('note', '')}"
        )
    if items:
        return items
    for chunk in (evidence or {}).get("document_chunks") or []:
        items.append(f"{chunk.get('filename', '')} p.{chunk.get('page', 0)}")
    return items


def _sensor_stats_table(evidence: dict | None, styles) -> Table | None:
    sensor = (evidence or {}).get("sensor_summary") or {}
    stats = sensor.get("stats") or []
    if not stats:
        return None
    table_data = [["Column", "Mean", "Min", "Max", "Std", "Missing"]]
    for row in stats:
        table_data.append(
            [
                str(row.get("column", "")),
                str(row.get("mean", "")),
                str(row.get("minimum", "")),
                str(row.get("maximum", "")),
                str(row.get("standard_deviation", "")),
                str(row.get("missing_values", "")),
            ]
        )
    table = Table(table_data, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8A84A")),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#243044")),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def generate_report(
    *,
    engineer: str,
    question: str,
    notes: str,
    status: str,
    answer: dict | None,
    evidence: dict | None,
    image_result: dict | None,
    review: dict | None,
    machine_id: str | None = None,
) -> Path:
    """Write an investigation PDF with the Phase 11 sections under data/reports/."""
    ensure_folders()
    machine = machine_id or (evidence or {}).get("machine_id") or DEMO_MACHINE_ID
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = REPORTS_DIR / f"{machine}-report-{stamp}.pdf"
    styles = _styles()

    story: list = [
        Paragraph("INDUSAI investigation report", styles["title"]),
        Paragraph(AI_INFERENCE_LABEL, styles["mute"]),
        Paragraph(
            "Synthetic student demo. Not a certified engineering inspection. "
            "Answers use an external multimodal LLM, not an on-premises model.",
            styles["mute"],
        ),
        Spacer(1, 4 * mm),
    ]

    # Machine
    _section(story, "Machine", styles)
    story.append(Paragraph(_escape(str(machine)), styles["body"]))

    # Investigation
    _section(story, "Investigation", styles)
    story.append(Paragraph(f"<b>Engineer:</b> {_escape(engineer)}", styles["body"]))
    story.append(Paragraph(f"<b>Investigation status:</b> {_escape(status)}", styles["body"]))
    story.append(Paragraph(f"<b>Generated (UTC):</b> {stamp}", styles["body"]))
    if notes:
        story.append(Paragraph(f"<b>Engineer notes:</b> {_escape(notes)}", styles["body"]))

    # Question
    _section(story, "Question", styles)
    story.append(Paragraph(_escape(question or "(none)"), styles["body"]))

    # Summary
    _section(story, "Summary", styles)
    if answer and answer.get("summary"):
        story.append(Paragraph(_escape(str(answer.get("summary"))), styles["body"]))
    else:
        story.append(Paragraph("No AI summary was generated for this report.", styles["body"]))

    # Sensor Findings
    _section(story, "Sensor Findings", styles)
    story.append(_bullets(_sensor_findings(answer, evidence), styles["body"]))
    stats_table = _sensor_stats_table(evidence, styles)
    if stats_table is not None:
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph("Sensor statistics (Python, not LLM)", styles["mute"]))
        story.append(stats_table)

    # Image Findings
    _section(story, "Image Findings", styles)
    story.append(_bullets(_image_findings(image_result, evidence), styles["body"]))

    # Document Evidence
    _section(story, "Document Evidence", styles)
    story.append(_bullets(_document_evidence(answer, evidence), styles["body"]))

    # Suggested Inspection
    _section(story, "Suggested Inspection", styles)
    story.append(_bullets(_suggested_inspection(answer, image_result), styles["body"]))
    if answer and answer.get("missing_evidence"):
        story.append(Paragraph("Missing evidence", styles["mute"]))
        story.append(_bullets(list(answer.get("missing_evidence") or []), styles["body"]))

    # Sources
    _section(story, "Sources", styles)
    story.append(_bullets(_sources(answer, evidence), styles["body"]))

    # Review Status
    _section(story, "Review Status", styles)
    if review:
        rev_status = review.get("status") or review.get("decision") or "pending"
        story.append(Paragraph(f"<b>Status:</b> {_escape(str(rev_status))}", styles["body"]))
        story.append(
            Paragraph(
                f"<b>Requested by:</b> {_escape(str(review.get('user') or review.get('requested_by') or '—'))}",
                styles["body"],
            )
        )
        story.append(
            Paragraph(
                f"<b>Reviewer:</b> {_escape(str(review.get('reviewer') or '—'))}",
                styles["body"],
            )
        )
        if review.get("timestamp") or review.get("created_at"):
            story.append(
                Paragraph(
                    f"<b>Requested at:</b> {_escape(str(review.get('timestamp') or review.get('created_at')))}",
                    styles["body"],
                )
            )
        if review.get("reason"):
            story.append(Paragraph(f"<b>Reason:</b> {_escape(str(review['reason']))}", styles["body"]))
    else:
        story.append(Paragraph("No human review requested.", styles["body"]))

    story.append(Spacer(1, 8 * mm))
    story.append(
        Paragraph(
            "END OF REPORT. Do not treat this file as an approved plant work order.",
            styles["mute"],
        )
    )

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"INDUSAI {machine} report",
        author="INDUSAI prototype",
    )
    doc.build(story)
    return path
