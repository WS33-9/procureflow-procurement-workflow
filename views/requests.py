"""ProcureFlow requestor intake and procurement workflow experience."""

from __future__ import annotations

import os
from datetime import date, datetime, time
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import streamlit as st

from src import config
from src.database import (
    ValidationError,
    add_request_reference,
    assign_request,
    connect_database,
    create_request,
    list_table_names,
    transition_request_status,
    update_request,
)
from src.demo_workspace import (
    DemoWorkspaceError,
    create_demo_workspace,
    is_baseline_path,
    reset_demo_workspace,
)
from src.queries import (
    get_enriched_request,
    get_filter_options,
    list_active_app_users,
    list_enriched_requests,
)
from src.rules import RULE_CODES
from src.ui import (
    ACTIVE_DATABASE_STATE_KEY,
    ATTENTION_LABELS,
    DEFAULT_DEMO_DATABASE_PATH,
    DEMO_SESSION_DIRECTORY,
    EXPECTED_TABLES,
    attention_labels,
    format_cad,
    format_display_date,
    load_application_styles,
    relevant_due,
    resolve_database_path,
)


DEMO_AS_OF_DATE = date(2026, 7, 30)
SELECTED_REQUEST_KEY = "requests_selected_request_id"
INTAKE_STATE_KEY = "requests_show_intake"
PAGE_NUMBER_KEY = "requests_page_number"
PAGE_SIZE = 12

FILTER_KEYS = (
    "requests_search_text",
    "requests_lifecycle_statuses",
    "requests_priorities",
    "requests_business_units",
    "requests_request_categories",
    "requests_owner_ids",
    "requests_attention_codes",
    "requests_include_completed",
    "requests_include_cancelled",
)


def _reset_filters() -> None:
    for key in FILTER_KEYS:
        st.session_state.pop(key, None)
    st.session_state[PAGE_NUMBER_KEY] = 1


def _open_request(request_id: Any) -> None:
    st.session_state.pop(INTAKE_STATE_KEY, None)
    st.session_state[SELECTED_REQUEST_KEY] = str(request_id)


def _close_request() -> None:
    st.session_state.pop(SELECTED_REQUEST_KEY, None)


def _open_intake() -> None:
    st.session_state.pop(SELECTED_REQUEST_KEY, None)
    st.session_state[INTAKE_STATE_KEY] = True


def _close_intake() -> None:
    st.session_state.pop(INTAKE_STATE_KEY, None)


def _is_writable_workspace(database_path: Path) -> bool:
    if os.environ.get("PROCUREFLOW_DATABASE_PATH", "").strip():
        return True
    return not is_baseline_path(database_path, DEFAULT_DEMO_DATABASE_PATH)


