"""INDUSAI Streamlit workbench — UI/UX shell over existing backend."""

from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from agent import STEPS, gather_evidence, run_agent
from auth import can_access_department, current_user, logout, render_login
from config import AI_INFERENCE_LABEL, APP_NAME, DEMO_MACHINE_ID, SENSORS_DIR, ensure_folders
from database import (
    AUDIT_ACTIONS,
    AUDIT_AI_QUERY,
    AUDIT_DOCUMENT_SEARCH,
    AUDIT_IMAGE_ANALYSIS,
    AUDIT_REPORT,
    AUDIT_REVIEW,
    AUDIT_SENSOR_ANALYSIS,
    AUDIT_UPLOAD,
    audit_table,
    decide_review,
    get_investigation,
    init_db,
    latest_review,
    log_action,
    review_as_dict,
    save_investigation,
    submit_review,
)
from documents import (
    copy_demo_pdfs,
    ensure_demo_pdfs,
    list_documents,
    process_pdf,
    save_pdf,
)
from image_analysis import (
    analyze_image,
    demo_image_path,
    ensure_demo_images,
    save_image,
)
from rag import index_chunks, indexed_count, search_documents
from report import generate_report, list_reports
from sensor_analysis import (
    build_box_figure,
    build_sensor_figure,
    detect_anomalies,
    flag_rows,
    latest_status,
    load_sensor_frame,
    numeric_columns,
    sensor_csv_path,
    summarize_sensors,
)
from ui import (
    banner,
    checklist,
    chip_row,
    disclaimer,
    empty_state,
    error_box,
    evidence_card,
    finding_list,
    html,
    inject_styles,
    machine_card_html,
    metric_cards,
    page_header,
    progress_steps,
    render_status_badge,
    review_status_tone,
    section,
    status_badge,
    tone_class,
    topbar,
)

PAGES = [
    "Dashboard",
    "Investigation",
    "Documents",
    "Sensor Analysis",
    "Reports",
    "Audit Log",
]

MACHINES = [
    {
        "id": "PUMP-204",
        "name": "Centrifugal process pump",
        "area": "Unit 2 · Cooling water",
        "department": "Maintenance",
        "criticality": "High",
    },
    {
        "id": "FAN-118",
        "name": "Induced draft fan",
        "area": "Unit 1 · Boiler house",
        "department": "Operations",
        "criticality": "Medium",
    },
]

STEP_LABELS = {
    "Searching documents": "Documents retrieved",
    "Analyzing sensor data": "Sensor data analyzed",
    "Analyzing image": "Image analyzed",
    "Generating answer": "Generating AI assessment",
}


