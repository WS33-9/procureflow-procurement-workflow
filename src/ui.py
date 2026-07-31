"""Presentation helpers for the ProcureFlow Streamlit application."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import altair as alt
import streamlit as st

from src import config
from src.rules import RULE_CODES


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEMO_DATABASE_PATH = (
    PROJECT_ROOT / "database" / "procureflow_demo.duckdb"
)
DEMO_SESSION_DIRECTORY = PROJECT_ROOT / "database" / "demo_sessions"
ACTIVE_DATABASE_STATE_KEY = "procureflow_active_database_path"
STYLESHEET_PATH = PROJECT_ROOT / "assets" / "styles.css"

EXPECTED_TABLES = (
    "app_users",
    "procurement_requests",
    "request_history",
    "request_references",
)

ACCENT_COLOR = "#167A72"
NAVY_COLOR = "#17324D"
MUTED_COLOR = "#6B7A89"
LIGHT_TEAL = "#B9DDD8"
AMBER_COLOR = "#B7791F"
GREEN_COLOR = "#3E7C59"
SLATE_COLOR = "#7B8995"
CHART_FONT = "Inter, Aptos, Segoe UI, system-ui, sans-serif"
APPLICATION_ZONE = ZoneInfo(config.APPLICATION_TIMEZONE)

ATTENTION_LABELS = {
    "assignment_overdue": "Assignment overdue",
    "follow_up_overdue": "Follow-up overdue",
    "target_completion_missed": "Target completion missed",
    "required_information_outstanding": "Required information outstanding",
    "required_approval_not_confirmed": "Approval not confirmed",
    "no_recent_update": "No update in 7 days",
    "high_priority_overdue_dependency": "High-priority dependency overdue",
    "completed_missing_closure_evidence": (
        "Completed request missing closure evidence"
    ),
}

PRIORITY_RANK = {
    "Urgent": 0,
    "High": 1,
    "Medium": 2,
    "Low": 3,
}


def resolve_database_path() -> Path:
    """Return the configured application database without creating it."""
    configured_path = os.environ.get("PROCUREFLOW_DATABASE_PATH")
    if configured_path and configured_path.strip():
        return Path(configured_path).expanduser()
    active_path = st.session_state.get(ACTIVE_DATABASE_STATE_KEY)
    if active_path:
        return Path(active_path).expanduser()
    return DEFAULT_DEMO_DATABASE_PATH


def relevant_due(request: dict[str, Any]) -> tuple[str, str]:
    """Return the most decision-relevant due date and concise label."""

    attention_date, attention_label = _attention_due(request)
    if attention_date != "—":
        return attention_date, attention_label

    candidates = (
        (request.get("follow_up_date"), "Follow-up"),
        (request.get("target_completion_date"), "Target"),
        (request.get("required_by_date"), "Required by"),
    )
    for value, label in candidates:
        if value is not None:
            return format_display_date(value), label
    return "—", ""


def attention_labels(request: dict[str, Any]) -> list[str]:
    """Return business-facing attention labels without exposing rule codes."""

    return [
        ATTENTION_LABELS.get(code, reason)
        for code, reason in zip(
            request.get("attention_rule_codes", ()),
            request.get("attention_reasons", ()),
            strict=True,
        )
    ]


def load_application_styles() -> None:
    """Load the centralized application stylesheet when available."""
    if STYLESHEET_PATH.exists():
        st.markdown(
            f"<style>{STYLESHEET_PATH.read_text(encoding='utf-8')}</style>",
            unsafe_allow_html=True,
        )


def format_cad(value: Decimal | int | float | None) -> str:
    """Format an indicative value in Canadian dollars."""
    amount = Decimal("0.00") if value is None else Decimal(str(value))
    return f"CAD {amount:,.0f}"


def format_cad_compact(value: Decimal | int | float | None) -> str:
    """Format an indicative CAD value compactly for a KPI card."""
    amount = Decimal("0.00") if value is None else Decimal(str(value))
    absolute_amount = abs(amount)
    if absolute_amount >= Decimal("1000000"):
        return f"CAD {amount / Decimal('1000000'):.2f}M"
    if absolute_amount >= Decimal("1000"):
        return f"CAD {amount / Decimal('1000'):.1f}K"
    return format_cad(amount)


def format_display_date(value: date | datetime | None) -> str:
    if value is None:
        return "—"
    display_date = value.date() if isinstance(value, datetime) else value
    return display_date.strftime("%b %d, %Y").replace(" 0", " ")


def prioritize_attention_requests(
    requests: list[dict[str, Any]],
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Apply the approved presentation priority to attention records."""
    return sorted(
        requests,
        key=lambda request: (
            -request["attention_count"],
            PRIORITY_RANK.get(request["priority"], 99),
            request["request_number"],
        ),
    )[:limit]