def _render_header() -> None:
    st.markdown(
        """
        <section class="pf-header pf-header--requests">
          <div class="pf-eyebrow">Request intake and procurement workflow</div>
          <div class="pf-header__body">
            <h1>Procurement requests</h1>
            <p>
               Submit a procurement request, review ownership and current work,
  and maintain the shared record used for management reporting.
            </p>
          </div>
          <div class="pf-context-labels" aria-label="Prototype context">
            <span>Fictional implementation case</span>
            <span>Synthetic demo data</span>
            <span>Demo data snapshot · July 30, 2026</span>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_workspace_notice(database_path: Path, writable: bool) -> None:
    if writable:
        st.markdown(
            """
            <section class="pf-boundary pf-workspace-notice" role="note">
              <strong>Local demo workspace</strong>
              <span>
                Workflow changes are written to a local session copy. The
                approved synthetic-data baseline remains unchanged.
              </span>
            </section>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <section class="pf-boundary pf-workspace-notice" role="note">
              <strong>Baseline preview</strong>
              <span>
                Browse the approved synthetic data safely. Create a local demo
                workspace before performing workflow actions.
              </span>
            </section>
            """,
            unsafe_allow_html=True,
        )


def _render_workspace_controls(database_path: Path, writable: bool) -> None:
    st.sidebar.markdown("## Demo workspace")
    if not writable:
        st.sidebar.caption(
            "The approved baseline is read-only during interactive review."
        )
        if st.sidebar.button(
            "Create local demo workspace",
            type="primary",
            width="stretch",
            key="requests_create_workspace",
        ):
            try:
                workspace = create_demo_workspace(
                    DEFAULT_DEMO_DATABASE_PATH,
                    workspace_directory=DEMO_SESSION_DIRECTORY,
                )
            except DemoWorkspaceError as error:
                st.sidebar.error(str(error))
            else:
                st.session_state[ACTIVE_DATABASE_STATE_KEY] = str(workspace)
                st.session_state.pop(SELECTED_REQUEST_KEY, None)
                st.rerun()
        return

    st.sidebar.success("Local writable copy active")
    if os.environ.get("PROCUREFLOW_DATABASE_PATH", "").strip():
        st.sidebar.caption("An isolated database path is configured externally.")
        return

    confirm_reset = st.sidebar.checkbox(
        "Confirm reset to approved baseline",
        key="requests_confirm_reset_workspace",
    )
    if st.sidebar.button(
        "Reset local demo workspace",
        type="secondary",
        width="stretch",
        disabled=not confirm_reset,
        key="requests_reset_workspace",
    ):
        try:
            reset_demo_workspace(
                database_path,
                baseline_path=DEFAULT_DEMO_DATABASE_PATH,
            )
        except DemoWorkspaceError as error:
            st.sidebar.error(str(error))
        else:
            st.session_state.pop(SELECTED_REQUEST_KEY, None)
            st.session_state.pop(INTAKE_STATE_KEY, None)
            st.session_state["requests_workspace_message"] = (
                "Local demo workspace reset to the approved baseline."
            )
            st.rerun()


def _render_filters(options: dict[str, Any]) -> dict[str, Any]:
    st.sidebar.markdown("## Request filters")
    search_text = st.sidebar.text_input(
        "Search requests",
        placeholder="Number, title, requestor, work or reference",
        key="requests_search_text",
    )
    lifecycle_statuses = st.sidebar.multiselect(
        "Lifecycle status",
        options["lifecycle_statuses"],
        key="requests_lifecycle_statuses",
    )
    priorities = st.sidebar.multiselect(
        "Priority",
        options["priorities"],
        key="requests_priorities",
    )
    business_units = st.sidebar.multiselect(
        "Business unit",
        options["business_units"],
        key="requests_business_units",
    )
    request_categories = st.sidebar.multiselect(
        "Request category",
        options["request_categories"],
        key="requests_request_categories",
    )

    owner_labels: dict[Any, str] = {None: "Unassigned"}
    owner_labels.update(
        {
            officer["owner_user_id"]: officer["owner_name"]
            for officer in options["procurement_officers"]
        }
    )
    owner_ids = st.sidebar.multiselect(
        "Procurement owner",
        list(owner_labels),
        format_func=lambda owner_id: owner_labels[owner_id],
        key="requests_owner_ids",
    )

    attention_codes = st.sidebar.multiselect(
        "Attention condition",
        options["attention_rule_codes"],
        format_func=lambda code: ATTENTION_LABELS[code],
        key="requests_attention_codes",
    )
    st.sidebar.markdown(
        '<div class="pf-filter-group-label">Include closed records</div>',
        unsafe_allow_html=True,
    )
    closed_columns = st.sidebar.columns(2)
    include_completed = closed_columns[0].checkbox(
        "Completed",
        value=False,
        key="requests_include_completed",
    )
    include_cancelled = closed_columns[1].checkbox(
        "Cancelled",
        value=False,
        key="requests_include_cancelled",
    )
    st.sidebar.button(
        "Reset filters",
        type="secondary",
        width="stretch",
        key="requests_reset_filters",
        on_click=_reset_filters,
    )
    st.sidebar.caption("Selections within one filter use OR; filters combine with AND.")
    return {
        "search_text": search_text,
        "lifecycle_statuses": lifecycle_statuses,
        "priorities": priorities,
        "business_units": business_units,
        "request_categories": request_categories,
        "procurement_owner_user_ids": owner_ids,
        "attention_rule_codes": attention_codes,
        "include_completed": include_completed,
        "include_cancelled": include_cancelled,
    }


def _tag(text: str, modifier: str = "") -> str:
    css_class = "pf-table-tag"
    if modifier:
        css_class += f" pf-table-tag--{modifier}"
    return f'<span class="{css_class}">{escape(text)}</span>'


def _render_request_row(request: dict[str, Any]) -> None:
    due_date, due_label = relevant_due(request)
    labels = attention_labels(request)
    columns = st.columns([1.75, 0.9, 1.0, 1.8, 0.85, 1.35, 0.85], gap="small")
    with columns[0]:
        st.markdown(
            f'<span class="pf-request-number">{escape(request["request_number"])}</span>'
            f'<span class="pf-primary-text pf-clamp-two">{escape(request["request_title"])}</span>'
            f'<span class="pf-secondary-text">{escape(request["business_unit"])} · '
            f'{escape(request["request_category"])}</span>',
            unsafe_allow_html=True,
        )
    with columns[1]:
        st.markdown(
            _tag(request["lifecycle_status"], "status")
            + '<div class="pf-tag-gap"></div>'
            + _tag(request["priority"], request["priority"].lower()),
            unsafe_allow_html=True,
        )
    with columns[2]:
        owner = request["procurement_owner_name"] or "Unassigned"
        modifier = "unassigned" if owner == "Unassigned" else ""
        st.markdown(_tag(owner, modifier), unsafe_allow_html=True)
    with columns[3]:
        st.markdown(
            f'<span class="pf-primary-text pf-clamp-two">'
            f'{escape(request["current_dependency"] or "No current dependency")}</span>'
            f'<span class="pf-secondary-text pf-clamp-two">'
            f'{escape(request["next_action"] or "No next action recorded")}</span>',
            unsafe_allow_html=True,
        )
    with columns[4]:
        st.markdown(
            f'<span class="pf-due-date">{escape(due_date)}</span>'
            f'<span class="pf-secondary-text">{escape(due_label)}</span>',
            unsafe_allow_html=True,
        )
    with columns[5]:
        if labels:
            visible = labels[:2]
            extra = len(labels) - len(visible)
            markup = "".join(
                f'<span class="pf-list-attention-label">{escape(label)}</span>'
                for label in visible
            )
            if extra:
                markup += f'<span class="pf-attention-more">+{extra} more</span>'
            st.markdown(markup, unsafe_allow_html=True)
        else:
            st.markdown('<span class="pf-secondary-text">No current condition</span>', unsafe_allow_html=True)
    with columns[6]:
        st.button(
            "Open",
            key=f'open_request_{request["request_id"]}',
            on_click=_open_request,
            args=(request["request_id"],),
            width="stretch",
        )


def _render_request_list(
    connection: Any,
    options: dict[str, Any],
) -> None:
    filters = _render_filters(options)
    records = list_enriched_requests(
        connection,
        as_of=DEMO_AS_OF_DATE,
        sort_by="attention_count",
        sort_direction="desc",
        **filters,
    )
    if st.session_state.get("requests_workspace_message"):
        st.success(st.session_state.pop("requests_workspace_message"))

    heading, action = st.columns([5, 1])
    heading.markdown("## Procurement workspace")
    action.button(
        "Submit request",
        type="primary",
        width="stretch",
        key="requests_new_request",
        on_click=_open_intake,
    )
    st.caption(
        "Authorized procurement users can review submitted requests, assign ownership, "
"and maintain the operational record. Attention conditions are derived from "
"the same request data."
    )
    if not records:
        st.info(
            "No requests match the selected filters. Reset the filters or "
            "adjust your selections to view results."
        )
        return

    total_pages = max(1, (len(records) + PAGE_SIZE - 1) // PAGE_SIZE)
    page_number = min(
        max(1, int(st.session_state.get(PAGE_NUMBER_KEY, 1))),
        total_pages,
    )
    st.session_state[PAGE_NUMBER_KEY] = page_number
    start = (page_number - 1) * PAGE_SIZE
    end = min(start + PAGE_SIZE, len(records))
    st.markdown(
        f'<div class="pf-list-summary">Showing {start + 1}–{end} of '
        f'{len(records)} requests</div>',
        unsafe_allow_html=True,
    )
    headings = st.columns([1.75, 0.9, 1.0, 1.8, 0.85, 1.35, 0.85], gap="small")
    for column, label in zip(
        headings,
        ("Request", "Status", "Ownership", "Current work", "Due", "Attention", ""),
        strict=True,
    ):
        column.markdown(
            f'<div class="pf-list-column-label">{escape(label)}</div>',
            unsafe_allow_html=True,
        )
    for request in records[start:end]:
        st.markdown('<span class="pf-request-row-marker"></span>', unsafe_allow_html=True)
        _render_request_row(request)

    if total_pages > 1:
        previous, context, following = st.columns([1, 2, 1])
        if previous.button(
            "Previous",
            disabled=page_number == 1,
            width="stretch",
            key="requests_previous_page",
        ):
            st.session_state[PAGE_NUMBER_KEY] = page_number - 1
            st.rerun()
        context.markdown(
            f'<div class="pf-page-context">Page {page_number} of {total_pages}</div>',
            unsafe_allow_html=True,
        )
        if following.button(
            "Next",
            disabled=page_number == total_pages,
            width="stretch",
            key="requests_next_page",
        ):
            st.session_state[PAGE_NUMBER_KEY] = page_number + 1
            st.rerun()


def _render_intake(
    connection: Any,
    users: list[dict[str, Any]],
    writable: bool,
) -> None:
    st.button(
        "← Back to requests",
        key="requests_cancel_intake_top",
        on_click=_close_intake,
    )
    st.markdown(
        '<div class="pf-detail-eyebrow">Requestor experience</div>',
        unsafe_allow_html=True,
    )
    st.markdown("## Submit a procurement request")
    st.caption(
        "A requestor or authorized user submits the request. It enters the workflow "
        "as Submitted and Unassigned until an authorized procurement user assigns "
        "one procurement officer. This is a simulated role experience, not production authentication."
    )
    if not writable:
        st.info(
            "Create a local demo workspace from the sidebar to submit this request. "
            "The synthetic-data baseline remains protected."
        )

    user_labels = {
        user["user_id"]: f'{user["display_name"]} · {user["role"]}'
        for user in users
    }
    with st.form("requests_intake_form", border=True):
        st.markdown("Required fields are marked with *.")
        created_by_user_id = st.selectbox(
            "Submitted by / authorized requestor *",
            list(user_labels),
            format_func=lambda user_id: user_labels[user_id],
            key="requests_intake_submitter",
        )
        request_title = st.text_input(
            "Request title *",
            key="requests_intake_title",
        )
        requestor_name = st.text_input(
            "Requestor name *",
            key="requests_intake_requestor",
        )
        business_unit, request_category = st.columns(2)
        selected_business_unit = business_unit.selectbox(
            "Business unit *",
            config.BUSINESS_UNITS,
            key="requests_intake_business_unit",
        )
        selected_request_category = request_category.selectbox(
            "Request category *",
            config.REQUEST_CATEGORIES,
            key="requests_intake_category",
        )
        description = st.text_area(
            "Description *",
            key="requests_intake_description",
        )
        priority, required_by_date = st.columns(2)
        selected_priority = priority.selectbox(
            "Priority *",
            config.PRIORITIES,
            index=config.PRIORITIES.index("Medium"),
            key="requests_intake_priority",
        )
        selected_required_by_date = required_by_date.date_input(
            "Required-by date *",
            value=date(2026, 8, 14),
            key="requests_intake_required_by",
            help="A past date is allowed so late or urgent requests can still be recorded.",
        )
        estimated_value = st.number_input(
            "Estimated value (CAD, optional)",
            value=None,
            step=100.0,
            format="%.2f",
            key="requests_intake_estimated_value",
        )
        closure_evidence_required = st.checkbox(
            "Closure evidence required",
            key="requests_intake_closure_evidence",
            help="Records whether evidence will be required before completion.",
        )
        st.caption(
            "This fictional case uses synthetic data. Formal approvals, financial transactions, "
            "contracts and official documents remain in their existing processes and systems."
        )
        create_column, cancel_column = st.columns([1, 1])
        submitted = create_column.form_submit_button(
            "Submit request",
            type="primary",
            width="stretch",
            disabled=not writable,
        )
        cancelled = cancel_column.form_submit_button(
            "Cancel",
            width="stretch",
        )

    if cancelled:
        _close_intake()
        st.rerun()
    if not submitted:
        return

    try:
        created = create_request(
            connection,
            created_by_user_id=created_by_user_id,
            request_title=request_title,
            requestor_name=requestor_name,
            business_unit=selected_business_unit,
            request_category=selected_request_category,
            description=description,
            priority=selected_priority,
            required_by_date=selected_required_by_date,
            estimated_value=estimated_value,
            closure_evidence_required=closure_evidence_required,
        )
    except ValidationError as error:
        _render_action_error(error)
        return

    st.session_state.pop(INTAKE_STATE_KEY, None)
    st.session_state[SELECTED_REQUEST_KEY] = str(created["request_id"])
    st.session_state["requests_action_message"] = (
        f'{created["request_number"]} submitted successfully and awaiting assignment.'
    )
    st.rerun()


def _display(value: Any) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, datetime):
        from src.ui import APPLICATION_ZONE

        return (
            value.astimezone(APPLICATION_ZONE)
            .strftime("%b %d, %Y · %I:%M %p")
            .replace(" 0", " ")
        )
    if isinstance(value, date):
        return format_display_date(value)
    return str(value)


def _field(label: str, value: Any) -> None:
    st.markdown(
        f'<div class="pf-detail-field"><span>{escape(label)}</span>'
        f'<strong>{escape(_display(value))}</strong></div>',
        unsafe_allow_html=True,
    )


def _optional_text(value: str) -> str | None:
    normalized = value.strip()
    return normalized or None


def _as_confirmation_datetime(value: date) -> datetime:
    from src.ui import APPLICATION_ZONE

    return datetime.combine(value, time.min, tzinfo=APPLICATION_ZONE)


def _action_success(message: str) -> None:
    st.session_state["requests_action_message"] = message
    st.rerun()


def _render_action_error(error: Exception) -> None:
    st.error(str(error))


def _render_attention_summary(detail: dict[str, Any]) -> None:
    request = detail["request"]
    labels = attention_labels(request)
    attention_markup = "".join(
        f'<span class="pf-list-attention-label">{escape(label)}</span>'
        for label in labels
    ) or '<span class="pf-secondary-text">No current attention condition</span>'
    st.markdown(
        '<section class="pf-detail-summary">'
        f'<div><span>Status</span><strong>{escape(request["lifecycle_status"])}</strong></div>'
        f'<div><span>Priority</span><strong>{escape(request["priority"])}</strong></div>'
        f'<div><span>Owner</span><strong>{escape(request["procurement_owner_name"] or "Unassigned")}</strong></div>'
        f'<div class="pf-detail-summary__attention"><span>Attention</span>{attention_markup}</div>'
        '</section>',
        unsafe_allow_html=True,
    )


def _render_overview(request: dict[str, Any]) -> None:
    st.markdown("### Request overview")
    with st.container(border=True):
        st.markdown(
            f'<div class="pf-detail-description">{escape(request["description"])}</div>',
            unsafe_allow_html=True,
        )
        columns = st.columns(4)
        fields = (
            ("Requestor", request["requestor_name"]),
            ("Business unit", request["business_unit"]),
            ("Request category", request["request_category"]),
            ("Priority", request["priority"]),
            ("Required by", request["required_by_date"]),
            (
                "Estimated value",
                format_cad(request["estimated_value"])
                if request["estimated_value"] is not None
                else None,
            ),
            ("Procurement route", request["procurement_route"]),
            ("Last updated by", request["updated_by_name"]),
        )
        for index, (label, value) in enumerate(fields):
            with columns[index % 4]:
                _field(label, value)


def _render_ownership(request: dict[str, Any]) -> None:
    st.markdown("### Ownership and lifecycle")
    with st.container(border=True):
        columns = st.columns(4)
        fields = [
            ("Lifecycle status", request["lifecycle_status"]),
            ("Procurement owner", request["procurement_owner_name"] or "Unassigned"),
            ("Submitted", request["submitted_at"]),
            ("Assignment date", request["assignment_date"]),
            ("Target completion", request["target_completion_date"]),
            ("Completion date", request["completion_date"]),
            ("Cancellation date", request["cancellation_date"]),
            ("Last updated", request["updated_at"]),
        ]
        for index, (label, value) in enumerate(fields):
            with columns[index % 4]:
                _field(label, value)


def _render_current_work(request: dict[str, Any]) -> None:
    st.markdown("### Current work")
    st.caption(
        "Lifecycle status shows where the request is. Dependencies, next actions "
        "and dates show what requires follow-up. Dates do not change lifecycle status."
    )
    with st.container(border=True):
        columns = st.columns(3)
        fields = (
            ("Dependency type", request["dependency_type"]),
            ("Current dependency", request["current_dependency"]),
            ("Dependency owner", request["dependency_owner"]),
            ("Next action", request["next_action"]),
            ("Follow-up date", request["follow_up_date"]),
            ("Target completion date", request["target_completion_date"]),
        )
        for index, (label, value) in enumerate(fields):
            with columns[index % 3]:
                _field(label, value)
        _field("Officer note", request["officer_note"])


def _render_approval(request: dict[str, Any]) -> None:
    st.markdown("### Approval confirmation")
    st.caption(
        "ProcureFlow records approval confirmation from the source process. "
        "It does not make the approval decision."
    )
    with st.container(border=True):
        columns = st.columns(4)
        fields = (
            ("Approval required", request["approval_required"]),
            ("Approval requirement", request["approval_requirement"]),
            ("Approval status", request["approval_status"]),
            ("Approval source", request["approval_source"]),
            ("Approval reference", request["approval_reference"]),
            ("Confirmation date", request["approval_confirmation_date"]),
            ("Approval notes", request["approval_notes"]),
        )
        for index, (label, value) in enumerate(fields):
            with columns[index % 4]:
                _field(label, value)


def _render_references(detail: dict[str, Any]) -> None:
    st.markdown("### Related references")
    st.caption(
        "ProcureFlow stores links and identifiers for related records. Official "
        "documents remain in the external system or process that governs them."
    )
    references = detail["references"]
    if not references:
        st.info("No related references have been recorded.")
        return
    for reference in references:
        with st.container(border=True):
            columns = st.columns([1.25, 1.25, 1.4, 0.75])
            with columns[0]:
                _field("Reference type", reference["reference_type"])
            with columns[1]:
                _field("Reference number", reference["reference_number"])
            with columns[2]:
                _field("Source system or process", reference["source_system_or_process"])
            with columns[3]:
                _field("Closure evidence", reference["is_closure_evidence"])
            if reference["reference_link"]:
                reference_url = reference["reference_link"]
                hostname = urlparse(reference_url).hostname or ""

                if hostname.endswith(".example") or hostname.endswith(".invalid"):
                    st.caption(
                        f"Fictional demo reference: {reference_url} "
                        "This reserved domain is intentionally non-functional."
                    )
                else:
                    st.link_button("Open external reference", reference_url)
            if reference["note"]:
                st.caption(reference["note"])


def _render_closure(request: dict[str, Any]) -> None:
    st.markdown("### Closure")
    with st.container(border=True):
        columns = st.columns(4)
        fields = (
            ("Closure evidence required", request["closure_evidence_required"]),
            ("Closure evidence confirmed", request["closure_evidence_confirmed"]),
            ("Closure note", request["closure_note"]),
            ("Cancellation reason", request["cancellation_reason"]),
        )
        for index, (label, value) in enumerate(fields):
            with columns[index]:
                _field(label, value)


def _render_history(detail: dict[str, Any]) -> None:
    st.markdown("### Request history")
    st.caption(
        "Chronological operational events show how the shared request record changed."
    )
    history = detail["history"]
    if not history:
        st.info("No history events have been recorded.")
        return

    field_labels = {
        "lifecycle_status": "Lifecycle status",
        "procurement_owner_user_id": "Procurement owner",
        "target_completion_date": "Target completion date",
        "current_dependency": "Current dependency",
        "dependency_owner": "Dependency owner",
        "dependency_type": "Dependency type",
        "follow_up_date": "Follow-up date",
        "next_action": "Next action",
        "officer_note": "Officer note",
        "procurement_route": "Procurement route",
        "approval_required": "Approval required",
        "approval_requirement": "Approval requirement",
        "approval_status": "Approval status",
        "approval_source": "Approval source",
        "approval_reference": "Approval reference",
        "approval_confirmation_date": "Approval confirmation date",
        "approval_notes": "Approval notes",
        "closure_evidence_required": "Closure evidence required",
        "closure_evidence_confirmed": "Closure evidence confirmed",
        "closure_note": "Closure note",
        "request_references": "Related reference",
    }

    def history_value(value: Any, *, direction: str) -> str:
        text = _display(value)
        if text in ("—", "None"):
            return "Not set"
        if (
            len(text) > 72
            or "{" in text
            or "datetime." in text
            or text.count("-") >= 4
        ):
            return "Previous values" if direction == "previous" else "Updated values"
        return text

    for event in history:
        with st.container(border=True):
            columns = st.columns([1.05, 1.0, 2.45, 1.1])
            with columns[0]:
                _field("Date", event["event_at"])
            with columns[1]:
                _field("Event", event["event_type"])
            with columns[2]:
                _field("Summary", event["event_summary"])
            with columns[3]:
                _field("User", event["event_by_name"])
            if event["field_name"]:
                field_names = [
                    field_labels.get(name.strip(), name.strip().replace("_", " ").title())
                    for name in event["field_name"].split(",")
                ]
                change_label = ", ".join(field_names)
                st.markdown(
                    f'<div class="pf-history-change"><strong>{escape(change_label)}</strong>'
                    f'<span>{escape(history_value(event["previous_value"], direction="previous"))} → '
                    f'{escape(history_value(event["new_value"], direction="new"))}</span></div>',
                    unsafe_allow_html=True,
                )


def _render_actor_selector(
    users: list[dict[str, Any]],
    *,
    current_owner_user_id: Any = None,
) -> Any:
    user_labels = {
        user["user_id"]: f'{user["display_name"]} · {user["role"]}'
        for user in users
    }
    actor_id = st.selectbox(
        "Demo actor",
        list(user_labels),
        index=(
            list(user_labels).index(current_owner_user_id)
            if current_owner_user_id in user_labels
            else 0
        ),
        format_func=lambda user_id: user_labels[user_id],
        key="requests_demo_actor",
        help="Used only to demonstrate action attribution in request history; this is not authentication.",
    )
    st.caption("Demo actor selection demonstrates traceability, not access control.")
    return actor_id


def _render_assign_action(
    connection: Any,
    request: dict[str, Any],
    users: list[dict[str, Any]],
) -> None:
    officers = [user for user in users if user["role"] == "Procurement Officer"]
    managers = [
        user
        for user in users
        if user["role"] in ("Procurement Manager", "Administrator")
    ]
    with st.expander("Assign request", expanded=True):
        with st.form("requests_assign_form"):
            manager_labels = {
                user["user_id"]: f'{user["display_name"]} · {user["role"]}'
                for user in managers
            }
            officer_labels = {user["user_id"]: user["display_name"] for user in officers}
            assigned_by = st.selectbox(
                "Assigned by",
                list(manager_labels),
                format_func=lambda user_id: manager_labels[user_id],
                key="requests_assign_actor",
            )
            owner_id = st.selectbox(
                "Procurement owner",
                list(officer_labels),
                format_func=lambda user_id: officer_labels[user_id],
                key="requests_assign_owner",
            )
            submitted = st.form_submit_button("Assign request", type="primary")
        if submitted:
            try:
                assign_request(
                    connection,
                    request["request_id"],
                    procurement_owner_user_id=owner_id,
                    assigned_by_user_id=assigned_by,
                )
            except ValidationError as error:
                _render_action_error(error)
            else:
                _action_success(
                    f'Request assigned to {officer_labels[owner_id]} and moved to Assigned.'
                )


def _render_start_work_action(connection: Any, request: dict[str, Any], actor_id: Any) -> None:
    with st.expander("Start work", expanded=True):
        with st.form("requests_start_work_form"):
            st.caption("Moves the request from Assigned to In Progress and records history.")
            submitted = st.form_submit_button("Start work", type="primary")
        if submitted:
            try:
                transition_request_status(
                    connection,
                    request["request_id"],
                    new_status="In Progress",
                    updated_by_user_id=actor_id,
                )
            except ValidationError as error:
                _render_action_error(error)
            else:
                _action_success("Request moved to In Progress.")


def _render_current_work_action(connection: Any, request: dict[str, Any], actor_id: Any) -> None:
    with st.expander("Update current work"):
        with st.form("requests_work_form"):
            has_dependency = st.checkbox(
                "A current dependency requires follow-up",
                value=bool(request["current_dependency"]),
                key="requests_work_has_dependency",
            )
            dependency_type = st.selectbox(
                "Dependency type",
                config.DEPENDENCY_TYPES,
                index=(
                    config.DEPENDENCY_TYPES.index(request["dependency_type"])
                    if request["dependency_type"] in config.DEPENDENCY_TYPES
                    else 0
                ),
                key="requests_work_dependency_type",
            )
            current_dependency = st.text_area(
                "Current dependency",
                value=request["current_dependency"] or "",
                key="requests_work_dependency",
            )
            left, right = st.columns(2)
            dependency_owner = left.text_input(
                "Dependency owner",
                value=request["dependency_owner"] or "",
                key="requests_work_dependency_owner",
            )
            next_action = right.text_input(
                "Next action",
                value=request["next_action"] or "",
                key="requests_work_next_action",
            )
            follow_up_date = st.date_input(
                "Follow-up date",
                value=request["follow_up_date"] or DEMO_AS_OF_DATE,
                key="requests_work_follow_up_date",
                help="The next date to follow up on the current dependency.",
            )
            has_target = st.checkbox(
                "Target completion date applies",
                value=request["target_completion_date"] is not None,
                key="requests_work_has_target",
            )
            target_completion_date = st.date_input(
                "Target completion date",
                value=request["target_completion_date"] or request["required_by_date"],
                key="requests_work_target_date",
                help="The planned completion date; it does not automatically change status.",
            )
            route_options = ("Not set",) + config.PROCUREMENT_ROUTES
            route_value = request["procurement_route"] or "Not set"
            route = st.selectbox(
                "Procurement route",
                route_options,
                index=route_options.index(route_value),
                key="requests_work_route",
            )
            officer_note = st.text_area(
                "Officer note",
                value=request["officer_note"] or "",
                key="requests_work_note",
            )
            submitted = st.form_submit_button("Save current work", type="primary")
        if submitted:
            changes = {
                "dependency_type": dependency_type if has_dependency else None,
                "current_dependency": _optional_text(current_dependency) if has_dependency else None,
                "dependency_owner": _optional_text(dependency_owner) if has_dependency else None,
                "next_action": _optional_text(next_action) if has_dependency else None,
                "follow_up_date": follow_up_date if has_dependency else None,
                "target_completion_date": target_completion_date if has_target else None,
                "procurement_route": None if route == "Not set" else route,
                "officer_note": _optional_text(officer_note),
            }
            try:
                update_request(
                    connection,
                    request["request_id"],
                    updated_by_user_id=actor_id,
                    **changes,
                )
            except ValidationError as error:
                _render_action_error(error)
            else:
                _action_success("Current work updated and recorded in request history.")


def _render_approval_action(connection: Any, request: dict[str, Any], actor_id: Any) -> None:
    with st.expander("Record approval confirmation"):
        with st.form("requests_approval_form"):
            approval_required = st.checkbox(
                "Approval is required",
                value=request["approval_required"],
                key="requests_approval_required",
            )
            approval_requirement = st.text_input(
                "Approval requirement",
                value=request["approval_requirement"] or "",
                key="requests_approval_requirement",
            )
            statuses = ("Not Confirmed", "Confirmed")
            current_status = (
                request["approval_status"]
                if request["approval_status"] in statuses
                else "Not Confirmed"
            )
            approval_status = st.selectbox(
                "Approval status",
                statuses,
                index=statuses.index(current_status),
                key="requests_approval_status",
            )
            left, right = st.columns(2)
            approval_source = left.text_input(
                "Approval source",
                value=request["approval_source"] or "",
                key="requests_approval_source",
            )
            approval_reference = right.text_input(
                "Approval reference",
                value=request["approval_reference"] or "",
                key="requests_approval_reference",
            )
            confirmation_date = st.date_input(
                "Approval confirmation date",
                value=(
                    request["approval_confirmation_date"].date()
                    if request["approval_confirmation_date"]
                    else DEMO_AS_OF_DATE
                ),
                key="requests_approval_confirmation_date",
            )
            approval_notes = st.text_area(
                "Approval notes",
                value=request["approval_notes"] or "",
                key="requests_approval_notes",
            )
            st.caption("This records confirmation only; ProcureFlow does not grant approval.")
            submitted = st.form_submit_button("Save approval information", type="primary")
        if submitted:
            changes = {
                "approval_required": approval_required,
                "approval_requirement": _optional_text(approval_requirement) if approval_required else None,
                "approval_status": approval_status if approval_required else "Not Required",
                "approval_source": _optional_text(approval_source) if approval_required else None,
                "approval_reference": _optional_text(approval_reference) if approval_required else None,
                "approval_confirmation_date": (
                    _as_confirmation_datetime(confirmation_date)
                    if approval_required and approval_status == "Confirmed"
                    else None
                ),
                "approval_notes": _optional_text(approval_notes) if approval_required else None,
            }
            try:
                update_request(
                    connection,
                    request["request_id"],
                    updated_by_user_id=actor_id,
                    **changes,
                )
            except ValidationError as error:
                _render_action_error(error)
            else:
                _action_success("Approval confirmation information updated.")


def _render_reference_action(connection: Any, request: dict[str, Any], actor_id: Any) -> None:
    with st.expander("Add related reference"):
        with st.form("requests_reference_form"):
            reference_type = st.selectbox(
                "Reference type",
                config.REFERENCE_TYPES,
                key="requests_reference_type",
            )
            reference_number = st.text_input("Reference number", key="requests_reference_number")
            source = st.text_input(
                "Source system or process",
                key="requests_reference_source",
            )
            link = st.text_input(
                "Reference link",
                placeholder="https://example.invalid/record",
                key="requests_reference_link",
            )
            closure_evidence = st.checkbox(
                "Use as closure evidence",
                key="requests_reference_closure_evidence",
            )
            note = st.text_area("Reference note", key="requests_reference_note")
            st.caption("Only the link and identifier are stored; no document is uploaded.")
            submitted = st.form_submit_button("Add related reference", type="primary")
        if submitted:
            try:
                add_request_reference(
                    connection,
                    request["request_id"],
                    reference_type=reference_type,
                    reference_number=reference_number,
                    source_system_or_process=source,
                    reference_link=_optional_text(link),
                    is_closure_evidence=closure_evidence,
                    note=_optional_text(note),
                    added_by_user_id=actor_id,
                )
            except (ValidationError, Exception) as error:
                _render_action_error(error)
            else:
                _action_success(f"Related reference {reference_number.strip()} added.")


def _render_complete_action(connection: Any, request: dict[str, Any], actor_id: Any) -> None:
    with st.expander("Complete request"):
        with st.form("requests_complete_form"):
            closure_note = st.text_area(
                "Closure note",
                value=request["closure_note"] or "",
                key="requests_completion_note",
            )
            evidence_confirmed = st.checkbox(
                "Required closure evidence is confirmed",
                value=request["closure_evidence_confirmed"],
                disabled=not request["closure_evidence_required"],
                key="requests_completion_evidence_confirmed",
            )
            if request["closure_evidence_required"]:
                st.caption(
                    "Completion requires confirmation and at least one related reference marked as closure evidence."
                )
            submitted = st.form_submit_button("Complete request", type="primary")
        if submitted:
            if not request["procurement_route"]:
                st.error("Completion is blocked until a procurement route is recorded.")
            elif not closure_note.strip():
                st.error("Completion is blocked until a closure note is recorded.")
            elif request["closure_evidence_required"] and not evidence_confirmed:
                st.error("Completion is blocked until required closure evidence is confirmed.")
            elif (
                request["closure_evidence_required"]
                and request["closure_evidence_reference_count"] < 1
            ):
                st.error(
                    "Completion is blocked until a related reference is marked as closure evidence."
                )
            else:
                try:
                    update_request(
                        connection,
                        request["request_id"],
                        updated_by_user_id=actor_id,
                        closure_note=closure_note.strip(),
                        closure_evidence_confirmed=(
                            evidence_confirmed
                            if request["closure_evidence_required"]
                            else request["closure_evidence_confirmed"]
                        ),
                    )
                    transition_request_status(
                        connection,
                        request["request_id"],
                        new_status="Completed",
                        updated_by_user_id=actor_id,
                    )
                except ValidationError as error:
                    _render_action_error(error)
                else:
                    _action_success("Request completed. Dashboard reporting now uses the updated state.")


def _render_cancel_action(connection: Any, request: dict[str, Any], actor_id: Any) -> None:
    with st.expander("Cancel request"):
        with st.form("requests_cancel_form"):
            reason = st.selectbox(
                "Cancellation reason",
                config.CANCELLATION_REASONS,
                key="requests_cancel_reason",
            )
            st.caption("Cancelled is terminal in this prototype.")
            submitted = st.form_submit_button("Cancel request")
        if submitted:
            try:
                transition_request_status(
                    connection,
                    request["request_id"],
                    new_status="Cancelled",
                    updated_by_user_id=actor_id,
                    cancellation_reason=reason,
                )
            except ValidationError as error:
                _render_action_error(error)
            else:
                _action_success(f"Request cancelled: {reason}.")


def _render_workflow_actions(
    connection: Any,
    request: dict[str, Any],
    users: list[dict[str, Any]],
    writable: bool,
) -> None:
    st.markdown("## Procurement workflow actions")
    if not writable:
        st.info("Create a local demo workspace to enable controlled workflow actions.")
        return
    if request["lifecycle_status"] in config.TERMINAL_STATUSES:
        st.info(
            f'{request["lifecycle_status"]} requests are terminal and available for read-only review.'
        )
        return
    actor_id = _render_actor_selector(
        users,
        current_owner_user_id=request.get("procurement_owner_user_id"),
    )
    if request["lifecycle_status"] == "Submitted":
        st.caption(
            "An authorized procurement user assigns the submitted request "
            "to one procurement officer."
        )
        _render_assign_action(connection, request, users)
    if request["lifecycle_status"] == "Assigned":
        _render_start_work_action(connection, request, actor_id)
    if request["lifecycle_status"] in ("Assigned", "In Progress"):
        _render_current_work_action(connection, request, actor_id)
        _render_approval_action(connection, request, actor_id)
        _render_reference_action(connection, request, actor_id)
    if request["lifecycle_status"] == "In Progress":
        _render_complete_action(connection, request, actor_id)
    _render_cancel_action(connection, request, actor_id)


def _render_request_detail(
    connection: Any,
    detail: dict[str, Any],
    writable: bool,
) -> None:
    request = detail["request"]
    st.button(
        "← Back to requests",
        key="requests_back_to_list",
        on_click=_close_request,
    )
    st.markdown(
        f'<div class="pf-detail-eyebrow">Request detail</div>'
        f'<h2 class="pf-detail-title">{escape(request["request_number"])} · '
        f'{escape(request["request_title"])}</h2>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Lifecycle status shows where the request is. Dependencies, next actions "
        "and dates show what requires follow-up."
    )
    message = st.session_state.pop("requests_action_message", None)
    if message:
        st.success(message)

    if request["lifecycle_status"] == "Submitted":
        st.info(
            "Requestor step complete. This request is now awaiting assignment "
            "by an authorized procurement user."
        )
    _render_attention_summary(detail)
    _render_overview(request)
    _render_ownership(request)
    _render_current_work(request)
    _render_approval(request)
    _render_references(detail)
    _render_closure(request)
    users = list_active_app_users(connection)
    _render_workflow_actions(connection, request, users, writable)
    _render_history(detail)


def render_requests() -> None:
    """Render the Request List or its routed Request Detail state."""

    load_application_styles()
    _render_header()
    database_path = resolve_database_path()
    writable = _is_writable_workspace(database_path)
    _render_workspace_notice(database_path, writable)
    _render_workspace_controls(database_path, writable)

    if not database_path.is_file():
        st.warning("ProcureFlow demo setup is required.")
        st.write(f"Database not found: `{database_path}`")
        return

    try:
        connection = connect_database(database_path)
    except Exception as error:  # pragma: no cover - Streamlit setup state
        st.error("The request workspace could not connect to the configured database.")
        st.caption(str(error))
        return

    try:
        if tuple(list_table_names(connection)) != EXPECTED_TABLES:
            st.warning("ProcureFlow demo setup is required.")
            st.write("The configured database does not contain the approved four-table schema.")
            return
        options = get_filter_options(connection)
        selected_request_id = st.session_state.get(SELECTED_REQUEST_KEY)
        if st.session_state.get(INTAKE_STATE_KEY):
            _render_intake(
                connection,
                list_active_app_users(connection),
                writable,
            )
        elif selected_request_id:
            detail = get_enriched_request(
                connection,
                selected_request_id,
                as_of=DEMO_AS_OF_DATE,
            )
            if detail is None:
                st.session_state.pop(SELECTED_REQUEST_KEY, None)
                st.warning("The selected request is no longer available.")
                _render_request_list(connection, options)
            else:
                _render_request_detail(connection, detail, writable)
        else:
            _render_request_list(connection, options)
    except Exception as error:  # pragma: no cover - defensive rendered state
        st.error("The request workspace could not load the current data.")
        st.caption(str(error))
    finally:
        connection.close()


if __name__ == "__main__":
    render_requests()
