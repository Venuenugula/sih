"""Inspection image analysis via an external vision model."""

from __future__ import annotations

import json
import re
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from config import DEMO_DIR, DEMO_IMAGE_NAME, DEMO_MACHINE_ID, IMAGES_DIR, ensure_folders
from llm import describe_image

ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png"}

VISION_PROMPT = f"""This is a SYNTHETIC demo inspection photo for machine {DEMO_MACHINE_ID}.
It is not a real plant photograph.

Look only at this image. Do not invent sensor readings or quote manuals.

Reply with JSON only, no markdown fences, using exactly these keys:
{{
  "observations": ["what you see in the image"],
  "possible_issues": ["possible problems suggested by the image"],
  "suggested_checks": ["simple physical checks an engineer could do"],
  "limitations": ["why this reading may be incomplete or wrong"]
}}

Limitations must state that this is a demo image and that vision models can misread photos.
"""


def save_image(filename: str, data: bytes) -> Path:
    ensure_folders()
    name = Path(filename).name
    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError("Only JPG and PNG uploads are allowed.")
    target = IMAGES_DIR / name
    target.write_bytes(data)
    return target


def demo_image_paths() -> list[Path]:
    ensure_demo_images()
    paths = []
    for name in (DEMO_IMAGE_NAME, "inspection.png"):
        path = DEMO_DIR / name
        if path.exists():
            paths.append(path)
    return paths


def demo_image_path() -> Path:
    paths = demo_image_paths()
    if not paths:
        raise FileNotFoundError("No demo inspection image found.")
    return paths[0]


def _font(size: int):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _draw_demo_image(path: Path, subtitle: str) -> None:
    """Paint a simple synthetic pump sketch. Not a real inspection photo."""
    image = Image.new("RGB", (960, 640), (18, 24, 32))
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 40, 920, 600), outline=(42, 52, 68), width=3)
    draw.rectangle((180, 260, 520, 420), fill=(58, 72, 90), outline=(180, 190, 200), width=3)
    draw.ellipse((470, 250, 700, 430), fill=(46, 56, 70), outline=(180, 190, 200), width=3)
    draw.rectangle((300, 420, 360, 540), fill=(70, 80, 94))
    draw.rectangle((400, 420, 460, 540), fill=(70, 80, 94))
    draw.ellipse((250, 500, 620, 560), fill=(160, 70, 28))
    draw.polygon([(280, 510), (360, 470), (500, 505), (430, 545)], fill=(196, 90, 32))
    draw.text((56, 56), "INDUSAI SYNTHETIC DEMO", fill=(232, 168, 74), font=_font(22))
    draw.text((56, 96), f"{DEMO_MACHINE_ID}  drive-end seal area", fill=(215, 222, 232), font=_font(28))
    draw.text((56, 150), subtitle, fill=(139, 152, 168), font=_font(18))
    draw.text((200, 300), "PUMP BODY", fill=(215, 222, 232), font=_font(18))
    draw.text((520, 320), "MOTOR", fill=(215, 222, 232), font=_font(18))
    draw.text((270, 470), "SEAL / DARK STAIN (DRAWN, NOT REAL)", fill=(255, 210, 140), font=_font(16))
    path.parent.mkdir(parents=True, exist_ok=True)
    fmt = "PNG" if path.suffix.lower() == ".png" else "JPEG"
    image.save(path, format=fmt, quality=90)


def ensure_demo_images() -> None:
    ensure_folders()
    jpg = DEMO_DIR / DEMO_IMAGE_NAME
    png = DEMO_DIR / "inspection.png"
    if not jpg.exists():
        _draw_demo_image(jpg, "Not a real plant photograph.")
    if not png.exists():
        _draw_demo_image(png, "PNG variant of the same synthetic sketch.")


def _mime_for(path: Path) -> str:
    return "image/png" if path.suffix.lower() == ".png" else "image/jpeg"


def _prepare_image(path: Path) -> tuple[bytes, str]:
    mime = _mime_for(path)
    with Image.open(path) as image:
        image = image.convert("RGB")
        image.thumbnail((1024, 1024))
        buffer = BytesIO()
        if mime == "image/png":
            image.save(buffer, format="PNG")
        else:
            image.save(buffer, format="JPEG", quality=85)
        return buffer.getvalue(), mime


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def parse_vision_json(text: str) -> dict:
    blob = (text or "").strip()
    match = re.search(r"\{.*\}", blob, flags=re.DOTALL)
    if match:
        blob = match.group(0)
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        return {
            "observations": [blob[:800]] if blob else [],
            "possible_issues": [],
            "suggested_checks": [],
            "limitations": ["The vision model did not return JSON, so the text was kept as observations."],
        }
    return {
        "observations": _as_list(data.get("observations")),
        "possible_issues": _as_list(data.get("possible_issues")),
        "suggested_checks": _as_list(data.get("suggested_checks")),
        "limitations": _as_list(data.get("limitations")),
    }


def _empty_fields() -> dict:
    return {
        "observations": [],
        "possible_issues": [],
        "suggested_checks": [],
        "limitations": [],
    }


def _demo_sketch_fallback(filename: str, api_error: str) -> dict:
    """When the vision API is down, describe the known synthetic demo sketch only."""
    return {
        "ok": True,
        "filename": filename,
        "error": "",
        "observations": [
            "Synthetic sketch labeled PUMP-204 drive-end seal area.",
            "Pump body and motor are labeled on the drawing.",
            "A dark stain is drawn near the seal / housing region.",
        ],
        "possible_issues": [
            "Possible seal-area residue or leakage suggested by the drawn stain (demo only).",
        ],
        "suggested_checks": [
            "Wipe and re-inspect the seal area under light.",
            "Check for fresh leakage around the mechanical seal.",
            "Compare local vibration and temperature to recent sensor trends.",
        ],
        "limitations": [
            f"External vision API unavailable ({api_error}). Used known synthetic demo sketch labels.",
            "This is not a real plant photograph. Vision models can misread photos.",
        ],
        "fallback": True,
    }


def analyze_image(path: str | Path) -> dict:
    """Send one local JPG/PNG to the external vision model."""
    image_path = Path(path)
    result = {
        "ok": False,
        "filename": image_path.name,
        "error": "",
        **_empty_fields(),
    }
    if image_path.suffix.lower() not in ALLOWED_SUFFIXES:
        result["error"] = "Only JPG and PNG files can be analysed."
        return result
    if not image_path.exists():
        result["error"] = f"Image not found: {image_path.name}"
        return result

    payload, mime = _prepare_image(image_path)
    raw = describe_image(payload, mime, VISION_PROMPT)
    if not raw.get("ok"):
        api_error = raw.get("error") or "Vision API request failed."
        # Keep the PUMP-204 demo path usable during transient API / rate-limit failures.
        if image_path.name in {DEMO_IMAGE_NAME, "inspection.png"}:
            return _demo_sketch_fallback(image_path.name, api_error)
        result["error"] = api_error
        result["limitations"] = [
            "No vision result is shown because the external API call failed.",
            "This prototype uses an external multimodal LLM, not an on-premises model.",
        ]
        return result

    parsed = parse_vision_json(raw["text"])
    result.update(parsed)
    result["ok"] = True
    return result
