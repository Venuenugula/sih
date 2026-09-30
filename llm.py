"""External multimodal LLM client. API key is read from the environment only."""

from __future__ import annotations

import base64
import json
import re
import time

import httpx

from config import (
    AI_INFERENCE_LABEL,
    LLM_API_BASE_URL,
    LLM_API_KEY,
    LLM_MODEL,
    LLM_TIMEOUT_SECONDS,
    VISION_MODEL,
    llm_configured,
    vision_configured,
)

ANSWER_SYSTEM_PROMPT = f"""You are INDUSAI, a student industrial workbench assistant.
{AI_INFERENCE_LABEL}
You are an external cloud model. You are not an on-premises plant system.

Rules:
- Use only the supplied evidence (question, document chunks, sensor analysis, image analysis).
- Do not invent facts, sensor numbers, manual text, image details, or citations.
- Do not cite a file or page unless it appears in the supplied document evidence.
- Clearly distinguish evidence (what the pack shows) from recommendations (optional next steps).
- Mention missing evidence. If a source was not supplied, say so.
- Do not present suggestions as certified engineering conclusions.
- Never ask for or repeat passwords, API keys, or audit-table contents.

Reply with JSON only, no markdown fences, using exactly these keys:
{{
  "summary": "short recap of the supplied evidence",
  "evidence_findings": ["facts taken only from the supplied evidence"],
  "sensor_findings": ["abnormal or notable sensor facts from the supplied sensor analysis only"],
  "inspection_checks": ["simple physical checks suggested by the supplied evidence"],
  "recommendations": ["suggestions only; not certified conclusions"],
  "missing_evidence": ["what was not in the pack"],
  "citations": [{{"filename": "file.pdf", "page": 1, "note": "must match a supplied chunk"}}]
}}
"""


def _auth_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {LLM_API_KEY.strip()}",
        "Content-Type": "application/json",
    }


