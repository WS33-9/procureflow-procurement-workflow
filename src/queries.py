"""Read-only query and service helpers for the ProcureFlow prototype.

All functions accept an existing DuckDB connection. Attention is calculated
in Python by :mod:`src.rules` and is never stored in the database.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import duckdb

from src import config
from src.rules import (
    FOLLOW_UP_OVERDUE,
    REQUIRED_APPROVAL_NOT_CONFIRMED,
    RULE_CODES,
    TARGET_COMPLETION_MISSED,
    evaluate_request_attention,
)


OPEN_STATUSES = ("Submitted", "Assigned", "In Progress")

SORT_FIELDS = {
    "request_number",
    "request_title",
    "requestor_name",
    "business_unit",
    "request_category",
    "estimated_value",
    "priority",
    "required_by_date",
    "submitted_at",
    "lifecycle_status",
    "procurement_owner_name",
    "assignment_date",
    "procurement_route",
    "follow_up_date",
    "target_completion_date",
    "approval_status",
    "updated_at",
    "attention_count",
}

DASHBOARD_FILTER_FIELDS = {
    "lifecycle_statuses",
    "priorities",
    "business_units",
    "request_categories",
    "procurement_owner_user_ids",
    "procurement_routes",
    "attention_rule_codes",
    "search_text",
    "include_completed",
    "include_cancelled",
}


class QueryValidationError(ValueError):
    """Raised when a query option is not supported or is malformed."""


def _fetch_dicts(
    connection: duckdb.DuckDBPyConnection,
    query: str,
    parameters: Sequence[Any] = (),
) -> list[dict[str, Any]]:
    cursor = connection.execute(query, list(parameters))
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _selected_values(values: Sequence[Any] | Any | None) -> list[Any]:
    if values is None:
        return []
    if isinstance(values, (str, bytes)):
        return [values]
    try:
        return list(values)
    except TypeError:
        return [values]


def _add_in_filter(
    clauses: list[str],
    parameters: list[Any],
    *,
    column: str,
    values: Sequence[Any] | Any | None,
) -> None:
    selected = _selected_values(values)
    if not selected:
        return
    placeholders = ", ".join("?" for _ in selected)
    clauses.append(f"{column} IN ({placeholders})")
    parameters.extend(selected)


def _base_enriched_requests(
    connection: duckdb.DuckDBPyConnection,
    *,
    clauses: Sequence[str] = (),
    parameters: Sequence[Any] = (),
) -> list[dict[str, Any]]:
    where_sql = ""
    if clauses:
        where_sql = "WHERE " + " AND ".join(clauses)

    return _fetch_dicts(
        connection,
        f"""
        SELECT
            r.*,
            owner.display_name AS procurement_owner_name,
            assigner.display_name AS assigned_by_name,
            creator.display_name AS created_by_name,
            updater.display_name AS updated_by_name,
            COALESCE(reference_totals.reference_count, 0)
                AS reference_count,
            COALESCE(
                reference_totals.closure_evidence_reference_count,
                0
            ) AS closure_evidence_reference_count
        FROM procurement_requests r
        LEFT JOIN app_users owner
          ON owner.user_id = r.procurement_owner_user_id
        LEFT JOIN app_users assigner
          ON assigner.user_id = r.assigned_by_user_id
        LEFT JOIN app_users creator
          ON creator.user_id = r.created_by_user_id
        LEFT JOIN app_users updater
          ON updater.user_id = r.updated_by_user_id
        LEFT JOIN (
            SELECT
                request_id,
                COUNT(*) AS reference_count,
                SUM(
                    CASE WHEN is_closure_evidence THEN 1 ELSE 0 END
                ) AS closure_evidence_reference_count
            FROM request_references
            GROUP BY request_id
        ) reference_totals
          ON reference_totals.request_id = r.request_id
        {where_sql}
        """,
        parameters,
    )


def _enrich_attention(
    requests: Sequence[dict[str, Any]],
    *,
    as_of: date | datetime,
) -> list[dict[str, Any]]:
    enriched = []
    for request in requests:
        record = dict(request)
        attention_results = evaluate_request_attention(
            record,
            as_of=as_of,
            procurement_owner_name=record.get(
                "procurement_owner_name"
            ),
            closure_evidence_reference_count=record.get(
                "closure_evidence_reference_count",
                0,
            ),
        )
        record["attention_rule_codes"] = [
            result["rule_code"] for result in attention_results
        ]
        record["attention_reasons"] = [
            result["reason"] for result in attention_results
        ]
        record["attention_count"] = len(attention_results)
        enriched.append(record)
    return enriched


def _sort_requests(
    requests: list[dict[str, Any]],
    *,
    sort_by: str,
    sort_direction: str,
) -> list[dict[str, Any]]:
    if sort_by not in SORT_FIELDS:
        raise QueryValidationError(
            f"sort_by must be one of: {', '.join(sorted(SORT_FIELDS))}."
        )
    direction = str(sort_direction).lower()
    if direction not in ("asc", "desc"):
        raise QueryValidationError(
            "sort_direction must be 'asc' or 'desc'."
        )

    requests.sort(key=lambda item: item["request_number"])
    with_value = [
        item for item in requests if item.get(sort_by) is not None
    ]
    without_value = [
        item for item in requests if item.get(sort_by) is None
    ]
    with_value.sort(
        key=lambda item: item[sort_by],
        reverse=direction == "desc",
    )
    return with_value + without_value


def _validate_pagination(limit: int | None, offset: int) -> None:
    if limit is not None and (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or limit < 0
    ):
        raise QueryValidationError(
            "limit must be a non-negative integer or None."
        )
    if (
        isinstance(offset, bool)
        or not isinstance(offset, int)
        or offset < 0
    ):
        raise QueryValidationError(
            "offset must be a non-negative integer."
        )


def list_enriched_requests(
    connection: duckdb.DuckDBPyConnection,
    *,
    as_of: date | datetime,
    lifecycle_statuses: Sequence[str] | None = None,
    priorities: Sequence[str] | None = None,
    business_units: Sequence[str] | None = None,
    request_categories: Sequence[str] | None = None,
    procurement_owner_user_ids: Sequence[Any] | None = None,
    procurement_routes: Sequence[str] | None = None,
    attention_rule_codes: Sequence[str] | None = None,
    search_text: str | None = None,
    include_completed: bool = True,
    include_cancelled: bool = True,
    sort_by: str = "updated_at",
    sort_direction: str = "desc",
    limit: int | None = None,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Return filtered requests with user names, counts, and derived attention.

    Multiple values inside one filter use OR logic. Separate filters use AND
    logic. Empty value lists and blank search strings are ignored.
    """
    _validate_pagination(limit, offset)
    clauses: list[str] = []
    parameters: list[Any] = []

    _add_in_filter(
        clauses,
        parameters,
        column="r.lifecycle_status",
        values=lifecycle_statuses,
    )
    _add_in_filter(
        clauses,
        parameters,
        column="r.priority",
        values=priorities,
    )
    _add_in_filter(
        clauses,
        parameters,
        column="r.business_unit",
        values=business_units,
    )
    _add_in_filter(
        clauses,
        parameters,
        column="r.request_category",
        values=request_categories,
    )
    selected_owners = _selected_values(procurement_owner_user_ids)
    if selected_owners:
        include_unassigned = None in selected_owners
        assigned_owners = [
            owner_id for owner_id in selected_owners if owner_id is not None
        ]
        owner_conditions: list[str] = []
        if assigned_owners:
            placeholders = ", ".join("?" for _ in assigned_owners)
            owner_conditions.append(
                f"r.procurement_owner_user_id IN ({placeholders})"
            )
            parameters.extend(assigned_owners)
        if include_unassigned:
            owner_conditions.append("r.procurement_owner_user_id IS NULL")
        clauses.append("(" + " OR ".join(owner_conditions) + ")")
    _add_in_filter(
        clauses,
        parameters,
        column="r.procurement_route",
        values=procurement_routes,
    )

    if not include_completed:
        clauses.append("r.lifecycle_status <> ?")
        parameters.append("Completed")
    if not include_cancelled:
        clauses.append("r.lifecycle_status <> ?")
        parameters.append("Cancelled")

    normalized_search = (
        search_text.strip()
        if search_text is not None and search_text.strip()
        else None
    )
    if normalized_search is not None:
        searchable_columns = (
            "r.request_number",
            "r.request_title",
            "r.requestor_name",
            "r.description",
            "r.current_dependency",
            "r.dependency_owner",
            "r.next_action",
            "r.approval_reference",
        )
        column_conditions = " OR ".join(
                f"STRPOS(LOWER(COALESCE({column}, '')), LOWER(?)) > 0"
                for column in searchable_columns
        )
        clauses.append(
            "("
            + column_conditions
            + " OR EXISTS ("
            "SELECT 1 FROM request_references search_reference "
            "WHERE search_reference.request_id = r.request_id "
            "AND STRPOS(LOWER(COALESCE(search_reference.reference_number, '')), "
            "LOWER(?)) > 0"
            "))"
        )
        parameters.extend(
            normalized_search for _ in searchable_columns
        )
        parameters.append(normalized_search)

    records = _enrich_attention(
        _base_enriched_requests(
            connection,
            clauses=clauses,
            parameters=parameters,
        ),
        as_of=as_of,
    )

    selected_attention_codes = set(
        _selected_values(attention_rule_codes)
    )
    if selected_attention_codes:
        records = [
            record
            for record in records
            if selected_attention_codes.intersection(
                record["attention_rule_codes"]
            )
        ]

    records = _sort_requests(
        records,
        sort_by=sort_by,
        sort_direction=sort_direction,
    )
    end = None if limit is None else offset + limit
    return records[offset:end]


