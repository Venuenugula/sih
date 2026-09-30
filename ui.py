"""Reusable INDUSAI UI helpers. Presentation only — no backend logic."""

from __future__ import annotations

import textwrap
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
STYLES_PATH = ROOT / "styles.css"


def html(markup: str) -> None:
    """Render HTML without Markdown turning indented tags into a code block."""
    st.html(textwrap.dedent(markup).strip())


def inject_styles() -> None:
    css = STYLES_PATH.read_text(encoding="utf-8")
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@500;600&display=swap');
        {css}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _escape(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def page_header(kicker: str, title: str, caption: str | None = None) -> None:
    st.markdown(f'<div class="indus-kicker">{kicker}</div>', unsafe_allow_html=True)
    st.markdown(f'<h1 class="indus-page-title">{title}</h1>', unsafe_allow_html=True)
    if caption:
        st.markdown(f'<p class="indus-muted">{caption}</p>', unsafe_allow_html=True)


def banner(text: str) -> None:
    st.markdown(f'<div class="indus-banner">{text}</div>', unsafe_allow_html=True)


def section(title: str) -> None:
    st.markdown(f'<div class="indus-section-title">{title}</div>', unsafe_allow_html=True)


def topbar(user_label: str | None = None, online: bool = True) -> None:
    right = ""
    if user_label:
        right += f'<span class="indus-muted">{user_label}</span>'
    if online:
        right += '<span class="indus-online">Online</span>'
    html(
        f"""
        <div class="indus-topbar">
          <div class="indus-topbar-left">
            <div class="indus-brand">INDUSAI</div>
            <div class="indus-brand-sub">Industrial AI Workbench</div>
          </div>
          <div class="indus-topbar-right">{right}</div>
        </div>
        """
    )


def status_badge(label: str, tone: str = "muted") -> str:
    cls = {
        "ok": "indus-badge-ok",
        "attn": "indus-badge-attn",
        "bad": "indus-badge-bad",
        "info": "indus-badge-info",
        "muted": "indus-badge-muted",
    }.get(tone, "indus-badge-muted")
    return f'<span class="indus-badge {cls}">{label}</span>'


def render_status_badge(label: str, tone: str = "muted") -> None:
    html(status_badge(label, tone))


def tone_class(tone: str) -> str:
    return {
        "ok": "indus-ok",
        "attn": "indus-attn",
        "bad": "indus-bad",
    }.get(tone, "indus-muted-status")


def metric_cards(items: list[dict]) -> None:
    """items: [{label, value, hint?}]"""
    cells = []
    for item in items:
        hint = item.get("hint") or ""
        hint_html = f'<div class="indus-metric-hint">{hint}</div>' if hint else ""
        cells.append(
            f"""
            <div class="indus-metric">
              <div class="indus-metric-label">{item.get("label", "")}</div>
              <div class="indus-metric-value">{item.get("value", "—")}</div>
              {hint_html}
            </div>
            """
        )
    html(f'<div class="indus-metric-grid">{"".join(cells)}</div>')


def empty_state(title: str, body: str) -> None:
    html(
        f"""
        <div class="indus-empty">
          <strong>{title}</strong>
          <div class="indus-muted">{body}</div>
        </div>
        """
    )


def error_box(message: str, detail: str | None = None) -> None:
    st.error(message)
    if detail:
        with st.expander("Technical details"):
            st.code(detail)


def disclaimer(text: str) -> None:
    st.markdown(f'<div class="indus-disclaimer">{text}</div>', unsafe_allow_html=True)


def evidence_card(filename: str, page: str | int, text: str, index: int | None = None) -> None:
    prefix = f"{index}. " if index is not None else ""
    snippet = (text or "").strip()
    if len(snippet) > 280:
        snippet = snippet[:277] + "…"
    html(
        f"""
        <div class="indus-evidence">
          <div class="indus-evidence-title">{prefix}{_escape(str(filename))}</div>
          <div class="indus-evidence-meta">Page {_escape(str(page))}</div>
          <div class="indus-evidence-body">{_escape(snippet)}</div>
        </div>
        """
    )


def finding_list(items: list[str], empty: str = "None recorded.") -> None:
    clean = [str(x).strip() for x in items if str(x).strip()]
    if not clean:
        st.caption(empty)
        return
    for item in clean:
        st.markdown(f"- {item}")


def checklist(items: list[str]) -> None:
    clean = [str(x).strip() for x in items if str(x).strip()]
    if not clean:
        st.caption("No suggested checks yet.")
        return
    for item in clean:
        html(
            f"""
            <div class="indus-check-item">
              <div class="indus-check-box"></div>
              <div>{_escape(item)}</div>
            </div>
            """
        )


def progress_steps(steps: list[str], done: list[str] | None = None, active: str | None = None) -> None:
    done = done or []
    lines = []
    for name in steps:
        if name in done and name != active:
            lines.append(f'<div class="indus-progress-done">✓ {name}</div>')
        elif name == active:
            lines.append(f'<div class="indus-progress-active">● {name}</div>')
        else:
            lines.append(f'<div class="indus-progress-todo">○ {name}</div>')
    html(f'<div class="indus-progress">{"".join(lines)}</div>')


def chip_row(labels: list[tuple[str, bool]]) -> None:
    """labels: [(text, active)]"""
    chips = []
    for text, active in labels:
        cls = "indus-chip indus-chip-on" if active else "indus-chip"
        chips.append(f'<span class="{cls}">{text}</span>')
    html(f'<div class="indus-chip-row">{"".join(chips)}</div>')


def review_status_tone(status: str) -> str:
    value = (status or "pending").lower()
    if value == "approved":
        return "ok"
    if value == "rejected":
        return "bad"
    if value == "pending":
        return "attn"
    return "muted"


def machine_card_html(machine_id: str, name: str, meta: str, badge_html: str = "") -> str:
    return f"""
    <div class="indus-card">
      <div class="indus-card-row">
        <div>
          <div class="indus-mono">{machine_id}</div>
          <div class="indus-card-title">{name}</div>
          <div class="indus-muted">{meta}</div>
        </div>
        <div>{badge_html}</div>
      </div>
    </div>
    """
