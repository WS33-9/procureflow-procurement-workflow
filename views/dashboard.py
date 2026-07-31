"""Default ProcureFlow Dashboard page composition."""

from __future__ import annotations

from datetime import date
from html import escape

import streamlit as st

from src.database import connect_database, list_table_names
from src.queries import (
    get_dashboard_summary,
    get_filter_options,
    list_enriched_requests,
)
from src.rules import RULE_CODES
from src.ui import (
    EXPECTED_TABLES,
    attention_chart,
    category_chart,
    format_cad,
    format_cad_compact,
    lifecycle_chart,
    load_application_styles,
    owner_workload_chart,
    prepare_attention_table,
    prioritize_attention_requests,
    resolve_database_path,
)


DEMO_AS_OF_DATE = date(2026, 7, 30)

FILTER_KEYS = (
    "dashboard_lifecycle_statuses",
    "dashboard_priorities",
    "dashboard_business_units",
    "dashboard_request_categories",
    "dashboard_owner_ids",
    "dashboard_include_completed",
    "dashboard_include_cancelled",
)


def _reset_filters() -> None:
    for key in FILTER_KEYS:
        st.session_state.pop(key, None)


def _render_header() -> None:
    st.markdown(
        """
        <section class="pf-header">
          <div class="pf-eyebrow">
            Enterprise procurement workflow implementation case
          </div>
          <div class="pf-header__body">
            <h1>ProcureFlow</h1>
            <p>
              A fictional SaaS prototype demonstrating how a shared
              operational layer can clarify ownership, surface requests
              requiring attention, and provide timely management visibility
              across the procurement request lifecycle.
            </p>
          </div>
          <div class="pf-context-labels" aria-label="Prototype context">
            <span>Synthetic demo data</span>
            <span>Demo data snapshot · July 30, 2026</span>
            <span>Dashboard preview</span>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_scope_notice() -> None:
    st.markdown(
        """
        <section class="pf-boundary" role="note">
          <strong>Implementation boundary</strong>
          <span>
            ProcureFlow coordinates operational workflow around ERP, approval,
            sourcing, contracting, and official-record systems. It does not
            replace those systems or store the official records they govern.
          </span>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_setup_state(message: str) -> None:
    st.warning("ProcureFlow demo setup is required.")
    st.write(message)
    st.caption(
        "Select a valid initialized ProcureFlow database through "
        "PROCUREFLOW_DATABASE_PATH, or create the approved deterministic "
        "demo database before starting the application."
    )


def _render_filters(options: dict) -> dict:
    st.sidebar.markdown("## Filters")

    lifecycle_statuses = st.sidebar.multiselect(
        "Lifecycle status",
        options["lifecycle_statuses"],
        key="dashboard_lifecycle_statuses",
    )
    priorities = st.sidebar.multiselect(
        "Priority",
        options["priorities"],
        key="dashboard_priorities",
    )
    business_units = st.sidebar.multiselect(
        "Business unit",
        options["business_units"],
        key="dashboard_business_units",
    )
    request_categories = st.sidebar.multiselect(
        "Request category",
        options["request_categories"],
        key="dashboard_request_categories",
    )

    officer_names = {
        officer["owner_user_id"]: officer["owner_name"]
        for officer in options["procurement_officers"]
    }
    owner_ids = st.sidebar.multiselect(
        "Procurement owner",
        list(officer_names),
        format_func=lambda owner_id: officer_names[owner_id],
        key="dashboard_owner_ids",
    )
    st.sidebar.markdown(
        '<div class="pf-filter-group-label">Include closed records</div>',
        unsafe_allow_html=True,
    )
    closed_status_columns = st.sidebar.columns(2)
    include_completed = closed_status_columns[0].checkbox(
        "Completed",
        value=True,
        key="dashboard_include_completed",
    )
    include_cancelled = closed_status_columns[1].checkbox(
        "Cancelled",
        value=True,
        key="dashboard_include_cancelled",
    )
    st.sidebar.button(
        "Reset filters",
        type="secondary",
        width="stretch",
        on_click=_reset_filters,
    )
    st.sidebar.caption("Empty selections mean no restriction.")

    return {
        "lifecycle_statuses": lifecycle_statuses,
        "priorities": priorities,
        "business_units": business_units,
        "request_categories": request_categories,
        "procurement_owner_user_ids": owner_ids,
        "include_completed": include_completed,
        "include_cancelled": include_cancelled,
    }


def _render_primary_kpis(summary: dict) -> None:
    st.markdown(
        '<div class="pf-section-label">Operating position</div>',
        unsafe_allow_html=True,
    )
    columns = st.columns([0.9, 1.35, 0.9, 1.15])
    columns[0].metric("Open requests", summary["open_requests"])
    columns[1].markdown(
        '<span class="pf-kpi-marker pf-kpi-marker--attention"></span>',
        unsafe_allow_html=True,
    )
    columns[1].metric(
        "Requests requiring attention",
        summary["requests_requiring_attention"],
        help=(
            f"{summary['total_attention_results']} total attention results "
            "across distinct requests."
        ),
    )
    columns[2].markdown(
        '<span class="pf-kpi-marker pf-kpi-marker--ownership"></span>',
        unsafe_allow_html=True,
    )
    columns[2].metric(
        "Unassigned requests",
        summary["unassigned_requests"],
    )
    columns[3].markdown(
        '<span class="pf-kpi-marker pf-kpi-marker--priority"></span>',
        unsafe_allow_html=True,
    )
    columns[3].metric(
        "High-priority requests requiring attention",
        summary["high_priority_requests_requiring_attention"],
    )
def _render_secondary_kpis(summary: dict) -> None:
    st.markdown(
        '<div class="pf-secondary-label">Operational context</div>',
        unsafe_allow_html=True,
    )
    columns = st.columns(4)
    for column in columns:
        column.markdown(
            '<span class="pf-kpi-marker pf-kpi-marker--secondary"></span>',
            unsafe_allow_html=True,
        )
    columns[0].metric(
        "Overdue follow-ups",
        summary["overdue_follow_ups"],
    )
    columns[1].metric(
        "Missed target dates",
        summary["missed_target_dates"],
    )
    columns[2].metric(
        "Approvals not confirmed",
        summary["approvals_not_confirmed"],
    )
    columns[3].metric(
        "Open estimated value",
        format_cad_compact(summary["total_open_estimated_value"]),
        help=(
            f"Exact recorded value: "
            f"{format_cad(summary['total_open_estimated_value'])}. "
            "Indicative operational estimate; not an audited financial total."
        ),
    )


def _render_charts(summary: dict) -> None:
    st.markdown("## Operational overview")
    left, right = st.columns([1, 1.5], gap="large")
    with left:
        st.markdown("### Lifecycle distribution")
        st.altair_chart(
            lifecycle_chart(summary["counts_by_lifecycle_status"]),
            width="stretch",
        )
    with right:
        st.markdown("### Requests requiring attention")
        st.altair_chart(
            attention_chart(summary["attention_counts_by_rule"]),
            width="stretch",
        )
        st.caption(
            "Operational conditions are ordered by count. The completed-"
            "request exception represents a limited legacy or imported "
            "data-quality issue."
        )
        with st.expander("How attention is determined"):
            st.markdown(
                """
                - **Assignment overdue:** still Submitted after more than one business day.
                - **Follow-up overdue:** the recorded follow-up date for the current dependency has passed.
                - **Target completion missed:** the target completion date has passed.
                - **Required information outstanding:** the current dependency is missing required request information.
                - **Approval not confirmed:** approval is required but confirmation has not been recorded.
                - **No update in 7 days:** seven calendar days have elapsed since the last meaningful update.
                - **High-priority dependency overdue:** a High or Urgent request has an overdue dependency follow-up.
                - **Completed request missing closure evidence:** a legacy/imported data-quality exception.
                """
            )

    left, right = st.columns([1.35, 1], gap="large")
    with left:
        st.markdown("### Owner workload")
        st.altair_chart(
            owner_workload_chart(summary["owner_workload"]),
            width="stretch",
        )
        st.caption(
            "Workload counts show current queue volume, not employee "
            "performance."
        )
    with right:
        st.markdown("### Request category distribution")
        st.altair_chart(
            category_chart(summary["counts_by_request_category"]),
            width="stretch",
        )


def _render_attention_table(requests: list[dict]) -> None:
    st.markdown("## Requests requiring attention")
    prioritized = prioritize_attention_requests(requests, limit=8)
    if not prioritized:
        st.success(
            "No requests require attention for the selected filters."
        )
        return

    st.caption(
        f"{len(requests)} requests require attention, producing "
        f"{sum(request['attention_count'] for request in requests)} attention "
        "conditions because one request may meet more than one rule. "
        "Records are prioritized by attention count, priority, and request "
        "number."
    )
    table_rows = prepare_attention_table(prioritized)
    columns = ("Request", "Priority", "Owner", "Attention", "Next action", "Due")
    column_widths = (19, 8, 11, 22, 28, 12)
    colgroup = "".join(
        f'<col style="width:{width}%">' for width in column_widths
    )
    headers = "".join(
        f'<th scope="col">{escape(column)}</th>' for column in columns
    )
    body_rows = []
    for row in table_rows:
        request_cell = (
            f'<span class="pf-request-number">{escape(row["Request number"])}</span>'
            f'<span class="pf-primary-text">{escape(row["Request title"])}</span>'
            f'<span class="pf-secondary-text">{escape(row["Status"])}</span>'
        )
        priority = escape(row["Priority"])
        priority_class = row["Priority"].lower()
        priority_cell = (
            f'<span class="pf-table-tag pf-table-tag--{priority_class}">'
            f"{priority}</span>"
        )
        owner = escape(row["Owner"])
        owner_cell = owner
        if row["Owner"] == "Unassigned":
            owner_cell = (
                '<span class="pf-table-tag '
                'pf-table-tag--unassigned">Unassigned</span>'
            )

        attention_title = escape(
            "; ".join(row["All attention labels"]),
            quote=True,
        )
        attention_items = "".join(
            f"<span>{escape(label)}</span>"
            for label in row["Attention labels"]
        )
        if row["Additional attention count"]:
            attention_items += (
                '<span class="pf-attention-more">+'
                f'{row["Additional attention count"]} more</span>'
            )
        attention_cell = (
            f'<div class="pf-attention-list" title="{attention_title}" '
            f'aria-label="{attention_title}">{attention_items}</div>'
        )

        next_action_cell = (
            f'<span class="pf-primary-text">{escape(row["Next action"])}</span>'
        )
        if row["Dependency"]:
            next_action_cell += (
                '<span class="pf-secondary-text pf-clamp-two">'
                f'{escape(row["Dependency"])}</span>'
            )

        due_cell = f'<span class="pf-due-date">{escape(row["Due date"])}</span>'
        if row["Due label"]:
            due_cell += (
                f'<span class="pf-secondary-text">{escape(row["Due label"])}</span>'
            )

        body_rows.append(
            "<tr>"
            f'<td>{request_cell}</td>'
            f'<td>{priority_cell}</td>'
            f'<td>{owner_cell}</td>'
            f'<td class="pf-attention-reasons">{attention_cell}</td>'
            f'<td>{next_action_cell}</td>'
            f'<td>{due_cell}</td>'
            "</tr>"
        )

    st.markdown(
        (
            '<div class="pf-table-scroll" tabindex="0" '
            'aria-label="Prioritized requests requiring attention">'
            '<table class="pf-attention-table">'
            f"<colgroup>{colgroup}</colgroup>"
            f"<thead><tr>{headers}</tr></thead>"
            f"<tbody>{''.join(body_rows)}</tbody>"
            "</table></div>"
        ),
        unsafe_allow_html=True,
    )


def _render_implementation_context() -> None:
    st.markdown("## Implementation context")
    st.markdown(
        """
        <section class="pf-implementation-context">
          <div class="pf-context-card">
            <strong>Shared workflow record</strong>
            <span>
              Intake, ownership, dependencies, next actions, dates,
              references, and closure status.
            </span>
          </div>
          <div class="pf-context-card">
            <strong>System boundary</strong>
            <span>
              Formal approvals, financial transactions, sourcing, contracts,
              and official documents remain in their existing systems.
            </span>
          </div>
          <div class="pf-context-card">
            <strong>Prototype assumption</strong>
            <span>
              Controlled values and attention thresholds are centrally
              configured and would be validated during discovery.
            </span>
          </div>
          <div class="pf-context-card">
            <strong>Value created</strong>
            <span>
              ProcureFlow is designed to improve ownership clarity, surface
              issues earlier, reduce manual status consolidation, and support
              more consistent operational reporting around formal procurement
              systems.
            </span>
          </div>
          <div class="pf-context-card">
            <strong>Next validation step</strong>
            <span>
              Confirm the proposed workflow, roles, required fields, attention
              thresholds, system boundaries, and reporting priorities with
              representative users before expanding the prototype.
            </span>
          </div>
          <div class="pf-implementation-note">
            <strong>Status and follow-up</strong>
            <span>
              Lifecycle status shows where the request is. Dependencies, next
              actions and dates show what requires follow-up; a missed date
              does not automatically change the lifecycle status.
            </span>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_dashboard() -> None:
    """Render the single approved ProcureFlow Dashboard page."""
    load_application_styles()
    _render_header()
    _render_scope_notice()

    database_path = resolve_database_path()
    if not database_path.exists() or not database_path.is_file():
        _render_setup_state(
            "The selected ProcureFlow database could not be found."
        )
        return

    connection = None
    try:
        connection = connect_database(database_path)
        table_names = list_table_names(connection)
        if table_names != list(EXPECTED_TABLES):
            _render_setup_state(
                "The selected database does not contain the approved "
                "ProcureFlow four-table structure."
            )
            return

        options = get_filter_options(connection)
        filters = _render_filters(options)
        summary = get_dashboard_summary(
            connection,
            as_of=DEMO_AS_OF_DATE,
            filters=filters,
        )
        if summary["total_requests"] == 0:
            st.info(
                "No requests match the selected filters. Reset the filters "
                "or adjust your selections to view results."
            )
            return

        attention_requests = list_enriched_requests(
            connection,
            as_of=DEMO_AS_OF_DATE,
            attention_rule_codes=RULE_CODES,
            sort_by="request_number",
            sort_direction="asc",
            **filters,
        )

        _render_primary_kpis(summary)
        _render_secondary_kpis(summary)
        _render_charts(summary)
        _render_attention_table(attention_requests)
        _render_implementation_context()
    except Exception:
        st.error(
            "The ProcureFlow Dashboard could not be loaded from the selected "
            "database."
        )
        st.caption(
            "Confirm that the configured file is a valid initialized "
            "ProcureFlow database and try again."
        )
    finally:
        if connection is not None:
            connection.close()