def describe_image(image_bytes: bytes, mime: str, prompt: str) -> dict:
    """Send one image + prompt to the external vision model.

    Returns {"ok": True, "text": "..."} or {"ok": False, "error": "..."}.
    Never includes the API key in the result.
    """
    if not vision_configured():
        return {
            "ok": False,
            "error": "Vision API is not configured. Copy .env.example to .env and set LLM_API_KEY, LLM_API_BASE_URL, and VISION_MODEL.",
        }
    if not image_bytes:
        return {"ok": False, "error": "No image data to send."}

    encoded = base64.b64encode(image_bytes).decode("ascii")
    payload = {
        "model": VISION_MODEL,
        "temperature": 0.2,
        "max_tokens": 800,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{encoded}"},
                    },
                ],
            }
        ],
    }

    url = f"{LLM_API_BASE_URL}/chat/completions"
    last_error = "Vision request failed."
    for attempt in range(3):
        try:
            with httpx.Client(timeout=LLM_TIMEOUT_SECONDS) as client:
                response = client.post(url, json=payload, headers=_auth_headers())
        except httpx.TimeoutException:
            return {"ok": False, "error": "Vision API timed out. Try again, or check the network."}
        except httpx.RequestError:
            return {
                "ok": False,
                "error": "Could not reach the vision API. Check LLM_API_BASE_URL and your internet connection.",
            }

        if response.status_code == 429:
            last_error = "Vision API rate-limited (HTTP 429). Try again in a minute."
            time.sleep(8 * (attempt + 1))
            continue

        if response.status_code in {401, 403}:
            detail = ""
            try:
                body = response.json()
                err = body.get("error") or body.get("message") or ""
                detail = f" Provider said: {err}" if err else ""
            except Exception:
                detail = ""
            return {
                "ok": False,
                "error": f"Vision API rejected the request (HTTP {response.status_code}). Check LLM_API_KEY and account credits/licenses.{detail}",
            }
        if response.status_code >= 400:
            detail = ""
            try:
                body = response.json()
                err = body.get("error") or body.get("message") or ""
                detail = f" {err}" if err else ""
            except Exception:
                detail = ""
            return {"ok": False, "error": f"Vision API returned HTTP {response.status_code}.{detail}"}

        try:
            body = response.json()
            text = body["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            return {"ok": False, "error": "Vision API returned a response that could not be read."}

        if not text or not str(text).strip():
            return {"ok": False, "error": "Vision API returned an empty answer."}
        return {"ok": True, "text": str(text)}

    return {"ok": False, "error": last_error}


def chat(messages: list[dict], max_tokens: int = 1200) -> dict:
    """Send a text-only chat request to the external LLM.

    Returns {"ok": True, "text": "..."} or {"ok": False, "error": "..."}.
    Never includes the API key in the result. Do not put secrets in messages.
    """
    if not llm_configured():
        return {
            "ok": False,
            "error": "Text LLM is not configured. Copy .env.example to .env and set LLM_API_KEY, LLM_API_BASE_URL, and LLM_MODEL.",
        }
    if not messages:
        return {"ok": False, "error": "No prompt to send."}

    payload = {
        "model": LLM_MODEL,
        "temperature": 0.2,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    url = f"{LLM_API_BASE_URL}/chat/completions"
    last_error = "LLM request failed."
    for attempt in range(3):
        try:
            with httpx.Client(timeout=LLM_TIMEOUT_SECONDS) as client:
                response = client.post(url, json=payload, headers=_auth_headers())
        except httpx.TimeoutException:
            return {"ok": False, "error": "LLM API timed out. Try again, or check the network."}
        except httpx.RequestError:
            return {
                "ok": False,
                "error": "Could not reach the LLM API. Check LLM_API_BASE_URL and your internet connection.",
            }

        if response.status_code == 429:
            last_error = "LLM API rate-limited (HTTP 429). Try again in a minute."
            time.sleep(8 * (attempt + 1))
            continue

        if response.status_code in {401, 403}:
            detail = ""
            try:
                body = response.json()
                err = body.get("error") or body.get("message") or ""
                detail = f" Provider said: {err}" if err else ""
            except Exception:
                detail = ""
            return {
                "ok": False,
                "error": f"LLM API rejected the request (HTTP {response.status_code}). Check LLM_API_KEY and account credits/licenses in .env provider console.{detail}",
            }
        if response.status_code >= 400:
            detail = ""
            try:
                body = response.json()
                err = body.get("error") or body.get("message") or ""
                detail = f" {err}" if err else ""
            except Exception:
                detail = ""
            return {"ok": False, "error": f"LLM API returned HTTP {response.status_code}.{detail}"}

        try:
            body = response.json()
            text = body["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            return {"ok": False, "error": "LLM API returned a response that could not be read."}

        if not text or not str(text).strip():
            return {"ok": False, "error": "LLM API returned an empty answer."}
        return {"ok": True, "text": str(text)}

    return {"ok": False, "error": last_error}


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _extract_json_object(text: str) -> str:
    blob = (text or "").strip()
    if blob.startswith("```"):
        blob = re.sub(r"^```(?:json)?\s*", "", blob)
        blob = re.sub(r"\s*```$", "", blob)
    start = blob.find("{")
    if start < 0:
        return blob
    # Prefer a complete object when present; otherwise keep from first brace
    # so truncated replies can still be repaired.
    match = re.search(r"\{.*\}", blob[start:], flags=re.DOTALL)
    if match:
        return match.group(0)
    return blob[start:]


def _loads_json_lenient(blob: str) -> dict | None:
    """Parse model JSON; tolerate common truncation by closing open structures."""
    candidates = [blob]
    trimmed = blob.rstrip()
    # Drop a trailing incomplete key/value fragment after the last comma/newline.
    if trimmed and trimmed[-1] not in "{}[]\"":
        cut = max(trimmed.rfind(","), trimmed.rfind("\n"))
        if cut > 0:
            candidates.append(trimmed[:cut])
    for candidate in candidates:
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
        repaired = candidate.rstrip().rstrip(",")
        # Close open quotes if odd number of unescaped quotes.
        if repaired.count('"') % 2 == 1:
            repaired += '"'
        opens = repaired.count("{") - repaired.count("}")
        opens_list = repaired.count("[") - repaired.count("]")
        repaired += "]" * max(0, opens_list) + "}" * max(0, opens)
        try:
            data = json.loads(repaired)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue
    return None


def _regex_string_field(blob: str, key: str) -> str:
    match = re.search(
        rf'"{re.escape(key)}"\s*:\s*"((?:\\.|[^"\\])*)"',
        blob,
        flags=re.DOTALL,
    )
    if not match:
        return ""
    try:
        return json.loads('"' + match.group(1) + '"')
    except Exception:
        return match.group(1).replace('\\"', '"').replace("\\n", "\n")


def _regex_string_list(blob: str, key: str) -> list[str]:
    match = re.search(rf'"{re.escape(key)}"\s*:\s*\[(.*?)\]', blob, flags=re.DOTALL)
    if not match:
        return []
    return [item.strip() for item in re.findall(r'"((?:\\.|[^"\\])*)"', match.group(1)) if item.strip()]


def _parse_answer_json(text: str) -> dict:
    blob = _extract_json_object(text)
    data = _loads_json_lenient(blob)
    if data is None:
        summary = _regex_string_field(blob, "summary") or (blob[:500] if blob else "The model did not return JSON.")
        inspection = _regex_string_list(blob, "inspection_checks")
        recommendations = _regex_string_list(blob, "recommendations")
        if not inspection and recommendations:
            inspection = list(recommendations)
        return {
            "summary": summary,
            "evidence_findings": _regex_string_list(blob, "evidence_findings"),
            "sensor_findings": _regex_string_list(blob, "sensor_findings"),
            "inspection_checks": inspection,
            "recommendations": recommendations,
            "missing_evidence": _regex_string_list(blob, "missing_evidence")
            or ["The model reply could not be fully parsed as JSON."],
            "citations": [],
        }

    findings = _as_list(data.get("evidence_findings"))
    sensor_findings = _as_list(data.get("sensor_findings"))
    if not findings:
        findings = _as_list(data.get("document_findings")) + sensor_findings

    citations = []
    raw_cites = data.get("citations") or []
    if isinstance(raw_cites, list):
        for item in raw_cites:
            if not isinstance(item, dict):
                continue
            citations.append(
                {
                    "filename": str(item.get("filename") or ""),
                    "page": int(item.get("page") or 0),
                    "note": str(item.get("note") or ""),
                }
            )

    inspection_checks = _as_list(data.get("inspection_checks"))
    recommendations = _as_list(data.get("recommendations"))
    if not inspection_checks and recommendations:
        inspection_checks = list(recommendations)

    return {
        "summary": str(data.get("summary") or "").strip(),
        "evidence_findings": findings,
        "sensor_findings": sensor_findings,
        "inspection_checks": inspection_checks,
        "recommendations": recommendations,
        "missing_evidence": _as_list(data.get("missing_evidence")),
        "citations": citations,
    }


def _allowed_citations(document_evidence: list) -> set[tuple[str, int]]:
    allowed = set()
    for chunk in document_evidence or []:
        if not isinstance(chunk, dict):
            continue
        name = str(chunk.get("filename") or "")
        if not name:
            continue
        allowed.add((name, int(chunk.get("page") or 0)))
    return allowed


def _compact_evidence_pack(
    question: str,
    docs: list,
    sensors: dict,
    image: dict,
) -> dict:
    """Shrink the evidence pack so the model reply stays within token limits."""
    doc_rows = []
    for chunk in (docs or [])[:5]:
        if not isinstance(chunk, dict):
            continue
        doc_rows.append(
            {
                "filename": chunk.get("filename"),
                "page": chunk.get("page"),
                "text": str(chunk.get("text") or "")[:350],
            }
        )
    anomalies = []
    for row in (sensors.get("anomalies") or [])[:8]:
        if not isinstance(row, dict):
            continue
        anomalies.append(
            {
                "column": row.get("column"),
                "value": row.get("value"),
                "detail": row.get("detail"),
            }
        )
    sensor_pack = {
        "row_count": sensors.get("row_count"),
        "missing_values": sensors.get("missing_values"),
        "anomalies": anomalies,
        "note": sensors.get("note"),
    }
    image_pack = {
        "available": bool(image.get("available") or image.get("ok")),
        "observations": (image.get("observations") or [])[:5],
        "possible_issues": (image.get("possible_issues") or [])[:5],
        "suggested_checks": (image.get("suggested_checks") or [])[:5],
        "note": image.get("note") or image.get("error") or "",
    }
    return {
        "question": question.strip(),
        "document_evidence": doc_rows,
        "sensor_analysis": sensor_pack,
        "image_analysis": image_pack,
    }


def _local_answer_from_evidence(docs: list, sensors: dict, image: dict, error: str = "") -> dict:
    """Build a usable answer pack from local evidence when the LLM is unavailable."""
    findings = []
    for chunk in docs[:5]:
        if not isinstance(chunk, dict):
            continue
        snippet = str(chunk.get("text") or "").strip().replace("\n", " ")
        if snippet:
            findings.append(f"{chunk.get('filename')} p.{chunk.get('page')}: {snippet[:160]}")
    sensor_findings = [
        f"{a.get('column')}: {a.get('value')} ({a.get('detail')})"
        for a in (sensors.get("anomalies") or [])[:5]
        if isinstance(a, dict)
    ]
    cols = []
    for row in sensors.get("anomalies") or []:
        if isinstance(row, dict) and row.get("column"):
            name = str(row["column"])
            if name not in cols:
                cols.append(name)
    inspection = _as_list(image.get("suggested_checks"))
    if not inspection:
        inspection = [f"Inspect hardware related to sensor '{col}'." for col in cols[:5]]
    citations = []
    for chunk in docs[:3]:
        if not isinstance(chunk, dict) or not chunk.get("filename"):
            continue
        citations.append(
            {
                "filename": str(chunk.get("filename") or ""),
                "page": int(chunk.get("page") or 0),
                "note": "retrieved evidence chunk",
            }
        )
    summary_bits = []
    if sensor_findings:
        summary_bits.append(f"{len(sensor_findings)} abnormal sensor flag(s) in local CSV analysis.")
    if findings:
        summary_bits.append(f"{len(findings)} document chunk(s) retrieved.")
    if image.get("observations") or image.get("available") or image.get("ok"):
        summary_bits.append("Inspection image analysis was included in the evidence pack.")
    return {
        "ok": False,
        "error": error,
        "summary": " ".join(summary_bits) or "Local evidence only; external LLM did not return an answer.",
        "evidence_findings": findings,
        "sensor_findings": sensor_findings,
        "inspection_checks": inspection,
        "recommendations": list(inspection),
        "missing_evidence": ["External LLM answer was unavailable."] if error else [],
        "citations": citations,
    }


def generate_answer(
    question: str,
    document_evidence: list | None = None,
    sensor_analysis: dict | None = None,
    image_analysis: dict | None = None,
) -> dict:
    """Ask the external LLM using only the current-question evidence pack."""
    docs = list(document_evidence or [])
    sensors = sensor_analysis if isinstance(sensor_analysis, dict) else {}
    image = image_analysis if isinstance(image_analysis, dict) else {}
    if not (question or "").strip():
        empty = _local_answer_from_evidence(docs, sensors, image, "Enter a question first.")
        empty["summary"] = ""
        return empty
    if not llm_configured():
        return _local_answer_from_evidence(
            docs,
            sensors,
            image,
            "Text LLM is not configured. Copy .env.example to .env and set LLM_API_KEY, "
            "LLM_API_BASE_URL, and LLM_MODEL.",
        )

    pack = _compact_evidence_pack(question, docs, sensors, image)
    user_content = (
        "Evidence pack for the current question only. "
        "Do not assume you have the rest of the database. "
        "Keep each list short (max 5 items).\n\n"
        + json.dumps(pack, default=str)
    )
    raw = chat(
        [
            {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        max_tokens=2500,
    )
    if not raw.get("ok"):
        return _local_answer_from_evidence(
            docs,
            sensors,
            image,
            raw.get("error") or "LLM request failed.",
        )

    parsed = _parse_answer_json(raw["text"])
    allowed = _allowed_citations(docs)
    kept = []
    dropped = False
    for cite in parsed["citations"]:
        if (cite["filename"], cite["page"]) in allowed:
            kept.append(cite)
        else:
            dropped = True
    parsed["citations"] = kept
    if dropped:
        parsed["missing_evidence"] = parsed["missing_evidence"] + [
            "Dropped citations that were not in the supplied document evidence."
        ]
    # Local fallbacks so Suggested Inspection / sensor findings stay usable
    # when the model truncates or omits list fields.
    if not parsed["inspection_checks"]:
        parsed["inspection_checks"] = _as_list(image.get("suggested_checks"))
    if not parsed["inspection_checks"]:
        cols = []
        for row in sensors.get("anomalies") or []:
            if isinstance(row, dict) and row.get("column"):
                name = str(row["column"])
                if name not in cols:
                    cols.append(name)
        parsed["inspection_checks"] = [
            f"Inspect hardware related to sensor '{col}'." for col in cols[:5]
        ]
    if not parsed["sensor_findings"]:
        anomalies_from_sensors = [
            f"{a.get('column')}: {a.get('value')} ({a.get('detail')})"
            for a in (sensors.get("anomalies") or [])[:5]
            if isinstance(a, dict)
        ]
        if anomalies_from_sensors:
            parsed["sensor_findings"] = anomalies_from_sensors
    if not parsed["citations"]:
        for chunk in docs[:3]:
            if not isinstance(chunk, dict) or not chunk.get("filename"):
                continue
            parsed["citations"].append(
                {
                    "filename": str(chunk.get("filename") or ""),
                    "page": int(chunk.get("page") or 0),
                    "note": "retrieved evidence chunk",
                }
            )
    # Treat a repaired local-style summary that is still raw JSON as a soft failure.
    summary = parsed.get("summary") or ""
    if summary.lstrip().startswith("{") and '"summary"' in summary:
        local = _local_answer_from_evidence(docs, sensors, image, "Model JSON was truncated.")
        local["ok"] = True
        local["error"] = ""
        local["missing_evidence"] = ["Model JSON was truncated; used local evidence fields."]
        return local
    parsed["ok"] = True
    parsed["error"] = ""
    return parsed