def get_enriched_request(
    connection: duckdb.DuckDBPyConnection,
    request_id: Any,
    *,
    as_of: date | datetime,
) -> dict[str, Any] | None:
    """Return request detail, or ``None`` when the request does not exist.

    The return value has four keys: ``request``, ``references``, ``history``,
    and ``attention_results``. Child rows are not duplicated inside the main
    request dictionary.
    """
    requests = _base_enriched_requests(
        connection,
        clauses=("r.request_id = ?",),
        parameters=(request_id,),
    )
    if not requests:
        return None

    request = _enrich_attention(requests, as_of=as_of)[0]
    references = _fetch_dicts(
        connection,
        """
        SELECT *
        FROM request_references
        WHERE request_id = ?
        ORDER BY added_at, reference_id
        """,
        [request["request_id"]],
    )
    history = _fetch_dicts(
        connection,
        """
        SELECT
            h.*,
            actor.display_name AS event_by_name
        FROM request_history h
        LEFT JOIN app_users actor
          ON actor.user_id = h.event_by_user_id
        WHERE h.request_id = ?
        ORDER BY h.event_at, h.history_id
        """,
        [request["request_id"]],
    )
    attention_results = evaluate_request_attention(
        request,
        as_of=as_of,
        procurement_owner_name=request.get("procurement_owner_name"),
        closure_evidence_reference_count=request[
            "closure_evidence_reference_count"
        ],
    )
    return {
        "request": request,
        "references": references,
        "history": history,
        "attention_results": attention_results,
    }