def _add_business_days(start_date: date, business_days: int) -> date:
    result = start_date
    added = 0
    while added < business_days:
        result += timedelta(days=1)
        if result.weekday() < 5:
            added += 1
    return result


def _local_date(value: date | datetime | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(APPLICATION_ZONE).date()
    return value


def _attention_due(request: dict[str, Any]) -> tuple[str, str]:
    codes = set(request["attention_rule_codes"])
    candidates: list[tuple[date, str]] = []

    if "assignment_overdue" in codes:
        submitted_date = _local_date(request.get("submitted_at"))
        if submitted_date is not None:
            threshold = config.ATTENTION_RULE_THRESHOLDS[
                "assignment_overdue_business_days"
            ]
            candidates.append(
                (_add_business_days(submitted_date, threshold), "Assignment")
            )

    follow_up_date = _local_date(request.get("follow_up_date"))
    if follow_up_date is not None and codes.intersection(
        {
            "follow_up_overdue",
            "required_information_outstanding",
            "high_priority_overdue_dependency",
        }
    ):
        candidates.append((follow_up_date, "Follow-up"))

    target_date = _local_date(request.get("target_completion_date"))
    if target_date is not None and "target_completion_missed" in codes:
        candidates.append((target_date, "Target"))

    if not candidates:
        return "—", ""

    due_date, due_label = min(candidates, key=lambda item: item[0])
    return format_display_date(due_date), due_label


def prepare_attention_table(
    requests: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return compact, business-facing attention queue rows."""
    rows = []
    for request in requests:
        attention_labels = [
            ATTENTION_LABELS.get(rule_code, reason)
            for rule_code, reason in zip(
                request["attention_rule_codes"],
                request["attention_reasons"],
                strict=True,
            )
        ]
        due_date, due_label = _attention_due(request)
        rows.append(
            {
                "Request number": request["request_number"],
                "Request title": request["request_title"],
                "Status": request["lifecycle_status"],
                "Priority": request["priority"],
                "Owner": request["procurement_owner_name"] or "Unassigned",
                "Attention labels": attention_labels[:2],
                "Additional attention count": max(
                    0,
                    len(attention_labels) - 2,
                ),
                "All attention labels": attention_labels,
                "Next action": request["next_action"] or "—",
                "Dependency": request["current_dependency"] or "",
                "Due date": due_date,
                "Due label": due_label,
            }
        )
    return rows


def _chart_properties(chart: alt.Chart, *, height: int = 300) -> alt.Chart:
    return (
        chart.properties(height=height)
        .configure_view(strokeWidth=0)
        .configure_axis(
            labelFont=CHART_FONT,
            labelColor=NAVY_COLOR,
            labelFontSize=12,
            titleColor=NAVY_COLOR,
            titleFont=CHART_FONT,
            titleFontSize=12,
            gridColor="#E8EDED",
            domainColor="#C8D2D2",
            tickColor="#C8D2D2",
        )
        .configure_legend(
            labelFont=CHART_FONT,
            labelColor=NAVY_COLOR,
            labelFontSize=12,
            titleColor=NAVY_COLOR,
            orient="bottom",
        )
        .configure_text(font=CHART_FONT)
    )


def lifecycle_chart(counts: dict[str, int]) -> alt.Chart:
    data = [
        {"Status": status, "Requests": counts.get(status, 0)}
        for status in config.LIFECYCLE_STATUSES
    ]
    maximum = max((item["Requests"] for item in data), default=1) or 1
    base = (
        alt.Chart(alt.Data(values=data))
        .encode(
            x=alt.X(
                "Status:N",
                sort=list(config.LIFECYCLE_STATUSES),
                title=None,
                axis=alt.Axis(
                    labelAngle=-20,
                    labelLimit=90,
                    labelOverlap=False,
                ),
            ),
            y=alt.Y(
                "Requests:Q",
                title="Requests",
                scale=alt.Scale(
                    domain=[0, maximum + max(1, round(maximum * 0.12))],
                    nice=True,
                    zero=True,
                ),
                stack=None,
            ),
            color=alt.Color(
                "Status:N",
                scale=alt.Scale(
                    domain=list(config.LIFECYCLE_STATUSES),
                    range=[
                        "#78909C",
                        "#5B8FA8",
                        ACCENT_COLOR,
                        GREEN_COLOR,
                        SLATE_COLOR,
                    ],
                ),
                legend=None,
            ),
            tooltip=["Status:N", "Requests:Q"],
        )
    )
    bars = base.mark_bar(
        cornerRadiusTopLeft=3,
        cornerRadiusTopRight=3,
    )
    labels = base.mark_text(
        color=NAVY_COLOR,
        dy=-8,
        fontSize=12,
        fontWeight=600,
    ).encode(text=alt.Text("Requests:Q", format="d"))
    chart = bars + labels
    return _chart_properties(chart)


def attention_chart(counts: dict[str, int]) -> alt.Chart:
    data = [
        {
            "Attention condition": ATTENTION_LABELS[code],
            "Results": counts.get(code, 0),
            "Condition type": (
                "Data-quality safeguard"
                if code == "completed_missing_closure_evidence"
                else "Operational condition"
            ),
            "Rule order": RULE_CODES.index(code),
        }
        for code in RULE_CODES
    ]
    data.sort(key=lambda item: (-item["Results"], item["Rule order"]))
    labels = [item["Attention condition"] for item in data]
    maximum = max((item["Results"] for item in data), default=1) or 1
    base = (
        alt.Chart(alt.Data(values=data))
        .encode(
            x=alt.X(
                "Results:Q",
                title="Attention results",
                scale=alt.Scale(
                    domain=[0, maximum + 1],
                    nice=False,
                    zero=True,
                ),
                stack=None,
            ),
            y=alt.Y(
                "Attention condition:N",
                sort=labels,
                title=None,
                axis=alt.Axis(labelLimit=280),
            ),
            color=alt.Color(
                "Condition type:N",
                scale=alt.Scale(
                    domain=[
                        "Operational condition",
                        "Data-quality safeguard",
                    ],
                    range=[NAVY_COLOR, AMBER_COLOR],
                ),
                legend=None,
            ),
            tooltip=["Attention condition:N", "Results:Q"],
        )
    )
    bars = base.mark_bar(cornerRadiusEnd=3)
    labels_layer = base.mark_text(
        align="left",
        color=NAVY_COLOR,
        dx=6,
        fontSize=12,
        fontWeight=600,
    ).encode(text=alt.Text("Results:Q", format="d"))
    chart = bars + labels_layer
    return _chart_properties(chart, height=300)


def owner_workload_chart(workload: list[dict[str, Any]]) -> alt.Chart:
    data = []
    for row in workload:
        data.extend(
            (
                {
                    "Owner": row["owner_name"],
                    "Measure": "Open requests",
                    "Requests": row["open_request_count"],
                },
                {
                    "Owner": row["owner_name"],
                    "Measure": "Require attention",
                    "Requests": row["attention_request_count"],
                },
            )
        )
    owner_order = [row["owner_name"] for row in workload]
    maximum = max((item["Requests"] for item in data), default=1) or 1
    base = (
        alt.Chart(alt.Data(values=data))
        .encode(
            x=alt.X(
                "Requests:Q",
                title="Requests",
                scale=alt.Scale(
                    domain=[0, maximum + 1],
                    nice=False,
                    zero=True,
                ),
                stack=None,
            ),
            y=alt.Y(
                "Owner:N",
                sort=owner_order,
                title=None,
                axis=alt.Axis(labelLimit=160),
            ),
            yOffset="Measure:N",
            color=alt.Color(
                "Measure:N",
                scale=alt.Scale(
                    domain=["Open requests", "Require attention"],
                    range=[ACCENT_COLOR, LIGHT_TEAL],
                ),
                title=None,
                legend=alt.Legend(orient="top", direction="horizontal"),
            ),
            tooltip=["Owner:N", "Measure:N", "Requests:Q"],
        )
    )
    bars = base.mark_bar(cornerRadiusEnd=2)
    labels = base.mark_text(
        align="left",
        color=NAVY_COLOR,
        dx=5,
        fontSize=11,
    ).encode(text=alt.Text("Requests:Q", format="d"))
    chart = bars + labels
    return _chart_properties(chart)


def category_chart(counts: dict[str, int]) -> alt.Chart:
    categories = list(config.REQUEST_CATEGORIES)
    data = [
        {"Request category": category, "Requests": counts.get(category, 0)}
        for category in categories
    ]
    data.sort(
        key=lambda item: (
            -item["Requests"],
            categories.index(item["Request category"]),
        )
    )
    ordered_categories = [item["Request category"] for item in data]
    maximum = max((item["Requests"] for item in data), default=1) or 1
    base = (
        alt.Chart(alt.Data(values=data))
        .encode(
            x=alt.X(
                "Requests:Q",
                title="Requests",
                scale=alt.Scale(
                    domain=[0, maximum + 1],
                    nice=False,
                    zero=True,
                ),
                stack=None,
            ),
            y=alt.Y(
                "Request category:N",
                sort=ordered_categories,
                title=None,
                axis=alt.Axis(labelLimit=270),
            ),
            tooltip=["Request category:N", "Requests:Q"],
        )
    )
    bars = base.mark_bar(color=ACCENT_COLOR, cornerRadiusEnd=3)
    labels = base.mark_text(
        align="left",
        color=NAVY_COLOR,
        dx=6,
        fontSize=12,
        fontWeight=600,
    ).encode(text=alt.Text("Requests:Q", format="d"))
    chart = bars + labels
    return _chart_properties(chart)
