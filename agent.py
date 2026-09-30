"""Simple sequential agent. No LangGraph, no hidden chain-of-thought."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from config import DEMO_MACHINE_ID
from image_analysis import analyze_image
from llm import generate_answer
from rag import search_documents
from sensor_analysis import detect_anomalies, load_sensor_frame, summarize_sensors

ProgressFn = Callable[[str], None]

STEPS = (
    "Searching documents",
    "Analyzing sensor data",
    "Analyzing image",
    "Generating answer",
)


def _round(value):
    if value is None:
        return None
    return round(float(value), 3)


def _search_documents(question: str) -> list[dict]:
    hits = search_documents(question)
    chunks = []
    for hit in hits:
        text = " ".join((hit.get("text") or "").split())
        chunks.append(
            {
                "filename": hit.get("filename") or "",
                "page": int(hit.get("page") or 0),
                "text": text[:500],
            }
        )
    return chunks


def _analyze_sensors() -> dict:
    df = load_sensor_frame()
    if df.empty:
        return {"row_count": 0, "stats": [], "anomalies": [], "note": "No sensor CSV loaded."}
    summary = summarize_sensors(df)
    stats_rows = []
    for _, row in summary["stats"].iterrows():
        stats_rows.append(
            {
                "column": row["column"],
                "mean": _round(row["mean"]),
                "minimum": _round(row["minimum"]),
                "maximum": _round(row["maximum"]),
                "standard_deviation": _round(row["standard_deviation"]),
                "missing_values": int(row["missing_values"]),
            }
        )
    anomalies = detect_anomalies(df, method="iqr")
    anomaly_rows = []
    if not anomalies.empty:
        for item in anomalies.head(12).itertuples():
            anomaly_rows.append(
                {
                    "column": item.column,
                    "value": _round(item.value),
                    "detail": item.detail,
                    "timestamp": str(getattr(item, "timestamp", "")),
                }
            )
    return {
        "row_count": summary["row_count"],
        "missing_values": summary["missing_values"],
        "stats": stats_rows,
        "anomalies": anomaly_rows,
        "note": "Numbers were calculated in Python (Pandas/NumPy). Do not recalculate them.",
    }


def _vision_pack(image_result: dict | None) -> dict:
    if not image_result:
        return {"available": False, "note": "No inspection image was analysed for this run."}
    if not image_result.get("ok"):
        return {
            "available": False,
            "note": image_result.get("error") or "Image analysis failed.",
        }
    return {
        "available": True,
        "filename": image_result.get("filename") or "",
        "observations": image_result.get("observations") or [],
        "possible_issues": image_result.get("possible_issues") or [],
        "suggested_checks": image_result.get("suggested_checks") or [],
        "limitations": image_result.get("limitations") or [],
    }


def _analyze_image(
    image_path: str | Path | None,
    image_result: dict | None,
) -> dict:
    """Prefer a fresh path analysis; otherwise reuse a prior result."""
    if image_path:
        path = Path(image_path)
        if path.exists():
            return analyze_image(path)
        return {
            "ok": False,
            "filename": path.name,
            "error": f"Image not found: {path.name}",
            "observations": [],
            "possible_issues": [],
            "suggested_checks": [],
            "limitations": ["Inspection image path was missing."],
        }
    if image_result is not None:
        return image_result
    return {
        "ok": False,
        "filename": "",
        "error": "No inspection image selected.",
        "observations": [],
        "possible_issues": [],
        "suggested_checks": [],
        "limitations": ["No image was supplied to the agent."],
    }


def gather_evidence(question: str, image_result: dict | None = None) -> dict:
    """Build a small evidence pack (used by PDF reports)."""
    return {
        "machine_id": DEMO_MACHINE_ID,
        "question": (question or "").strip(),
        "document_chunks": _search_documents(question),
        "sensor_summary": _analyze_sensors(),
        "image_analysis": _vision_pack(image_result),
    }


def run_agent(
    question: str,
    image_path: str | Path | None = None,
    image_result: dict | None = None,
    on_step: ProgressFn | None = None,
) -> dict:
    """Run the simple 4-step agent. No LangGraph. No chain-of-thought.

    Steps:
    1. Search documents
    2. Analyze sensor data
    3. Analyze image
    4. Combine evidence and call the external LLM
    """
    report = on_step or (lambda _step: None)
    empty = {
        "ok": False,
        "error": "",
        "steps": [],
        "evidence": None,
        "answer": None,
        "image_result": None,
    }
    q = (question or "").strip()
    if not q:
        empty["error"] = "Enter a question first."
        return empty

    completed: list[str] = []

    # 1. Documents
    report(STEPS[0])
    document_evidence = _search_documents(q)
    completed.append(STEPS[0])

    # 2. Sensors
    report(STEPS[1])
    sensor_analysis = _analyze_sensors()
    completed.append(STEPS[1])

    # 3. Image
    report(STEPS[2])
    vision = _analyze_image(image_path, image_result)
    image_analysis = _vision_pack(vision)
    completed.append(STEPS[2])

    # 4. Combine + LLM
    report(STEPS[3])
    evidence = {
        "machine_id": DEMO_MACHINE_ID,
        "question": q,
        "document_chunks": document_evidence,
        "sensor_summary": sensor_analysis,
        "image_analysis": image_analysis,
    }
    answer = generate_answer(
        question=q,
        document_evidence=document_evidence,
        sensor_analysis=sensor_analysis,
        image_analysis=image_analysis,
    )
    completed.append(STEPS[3])

    return {
        "ok": bool(answer.get("ok")),
        "error": answer.get("error") or "",
        "steps": completed,
        "evidence": evidence,
        "answer": answer,
        "image_result": vision,
    }


def ask(question: str, image_result: dict | None = None) -> dict:
    """Compatibility wrapper around run_agent()."""
    return run_agent(question=question, image_result=image_result)