def _init() -> None:
    st.set_page_config(
        page_title=f"{APP_NAME} · Industrial AI Workbench",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_styles()
    ensure_folders()
    ensure_demo_images()
    ensure_demo_pdfs()
    init_db()
    if "page" not in st.session_state:
        st.session_state.page = "Dashboard"
    if "machine_id" not in st.session_state:
        st.session_state.machine_id = DEMO_MACHINE_ID
    # Old keys from the broken nav sync. Safe to drop before widgets exist.
    st.session_state.pop("sidebar_nav", None)
    st.session_state.pop("mobile_nav_select", None)
    _resolve_page()


def _resolve_page() -> None:
    """Pick the active page before any nav widget is created.

    Widget keys may only be written here, never after st.radio / st.selectbox.
    """
    goto = st.session_state.pop("goto_page", None)
    page = st.session_state.get("page", "Dashboard")
    if page not in PAGES:
        page = "Dashboard"
    radio = st.session_state.get("nav_radio")
    select = st.session_state.get("nav_select")

    if goto in PAGES:
        page = goto
        st.session_state.nav_radio = page
        st.session_state.nav_select = page
    elif radio in PAGES and radio != page:
        page = radio
        st.session_state.nav_select = page
    elif select in PAGES and select != page:
        page = select
        st.session_state.nav_radio = page
    else:
        if radio not in PAGES:
            st.session_state.nav_radio = page
        if select not in PAGES:
            st.session_state.nav_select = page
    st.session_state.page = page


def _banner() -> None:
    banner(f"{AI_INFERENCE_LABEL} · External LLM only · not on-premises")


def _visible_machines(user: dict) -> list[dict]:
    if user.get("role") == "Admin":
        return list(MACHINES)
    return [machine for machine in MACHINES if machine["department"] == user.get("department")]


def _sidebar(user: dict) -> None:
    with st.sidebar:
        html(
            """
            <div class="indus-sidebar-brand">
              <div class="indus-brand">INDUSAI</div>
              <div class="indus-brand-sub">Industrial AI Workbench</div>
              <div class="indus-sidebar-user">
                {name}<br/>{role} · {dept}
              </div>
            </div>
            """.format(
                name=user.get("name") or user["username"],
                role=user["role"],
                dept=user["department"],
            )
        )
        st.radio(
            "Navigate",
            PAGES,
            key="nav_radio",
            label_visibility="collapsed",
        )
        st.divider()
        st.caption("Session · SQLite auth · no JWT")
        if st.button("Sign out", use_container_width=True, key="btn_sign_out"):
            logout()
            st.rerun()


def _mobile_nav() -> None:
    """Page jump. Value is applied on the next run inside _resolve_page."""
    st.selectbox("Page", PAGES, key="nav_select")


def _shell(user: dict) -> None:
    topbar(
        user_label=f"{user.get('name') or user['username']} · {user['role']}",
        online=True,
    )
    _mobile_nav()
    _banner()


def render_dashboard(user: dict) -> None:
    page_header("Overview", "Dashboard", "Industrial AI Workbench · system status and recent work")
    _shell(user)

    docs = list_documents()
    present = sum(1 for row in docs if row["present"])
    df = load_sensor_frame()
    sensor = latest_status(df)
    flags = flag_rows(df)
    audits = audit_table(limit=5)
    chunks = indexed_count()
    reports = list_reports()
    saved = get_investigation(DEMO_MACHINE_ID)

    metric_cards(
        [
            {"label": "Investigations", "value": "1" if saved else "0", "hint": DEMO_MACHINE_ID},
            {"label": "Documents", "value": f"{present}/{len(docs)}", "hint": "on disk"},
            {"label": "Datasets", "value": "1" if not df.empty else "0", "hint": f"{len(flags)} sensor flags"},
            {"label": "Reports", "value": str(len(reports)), "hint": f"{chunks} indexed chunks"},
        ]
    )

    st.markdown(
        f'<p class="{tone_class(sensor["tone"])}">{sensor["label"]} — {sensor["detail"]}</p>',
        unsafe_allow_html=True,
    )

    if can_access_department(user, "Maintenance"):
        section("Demo prepare")
        st.caption("Copies synthetic PDFs, indexes ChromaDB, and refreshes demo images.")
        if st.button("Prepare demo files", use_container_width=True):
            with st.spinner("Preparing PUMP-204 demo files..."):
                ensure_demo_images()
                indexed_total = 0
                for path in copy_demo_pdfs():
                    result = process_pdf(path)
                    indexed_total += index_chunks(result["chunk_records"])
                log_action(
                    user["username"],
                    user["department"],
                    AUDIT_UPLOAD,
                    f"demo prepare; chunks={indexed_total}",
                )
            st.success(f"Demo ready. Indexed {indexed_total} chunks ({indexed_count()} total).")

    section("Recent investigations")
    if st.button("+ New Investigation", type="primary", use_container_width=True, key="btn_new_investigation"):
        st.session_state.machine_id = DEMO_MACHINE_ID
        st.session_state.goto_page = "Investigation"
        st.rerun()

    visible = _visible_machines(user)
    if not visible:
        empty_state(
            "No machines in your department",
            f"No machines are assigned to **{user['department']}** in this prototype.",
        )
    for machine in visible:
        badge = ""
        if machine["id"] == DEMO_MACHINE_ID:
            badge = status_badge(sensor["label"], sensor["tone"])
        html(
            machine_card_html(
                machine["id"],
                machine["name"],
                f"{machine['area']} · Criticality {machine['criticality']} · {machine['department']}",
                badge,
            )
        )
        if machine["id"] == DEMO_MACHINE_ID and can_access_department(user, machine["department"]):
            inv_status = saved["status"] if saved else "Open"
            st.caption(f"Status · {inv_status}")
            if st.button("Open investigation", key=f"open_{machine['id']}", use_container_width=True):
                st.session_state.machine_id = machine["id"]
                st.session_state.goto_page = "Investigation"
                log_action(user["username"], user["department"], "open_investigation", machine["id"])
                st.rerun()
        elif machine["id"] == DEMO_MACHINE_ID:
            st.caption("Outside your department")
        else:
            st.caption("Listed for access demo only")

    section("Recent activity")
    if not audits:
        empty_state("No audit events yet", "Actions will appear here after you use the workbench.")
    else:
        for row in audits:
            html(
                f"""
                <div class="indus-card">
                  <div class="indus-muted">{row['timestamp']}</div>
                  <div class="indus-card-title">{row['action']}</div>
                  <div class="indus-muted">User · {row['user']}</div>
                  <div class="indus-evidence-body">{row['details']}</div>
                </div>
                """
            )


def render_investigation(user: dict) -> None:
    page_header("Work order", f"{DEMO_MACHINE_ID} — Investigation", "Single coherent machine analysis workflow")
    _shell(user)

    if not can_access_department(user, "Maintenance"):
        error_box(
            f"Department access denied. PUMP-204 belongs to Maintenance. Your account is {user['department']} ({user['role']}).",
            "Sign in as admin, engineer, or reviewer for the Maintenance demo.",
        )
        log_action(user["username"], user["department"], "access_denied", DEMO_MACHINE_ID)
        return

    machines = [item for item in _visible_machines(user) if item["id"] == DEMO_MACHINE_ID]
    if not machines:
        empty_state("PUMP-204 not visible", "This machine is not available to your department in this prototype.")
        return

    selected = DEMO_MACHINE_ID
    st.session_state.machine_id = selected
    machine = machines[0]
    saved = get_investigation(selected)
    df = load_sensor_frame()
    sensor = latest_status(df)
    docs = list_documents()

    html(
        machine_card_html(
            machine["id"],
            machine["name"],
            f"{machine['area']} · {machine['department']} · Criticality {machine['criticality']}",
            status_badge(sensor["label"], sensor["tone"]),
        )
    )
    st.caption(sensor["detail"])

    section("Evidence")
    chip_row(
        [
            ("pump_manual.pdf", any(d["name"] == "pump_manual.pdf" and d["present"] for d in docs)),
            ("maintenance_history.pdf", any(d["name"] == "maintenance_history.pdf" and d["present"] for d in docs)),
            ("inspection.jpg", bool(st.session_state.get("inspect_image"))),
            ("sensor_data.csv", not df.empty),
        ]
    )
    with st.expander("Linked files detail", expanded=False):
        st.dataframe(
            pd.DataFrame(docs)[["name", "kind", "role", "present"]],
            use_container_width=True,
            hide_index=True,
        )

    section("Inspection image")
    st.caption("External vision API · JPG or PNG · key from .env only")
    uploaded_image = st.file_uploader("Upload JPG or PNG", type=["jpg", "jpeg", "png"])
    if uploaded_image is not None:
        token = (uploaded_image.name, uploaded_image.size)
        if st.session_state.get("image_upload_token") != token:
            st.session_state.image_upload_token = token
            saved_image = save_image(uploaded_image.name, uploaded_image.getvalue())
            st.session_state.inspect_image = str(saved_image)
            log_action(user["username"], user["department"], AUDIT_UPLOAD, f"image:{saved_image.name}")

    if st.button("Use demo image", use_container_width=True, key="btn_use_demo_image"):
        demo_img = demo_image_path()
        saved_image = save_image(demo_img.name, demo_img.read_bytes())
        st.session_state.inspect_image = str(saved_image)
        log_action(user["username"], user["department"], AUDIT_UPLOAD, f"demo image:{saved_image.name}")
        st.rerun()

    current_image = st.session_state.get("inspect_image")
    if current_image:
        st.image(current_image, caption=Path(current_image).name, use_container_width=True)
        if st.button("Analyse image", use_container_width=True, key="btn_analyse_image"):
            with st.spinner("Analyzing image..."):
                result = analyze_image(current_image)
            st.session_state.image_result = result
            log_action(
                user["username"],
                user["department"],
                AUDIT_IMAGE_ANALYSIS,
                result["filename"] if result.get("ok") else "failed",
            )
            st.rerun()
    else:
        empty_state("No inspection image", "Upload a JPG/PNG or use the demo image.")

    _show_image_result(st.session_state.get("image_result"))

    section("Question")
    if "inv_question" not in st.session_state:
        st.session_state.inv_question = (
            saved["question"]
            if saved
            else "What should I inspect on this machine, and are there any abnormal sensor readings?"
        )
    if "inv_notes" not in st.session_state:
        st.session_state.inv_notes = saved["notes"] if saved else ""
    if "inv_status" not in st.session_state:
        st.session_state.inv_status = saved["status"] if saved else "Open"

    question = st.text_area("Question", height=90, key="inv_question")
    notes = st.text_area("Engineer notes", height=100, key="inv_notes")
    status = st.selectbox(
        "Investigation status",
        ["Open", "In review", "Closed"],
        key="inv_status",
    )

    if st.button("Save investigation", use_container_width=True, key="btn_save_investigation"):
        save_investigation(selected, notes, question, status)
        log_action(user["username"], user["department"], "save_investigation", selected)
        st.success("Saved locally in SQLite.")

    section("AI analysis")
    st.caption("Documents → sensors → image → external LLM. Evidence-only. No chain-of-thought.")
    if st.button("ANALYZE MACHINE", type="primary", use_container_width=True, key="btn_analyze_machine"):
        save_investigation(selected, notes, question, status)
        progress = st.empty()
        done: list[str] = []

        def on_step(step: str) -> None:
            idx = STEPS.index(step)
            for earlier in STEPS[:idx]:
                if earlier not in done:
                    done.append(earlier)
            labels = [STEP_LABELS.get(name, name) for name in STEPS]
            done_labels = [STEP_LABELS.get(name, name) for name in done]
            with progress.container():
                progress_steps(labels, done=done_labels, active=STEP_LABELS.get(step, step))

        with st.spinner("Generating AI assessment..."):
            result = run_agent(
                question=question,
                image_path=st.session_state.get("inspect_image"),
                image_result=st.session_state.get("image_result"),
                on_step=on_step,
            )
        labels = [STEP_LABELS.get(name, name) for name in STEPS]
        with progress.container():
            progress_steps(labels, done=labels)
            html(
                '<div class="indus-progress"><div class="indus-progress-done">✓ Analysis complete</div></div>'
            )
        st.session_state.ai_result = result
        st.session_state.agent_steps = list(result.get("steps") or list(STEPS))
        if result.get("image_result") is not None:
            st.session_state.image_result = result["image_result"]
        log_action(
            user["username"],
            user["department"],
            AUDIT_AI_QUERY,
            "ok" if result.get("ok") else "failed",
        )
        if result.get("ok") and result.get("evidence"):
            st.session_state.evidence = result["evidence"].get("document_chunks") or []

    if st.session_state.get("agent_steps") and st.session_state.get("ai_result"):
        labels = [STEP_LABELS.get(name, name) for name in STEPS]
        progress_steps(labels, done=labels)

    ai_result = st.session_state.get("ai_result")
    if ai_result:
        _show_ai_result(ai_result)

    section("Sources / document evidence")
    st.caption("Local ChromaDB retrieval used as input to analysis.")
    if st.button("Retrieve evidence", use_container_width=True, key="btn_retrieve_evidence"):
        with st.spinner("Searching documents..."):
            hits = search_documents(question)
        st.session_state.evidence = hits
        log_action(user["username"], user["department"], AUDIT_DOCUMENT_SEARCH, question[:80])
        if not hits:
            st.warning("No chunks in ChromaDB. Process demo PDFs on the Documents page first.")
    _show_evidence(st.session_state.get("evidence") or [])

    _render_human_review(user, selected, question, notes)

    section("Report")
    if st.button("GENERATE REPORT", type="primary", use_container_width=True, key="btn_generate_report_inv"):
        with st.spinner("Writing PDF report..."):
            save_investigation(selected, notes, question, status)
            review_row = latest_review(selected)
            ai_payload = st.session_state.get("ai_result") or {}
            path = generate_report(
                engineer=user.get("name") or user["username"],
                question=question,
                notes=notes,
                status=status,
                answer=(ai_payload.get("answer") if ai_payload.get("ok") else None),
                evidence=ai_payload.get("evidence")
                or gather_evidence(question, st.session_state.get("image_result")),
                image_result=st.session_state.get("image_result"),
                review=review_as_dict(review_row),
                machine_id=selected,
            )
        st.session_state.last_report = str(path)
        log_action(user["username"], user["department"], AUDIT_REPORT, path.name)
        st.success(f"Wrote `{path.name}`")
        st.session_state.goto_page = "Reports"
        st.rerun()


def _answer_text_for_review(ai_result: dict | None) -> str:
    if not ai_result or not ai_result.get("ok"):
        return ""
    answer = ai_result.get("answer") or {}
    lines = [answer.get("summary") or ""]
    findings = (
        answer.get("evidence_findings")
        or (answer.get("document_findings") or []) + (answer.get("sensor_findings") or [])
    )
    for item in findings:
        lines.append(f"- {item}")
    for item in answer.get("recommendations") or []:
        lines.append(f"Rec: {item}")
    return "\n".join(line for line in lines if line).strip()


def _render_human_review(user: dict, machine_id: str, question: str, notes: str) -> None:
    section("Human review")
    review = review_as_dict(latest_review(machine_id))
    ai_result = st.session_state.get("ai_result")
    ai_ok = bool(ai_result and ai_result.get("ok"))

    st.markdown('<div class="indus-card">', unsafe_allow_html=True)
    if review:
        status = (review.get("status") or "pending").upper()
        render_status_badge(status, review_status_tone(status))
        st.write(
            f"**Investigation:** `{review['investigation']}` · "
            f"**User:** `{review['user']}` · "
            f"**Timestamp:** {review['timestamp']}"
        )
        if review.get("question"):
            st.caption(f"Question: {review['question']}")
        if review.get("answer"):
            with st.expander("Stored answer"):
                st.text(review["answer"])
        if review.get("reviewer"):
            st.caption(f"Reviewer: `{review['reviewer']}`")
        if review.get("reason"):
            st.caption(f"Reason: {review['reason']}")
    else:
        render_status_badge("NO REVIEW", "muted")
        st.caption("AI recommendations can be sent for engineer/reviewer verification.")
    st.markdown("</div>", unsafe_allow_html=True)

    if user["role"] in {"Engineer", "Admin"} and ai_ok:
        pending = review and review.get("status") == "pending"
        if pending:
            st.caption("A review is already pending.")
        elif st.button("REQUEST REVIEW", type="primary", use_container_width=True, key="btn_request_review"):
            answer_text = _answer_text_for_review(ai_result)
            save_investigation(machine_id, notes, question, "In review")
            submit_review(machine_id, user["username"], question=question, answer=answer_text)
            log_action(user["username"], user["department"], AUDIT_REVIEW, f"request:{machine_id}")
            st.success("Review requested.")
            st.rerun()
    elif user["role"] in {"Engineer", "Admin"} and not ai_ok:
        st.caption("Run ANALYZE MACHINE first, then request human review.")

    if user["role"] == "Reviewer" and review and review.get("status") == "pending":
        reason = st.text_input("Review reason (optional)", key="review_reason")
        c1, c2 = st.columns(2)
        if c1.button("APPROVE", use_container_width=True, key="btn_approve_review"):
            decide_review(int(review["id"]), user["username"], "approved", reason)
            log_action(user["username"], user["department"], AUDIT_REVIEW, f"approved:{machine_id}")
            st.success("Approved.")
            st.rerun()
        if c2.button("REJECT", use_container_width=True, key="btn_reject_review"):
            decide_review(int(review["id"]), user["username"], "rejected", reason)
            log_action(user["username"], user["department"], AUDIT_REVIEW, f"rejected:{machine_id}")
            st.warning("Rejected. Investigation set back to Open.")
            st.rerun()


def _show_ai_result(result: dict) -> None:
    if not result.get("ok"):
        error_box(
            "AI service unavailable or returned an incomplete answer. Local retrieval and sensor numbers still work.",
            result.get("error") or "Answer generation failed.",
        )
        answer = result.get("answer") or {}
        if not any(answer.get(k) for k in ("summary", "inspection_checks", "sensor_findings", "citations")):
            return

    answer = result.get("answer") or {}
    section("Executive summary")
    st.write(answer.get("summary") or "No summary returned.")
    disclaimer("AI suggestions are not certified engineering conclusions.")

    section("Sensor findings")
    sensor_bits = answer.get("sensor_findings") or []
    findings = (
        answer.get("evidence_findings")
        or (answer.get("document_findings") or []) + sensor_bits
    )
    finding_list(sensor_bits or [f for f in findings if "sensor" in f.lower() or "vibr" in f.lower() or "temp" in f.lower()] or findings[:5])

    section("Image observations")
    image_result = st.session_state.get("image_result") or result.get("image_result") or {}
    if image_result.get("ok"):
        finding_list(image_result.get("observations") or [])
    else:
        st.caption("No image observations available for this run.")

    section("Document evidence")
    finding_list(answer.get("evidence_findings") or answer.get("document_findings") or [])

    section("Suggested inspection")
    checklist(answer.get("inspection_checks") or answer.get("recommendations") or [])
    disclaimer("AI SUGGESTIONS — verify on site before any work order.")

    section("Missing evidence")
    finding_list(answer.get("missing_evidence") or [], empty="None listed.")

    cites = answer.get("citations") or []
    if cites:
        section("Sources")
        for cite in cites:
            evidence_card(
                str(cite.get("filename") or "source"),
                cite.get("page", "—"),
                str(cite.get("note") or ""),
            )


def _show_image_result(result: dict | None) -> None:
    if not result:
        return
    if not result.get("ok"):
        error_box(
            "Image analysis failed. The rest of the workbench still works.",
            result.get("error") or "Image analysis failed.",
        )
        return
    section("Image findings")
    groups = [
        ("Observations", "observations"),
        ("Possible issues", "possible_issues"),
        ("Suggested checks", "suggested_checks"),
        ("Limitations", "limitations"),
    ]
    for title, key in groups:
        st.markdown(f"**{title}**")
        finding_list(result.get(key) or [], empty="None returned.")


def _show_evidence(hits: list[dict]) -> None:
    if not hits:
        return
    for i, hit in enumerate(hits, start=1):
        evidence_card(hit.get("filename", ""), hit.get("page", "—"), hit.get("text", ""), index=i)
        with st.expander(f"View source · {hit.get('filename')} p.{hit.get('page')}"):
            st.write(hit.get("text") or "")


def _show_pdf_result(result: dict) -> None:
    metric_cards(
        [
            {"label": "Filename", "value": result["filename"]},
            {"label": "Pages", "value": str(result["page_count"])},
        ]
    )
    st.caption(f"Saved to `{result['saved_path']}`")
    with st.expander("Extracted text", expanded=False):
        st.text_area("Extracted text", result["text"], height=280, label_visibility="collapsed")
    if not result["text"]:
        st.warning("This PDF has no extractable text.")


def render_documents(user: dict) -> None:
    page_header("File store", "Documents", "Upload manuals and history · extract · index for RAG")
    _shell(user)

    uploaded = st.file_uploader("Upload PDF", type=["pdf"])
    if uploaded is not None:
        token = (uploaded.name, uploaded.size)
        if st.session_state.get("pdf_upload_token") != token:
            st.session_state.pdf_upload_token = token
            with st.spinner("Processing document..."):
                path = save_pdf(uploaded.name, uploaded.getvalue())
                result = process_pdf(path)
                n = index_chunks(result["chunk_records"])
                result["indexed"] = n
                st.session_state.last_pdf = result
                log_action(user["username"], user["department"], AUDIT_UPLOAD, f"pdf:{path.name}")

    if st.button("Process demo PDFs", use_container_width=True):
        with st.spinner("Processing demo PDFs..."):
            indexed_total = 0
            last = None
            for path in copy_demo_pdfs():
                result = process_pdf(path)
                n = index_chunks(result["chunk_records"])
                result["indexed"] = n
                last = result
                indexed_total += n
            if last:
                st.session_state.last_pdf = last
            log_action(user["username"], user["department"], AUDIT_UPLOAD, f"demo pdfs; chunks={indexed_total}")
        st.success(f"Indexed demo PDFs ({indexed_total} chunks).")

    if st.session_state.get("last_pdf"):
        section("Extraction result")
        _show_pdf_result(st.session_state.last_pdf)
        indexed = st.session_state.last_pdf.get("indexed")
        if indexed:
            st.caption(f"Indexed {indexed} chunks in ChromaDB ({indexed_count()} total).")

    section("Files")
    rows = list_documents()
    if not rows:
        empty_state("No documents uploaded", "Upload a machine manual or maintenance document.")
    else:
        for row in rows:
            present = "Ready" if row.get("present") else "Missing"
            tone = "ok" if row.get("present") else "muted"
            html(
                f"""
                <div class="indus-card">
                  <div class="indus-card-row">
                    <div>
                      <div class="indus-evidence-title">{row.get('name')}</div>
                      <div class="indus-muted">{row.get('kind')} · {row.get('role')} · {row.get('size_kb', 0)} KB</div>
                    </div>
                    {status_badge(present, tone)}
                  </div>
                </div>
                """
            )

    section("Search documents")
    query = st.text_input(
        "Question",
        value="What should I inspect on this machine?",
        key="doc_search_q",
    )
    if st.button("Search", use_container_width=True):
        with st.spinner("Searching documents..."):
            hits = search_documents(query)
        st.session_state.doc_hits = hits
        log_action(user["username"], user["department"], AUDIT_DOCUMENT_SEARCH, query[:80])
        if not hits:
            st.warning("No matching chunks. Process a PDF first.")
    _show_evidence(st.session_state.get("doc_hits") or [])


def render_sensors(user: dict) -> None:
    page_header("Telemetry", "Sensor Analysis", f"{DEMO_MACHINE_ID} · Pandas / NumPy / Plotly · no LLM for numbers")
    _shell(user)

    uploaded = st.file_uploader("Upload sensor CSV", type=["csv"])
    if uploaded is not None:
        token = (uploaded.name, uploaded.size)
        if st.session_state.get("csv_upload_token") != token:
            st.session_state.csv_upload_token = token
            SENSORS_DIR.mkdir(parents=True, exist_ok=True)
            target = SENSORS_DIR / uploaded.name
            target.write_bytes(uploaded.getvalue())
            st.success(f"Saved `{target.name}` to data/sensors/.")
            log_action(user["username"], user["department"], AUDIT_UPLOAD, f"csv:{target.name}")

    source = sensor_csv_path()
    df = load_sensor_frame(source)
    if df.empty:
        empty_state("No sensor dataset", "Put sensor_data.csv in demo/ or data/sensors/, or upload a CSV.")
        return

    st.caption(f"File: `{source}`")
    method = st.radio("Anomaly method", ["IQR", "z-score"], horizontal=True)
    summary = summarize_sensors(df)
    anomalies = detect_anomalies(df, method=method)
    sensor = latest_status(df)

    audit_token = (str(source), method, int(summary["row_count"]), int(len(anomalies)))
    if st.session_state.get("sensor_audit_token") != audit_token:
        st.session_state.sensor_audit_token = audit_token
        log_action(
            user["username"],
            user["department"],
            AUDIT_SENSOR_ANALYSIS,
            f"{Path(source).name if source else 'csv'}; method={method}; rows={summary['row_count']}; flags={len(anomalies)}",
        )

    # Compact latest readings for key columns
    cols = numeric_columns(df)
    latest_metrics = []
    if not df.empty and cols:
        last = df.iloc[-1]
        for col in cols[:4]:
            value = last[col]
            flagged = (not anomalies.empty) and (col in set(anomalies["column"].astype(str)))
            hint = "Abnormal" if flagged else "Latest"
            latest_metrics.append(
                {
                    "label": col.replace("_", " "),
                    "value": f"{float(value):.2f}" if pd.notna(value) else "—",
                    "hint": hint,
                }
            )
    if latest_metrics:
        section("Latest readings")
        metric_cards(latest_metrics)

    metric_cards(
        [
            {"label": "Row count", "value": str(summary["row_count"])},
            {"label": "Missing", "value": str(summary["missing_values"])},
            {"label": "Numeric cols", "value": str(len(summary["stats"]))},
            {"label": "Anomaly flags", "value": str(len(anomalies))},
        ]
    )
    st.markdown(
        f'<p class="{tone_class(sensor["tone"])}">{sensor["label"]} — {sensor["detail"]}</p>',
        unsafe_allow_html=True,
    )

    section("Statistics")
    stats = summary["stats"].copy()
    for col in ["mean", "minimum", "maximum", "standard_deviation"]:
        stats[col] = stats[col].map(lambda value: None if value is None else round(float(value), 3))
    st.dataframe(stats, use_container_width=True, hide_index=True)

    section("Trend chart")
    st.plotly_chart(build_sensor_figure(df, anomalies), use_container_width=True)
    section("Distribution")
    st.plotly_chart(build_box_figure(df), use_container_width=True)

    section("Detected anomalies")
    if anomalies.empty:
        st.success("No outliers for the selected method.")
    else:
        st.dataframe(anomalies, use_container_width=True, hide_index=True)

    with st.expander("Raw samples"):
        st.dataframe(df, use_container_width=True, hide_index=True)


def render_reports(user: dict) -> None:
    page_header("Exports", "Reports", "ReportLab PDF · not a certified inspection")
    _shell(user)

    if st.button("GENERATE REPORT", type="primary", use_container_width=True):
        with st.spinner("Writing PDF report..."):
            saved = get_investigation(DEMO_MACHINE_ID)
            review_row = latest_review(DEMO_MACHINE_ID)
            ai_result = st.session_state.get("ai_result") or {}
            path = generate_report(
                engineer=user.get("name") or user["username"],
                question=(saved["question"] if saved else ""),
                notes=(saved["notes"] if saved else ""),
                status=(saved["status"] if saved else "Open"),
                answer=(ai_result.get("answer") if ai_result.get("ok") else None),
                evidence=ai_result.get("evidence")
                or gather_evidence(
                    (saved["question"] if saved else "What should I inspect on this machine?"),
                    st.session_state.get("image_result"),
                ),
                image_result=st.session_state.get("image_result"),
                review=review_as_dict(review_row),
                machine_id=DEMO_MACHINE_ID,
            )
            log_action(user["username"], user["department"], AUDIT_REPORT, path.name)
        st.success(f"Wrote `{path.name}`")

    rows = list_reports()
    if not rows:
        empty_state("No reports yet", "Generate one here or from the Investigation page.")
        return

    review = review_as_dict(latest_review(DEMO_MACHINE_ID))
    review_label = (review.get("status") if review else "none") or "none"
    section("Generated reports")
    for row in rows:
        modified = datetime.fromtimestamp(row["modified"]).strftime("%Y-%m-%d %H:%M")
        html(
            f"""
            <div class="indus-card">
              <div class="indus-mono">{DEMO_MACHINE_ID}</div>
              <div class="indus-card-title">{row['name']}</div>
              <div class="indus-muted">Generated · {modified} · {row['size_kb']} KB · Review · {review_label}</div>
            </div>
            """
        )
        path = Path(row["path"])
        if path.exists():
            st.download_button(
                "DOWNLOAD",
                data=path.read_bytes(),
                file_name=path.name,
                mime="application/pdf",
                key=f"dl_{row['name']}",
                use_container_width=True,
            )


def render_audit(_user: dict) -> None:
    page_header("Trace", "Audit Log", "SQLite trail · passwords and API keys are never stored")
    _shell(_user)

    filter_options = ["All actions", *AUDIT_ACTIONS]
    choice = st.selectbox("Filter by action", filter_options)
    action = None if choice == "All actions" else choice
    rows = audit_table(limit=200, action=action)
    if not rows:
        empty_state("No events recorded yet", "Login, uploads, analysis, review, and reports appear here.")
        return

    # Desktop-friendly table
    with st.expander("Table view", expanded=True):
        st.dataframe(
            pd.DataFrame(rows)[["timestamp", "user", "action", "details"]],
            use_container_width=True,
            hide_index=True,
        )

    section("Event cards")
    for row in rows[:40]:
        html(
            f"""
            <div class="indus-card">
              <div class="indus-muted">{row['timestamp']}</div>
              <div class="indus-card-title">{row['action']}</div>
              <div class="indus-muted">User · {row['user']}</div>
              <div class="indus-evidence-body">{row['details']}</div>
            </div>
            """
        )
    st.caption(f"Showing {len(rows)} event(s).")


def main() -> None:
    _init()
    user = current_user()
    if not user:
        render_login()
        return
    _sidebar(user)
    page = st.session_state.page
    if page == "Dashboard":
        render_dashboard(user)
    elif page == "Investigation":
        render_investigation(user)
    elif page == "Documents":
        render_documents(user)
    elif page == "Sensor Analysis":
        render_sensors(user)
    elif page == "Reports":
        render_reports(user)
    elif page == "Audit Log":
        render_audit(user)


main()