def _validated_summary_filters(
    filters: Mapping[str, Any] | None,
) -> dict[str, Any]:
    selected = dict(filters or {})
    unsupported = set(selected) - DASHBOARD_FILTER_FIELDS
    if unsupported:
        raise QueryValidationError(
            "Unsupported dashboard filters: "
            + ", ".join(sorted(unsupported))
        )
    return selected


def _controlled_counts(
    requests: Sequence[dict[str, Any]],
    *,
    field_name: str,
    controlled_values: Sequence[str],
) -> dict[str, int]:
    observed = Counter(request[field_name] for request in requests)
    return {value: observed[value] for value in controlled_values}


def _active_officers(
    connection: duckdb.DuckDBPyConnection,
) -> list[dict[str, Any]]:
    return _fetch_dicts(
        connection,
        """
        SELECT
            user_id AS owner_user_id,
            display_name AS owner_name
        FROM app_users
        WHERE role = ?
          AND is_active = TRUE
        ORDER BY display_name, user_id
        """,
        ["Procurement Officer"],
    )


def _owner_workload_from_requests(
    requests: Sequence[dict[str, Any]],
    officers: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = [
        {
            "owner_user_id": officer["owner_user_id"],
            "owner_name": officer["owner_name"],
            "open_request_count": 0,
            "assigned_count": 0,
            "in_progress_count": 0,
            "attention_request_count": 0,
            "high_priority_open_count": 0,
            "overdue_follow_up_count": 0,
            "total_open_estimated_value": Decimal("0.00"),
        }
        for officer in officers
    ]
    rows.append(
        {
            "owner_user_id": None,
            "owner_name": "Unassigned",
            "open_request_count": 0,
            "assigned_count": 0,
            "in_progress_count": 0,
            "attention_request_count": 0,
            "high_priority_open_count": 0,
            "overdue_follow_up_count": 0,
            "total_open_estimated_value": Decimal("0.00"),
        }
    )
    rows_by_owner = {
        row["owner_user_id"]: row
        for row in rows
    }

    for request in requests:
        if request["lifecycle_status"] not in OPEN_STATUSES:
            continue
        row = rows_by_owner.get(request["procurement_owner_user_id"])
        if row is None:
            continue
        row["open_request_count"] += 1
        if request["lifecycle_status"] == "Assigned":
            row["assigned_count"] += 1
        if request["lifecycle_status"] == "In Progress":
            row["in_progress_count"] += 1
        if request["attention_count"] > 0:
            row["attention_request_count"] += 1
        if request["priority"] in config.HIGH_PRIORITIES:
            row["high_priority_open_count"] += 1
        if FOLLOW_UP_OVERDUE in request["attention_rule_codes"]:
            row["overdue_follow_up_count"] += 1
        if request["estimated_value"] is not None:
            row["total_open_estimated_value"] += request[
                "estimated_value"
            ]

    return rows


def get_owner_workload(
    connection: duckdb.DuckDBPyConnection,
    *,
    as_of: date | datetime,
    filters: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return open workload for active officers plus an Unassigned row."""
    selected_filters = _validated_summary_filters(filters)
    requests = list_enriched_requests(
        connection,
        as_of=as_of,
        sort_by="request_number",
        sort_direction="asc",
        **selected_filters,
    )
    return _owner_workload_from_requests(
        requests,
        _active_officers(connection),
    )


def get_dashboard_summary(
    connection: duckdb.DuckDBPyConnection,
    *,
    as_of: date | datetime,
    filters: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Aggregate dashboard measures from filtered enriched requests.

    ``requests_requiring_attention`` deduplicates requests, while
    ``total_attention_results`` counts every triggered rule. Unassigned count
    is limited to open requests.
    """
    selected_filters = _validated_summary_filters(filters)
    requests = list_enriched_requests(
        connection,
        as_of=as_of,
        sort_by="request_number",
        sort_direction="asc",
        **selected_filters,
    )
    open_requests = [
        request
        for request in requests
        if request["lifecycle_status"] in OPEN_STATUSES
    ]
    lifecycle_counts = _controlled_counts(
        requests,
        field_name="lifecycle_status",
        controlled_values=config.LIFECYCLE_STATUSES,
    )
    attention_counts = Counter(
        code
        for request in requests
        for code in request["attention_rule_codes"]
    )
    route_counts = Counter(
        request["procurement_route"] or "Not Set"
        for request in requests
    )

    total_estimated_value = sum(
        (
            request["estimated_value"]
            for request in requests
            if request["estimated_value"] is not None
        ),
        Decimal("0.00"),
    )
    open_estimated_value = sum(
        (
            request["estimated_value"]
            for request in open_requests
            if request["estimated_value"] is not None
        ),
        Decimal("0.00"),
    )
    owner_workload = _owner_workload_from_requests(
        requests,
        _active_officers(connection),
    )

    return {
        "total_requests": len(requests),
        "open_requests": len(open_requests),
        "submitted_count": lifecycle_counts["Submitted"],
        "assigned_count": lifecycle_counts["Assigned"],
        "in_progress_count": lifecycle_counts["In Progress"],
        "completed_count": lifecycle_counts["Completed"],
        "cancelled_count": lifecycle_counts["Cancelled"],
        "requests_requiring_attention": sum(
            request["attention_count"] > 0 for request in requests
        ),
        "total_attention_results": sum(attention_counts.values()),
        "unassigned_requests": sum(
            request["procurement_owner_user_id"] is None
            for request in open_requests
        ),
        "overdue_follow_ups": attention_counts[FOLLOW_UP_OVERDUE],
        "missed_target_dates": attention_counts[
            TARGET_COMPLETION_MISSED
        ],
        "approvals_not_confirmed": attention_counts[
            REQUIRED_APPROVAL_NOT_CONFIRMED
        ],
        "high_priority_requests_requiring_attention": sum(
            request["priority"] in config.HIGH_PRIORITIES
            and request["attention_count"] > 0
            for request in open_requests
        ),
        "total_estimated_value": total_estimated_value,
        "total_open_estimated_value": open_estimated_value,
        "counts_by_lifecycle_status": lifecycle_counts,
        "counts_by_priority": _controlled_counts(
            requests,
            field_name="priority",
            controlled_values=config.PRIORITIES,
        ),
        "counts_by_business_unit": _controlled_counts(
            requests,
            field_name="business_unit",
            controlled_values=config.BUSINESS_UNITS,
        ),
        "counts_by_request_category": _controlled_counts(
            requests,
            field_name="request_category",
            controlled_values=config.REQUEST_CATEGORIES,
        ),
        "counts_by_procurement_route": {
            **{
                route: route_counts[route]
                for route in config.PROCUREMENT_ROUTES
            },
            "Not Set": route_counts["Not Set"],
        },
        "owner_workload": owner_workload,
        "attention_counts_by_rule": {
            rule_code: attention_counts[rule_code]
            for rule_code in RULE_CODES
        },
    }


def list_active_procurement_officers(
    connection: duckdb.DuckDBPyConnection,
) -> list[dict[str, Any]]:
    """Return active procurement officers for future owner filters."""
    return _active_officers(connection)


def list_active_app_users(
    connection: duckdb.DuckDBPyConnection,
) -> list[dict[str, Any]]:
    """Return active users for the explicit local demo actor selector."""

    return _fetch_dicts(
        connection,
        """
        SELECT user_id, display_name, role
        FROM app_users
        WHERE is_active = TRUE
        ORDER BY
            CASE role
                WHEN 'Procurement Manager' THEN 1
                WHEN 'Administrator' THEN 2
                ELSE 3
            END,
            display_name,
            user_id
        """,
    )


def get_filter_options(
    connection: duckdb.DuckDBPyConnection,
) -> dict[str, Any]:
    """Return complete controlled options for future filter controls."""
    return {
        "procurement_officers": list_active_procurement_officers(
            connection
        ),
        "lifecycle_statuses": list(config.LIFECYCLE_STATUSES),
        "priorities": list(config.PRIORITIES),
        "business_units": list(config.BUSINESS_UNITS),
        "request_categories": list(config.REQUEST_CATEGORIES),
        "procurement_routes": list(config.PROCUREMENT_ROUTES),
        "attention_rule_codes": list(RULE_CODES),
    }
