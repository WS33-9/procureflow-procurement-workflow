"""Pure attention-rule evaluation for the ProcureFlow prototype.

This module derives attention results from request dictionaries. It does not
query or write the database, persist results, or maintain application state.
Callers must supply ``as_of`` so tests and reports can be deterministic.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from src import config


APPLICATION_ZONE = ZoneInfo(config.APPLICATION_TIMEZONE)

OPEN_WORK_STATUSES = tuple(
    status
    for status in config.LIFECYCLE_STATUSES
    if status not in config.TERMINAL_STATUSES
)
ACTIVE_WORK_STATUSES = ("Assigned", "In Progress")

ASSIGNMENT_OVERDUE = "assignment_overdue"
FOLLOW_UP_OVERDUE = "follow_up_overdue"
TARGET_COMPLETION_MISSED = "target_completion_missed"
REQUIRED_INFORMATION_OUTSTANDING = "required_information_outstanding"
REQUIRED_APPROVAL_NOT_CONFIRMED = "required_approval_not_confirmed"
NO_RECENT_UPDATE = "no_recent_update"
HIGH_PRIORITY_OVERDUE_DEPENDENCY = "high_priority_overdue_dependency"
COMPLETED_MISSING_CLOSURE_EVIDENCE = (
    "completed_missing_closure_evidence"
)

RULE_CODES = (
    ASSIGNMENT_OVERDUE,
    FOLLOW_UP_OVERDUE,
    TARGET_COMPLETION_MISSED,
    REQUIRED_INFORMATION_OUTSTANDING,
    REQUIRED_APPROVAL_NOT_CONFIRMED,
    NO_RECENT_UPDATE,
    HIGH_PRIORITY_OVERDUE_DEPENDENCY,
    COMPLETED_MISSING_CLOSURE_EVIDENCE,
)


class AttentionRuleError(ValueError):
    """Raised when a supplied datetime cannot be evaluated safely."""


def _local_date(value: date | datetime, *, field_name: str) -> date:
    """Return a Toronto-local date, rejecting ambiguous naive datetimes."""
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise AttentionRuleError(
                f"{field_name} must be timezone-aware when supplied as a "
                "datetime"
            )
        return value.astimezone(APPLICATION_ZONE).date()
    if isinstance(value, date):
        return value
    raise AttentionRuleError(
        f"{field_name} must be a date or timezone-aware datetime"
    )


def _optional_local_date(
    value: Any,
    *,
    field_name: str,
) -> date | None:
    if value is None:
        return None
    return _local_date(value, field_name=field_name)


def elapsed_business_days(start_date: date, end_date: date) -> int:
    """Count weekdays after ``start_date`` through and including ``end_date``.

    Statutory holidays are intentionally not excluded in this prototype.
    """
    if end_date <= start_date:
        return 0

    elapsed = 0
    current_date = start_date + timedelta(days=1)
    while current_date <= end_date:
        if current_date.weekday() < 5:
            elapsed += 1
        current_date += timedelta(days=1)
    return elapsed


def _result(
    request: Mapping[str, Any],
    *,
    rule_code: str,
    reason: str,
    procurement_owner_name: str | None,
    relevant_date: date | None = None,
    days_outstanding: int | None = None,
) -> dict[str, Any]:
    return {
        "rule_code": rule_code,
        "reason": reason,
        "request_id": request.get("request_id"),
        "request_number": request.get("request_number"),
        "request_title": request.get("request_title"),
        "lifecycle_status": request.get("lifecycle_status"),
        "procurement_owner_name": procurement_owner_name,
        "dependency_owner": request.get("dependency_owner"),
        "next_action": request.get("next_action"),
        "relevant_date": relevant_date,
        "days_outstanding": days_outstanding,
        "priority": request.get("priority"),
    }


def evaluate_request_attention(
    request: Mapping[str, Any],
    *,
    as_of: date | datetime,
    procurement_owner_name: str | None = None,
    closure_evidence_reference_count: int = 0,
) -> list[dict[str, Any]]:
    """Evaluate all applicable attention rules for one enriched request.

    ``as_of`` may be a date or timezone-aware datetime. Datetimes are
    normalized to ``America/Toronto`` before their date is used. DATE fields
    may be supplied as dates or timezone-aware datetimes. Naive datetimes are
    rejected.
    """
    as_of_date = _local_date(as_of, field_name="as_of")
    lifecycle_status = request.get("lifecycle_status")

    if lifecycle_status == "Cancelled":
        return []

    if lifecycle_status == "Completed":
        if (
            request.get("closure_evidence_required") is True
            and (
                request.get("closure_evidence_confirmed") is not True
                or closure_evidence_reference_count == 0
            )
        ):
            return [
                _result(
                    request,
                    rule_code=COMPLETED_MISSING_CLOSURE_EVIDENCE,
                    reason=(
                        "Completed request is missing confirmation or a "
                        "related closure-evidence reference."
                    ),
                    procurement_owner_name=procurement_owner_name,
                )
            ]
        return []

    results: list[dict[str, Any]] = []
    current_dependency = request.get("current_dependency")
    has_dependency = bool(
        isinstance(current_dependency, str)
        and current_dependency.strip()
    ) or (
        current_dependency is not None
        and not isinstance(current_dependency, str)
    )

    if lifecycle_status == "Submitted":
        submitted_date = _optional_local_date(
            request.get("submitted_at"),
            field_name="submitted_at",
        )
        if submitted_date is not None:
            business_days = elapsed_business_days(
                submitted_date,
                as_of_date,
            )
            threshold = config.ATTENTION_RULE_THRESHOLDS[
                "assignment_overdue_business_days"
            ]
            if business_days > threshold:
                results.append(
                    _result(
                        request,
                        rule_code=ASSIGNMENT_OVERDUE,
                        reason=(
                            "Request remains unassigned beyond the "
                            f"{threshold}-business-day threshold."
                        ),
                        procurement_owner_name=procurement_owner_name,
                        relevant_date=submitted_date,
                        days_outstanding=business_days - threshold,
                    )
                )

    if lifecycle_status in ACTIVE_WORK_STATUSES:
        follow_up_date = _optional_local_date(
            request.get("follow_up_date"),
            field_name="follow_up_date",
        )
        target_date = _optional_local_date(
            request.get("target_completion_date"),
            field_name="target_completion_date",
        )

        if (
            has_dependency
            and follow_up_date is not None
            and follow_up_date < as_of_date
        ):
            days_past_follow_up = (as_of_date - follow_up_date).days
            results.append(
                _result(
                    request,
                    rule_code=FOLLOW_UP_OVERDUE,
                    reason="Current dependency follow-up date is overdue.",
                    procurement_owner_name=procurement_owner_name,
                    relevant_date=follow_up_date,
                    days_outstanding=days_past_follow_up,
                )
            )

        if target_date is not None and target_date < as_of_date:
            results.append(
                _result(
                    request,
                    rule_code=TARGET_COMPLETION_MISSED,
                    reason="Target completion date has been missed.",
                    procurement_owner_name=procurement_owner_name,
                    relevant_date=target_date,
                    days_outstanding=(as_of_date - target_date).days,
                )
            )

        if (
            request.get("dependency_type") == "Required Information"
            and has_dependency
        ):
            results.append(
                _result(
                    request,
                    rule_code=REQUIRED_INFORMATION_OUTSTANDING,
                    reason="Required information remains outstanding.",
                    procurement_owner_name=procurement_owner_name,
                    relevant_date=follow_up_date,
                )
            )

        if (
            request.get("approval_required") is True
            and request.get("approval_status") != "Confirmed"
        ):
            results.append(
                _result(
                    request,
                    rule_code=REQUIRED_APPROVAL_NOT_CONFIRMED,
                    reason="Required approval has not been confirmed.",
                    procurement_owner_name=procurement_owner_name,
                )
            )

        if (
            request.get("priority") in config.HIGH_PRIORITIES
            and has_dependency
            and follow_up_date is not None
            and follow_up_date < as_of_date
        ):
            results.append(
                _result(
                    request,
                    rule_code=HIGH_PRIORITY_OVERDUE_DEPENDENCY,
                    reason=(
                        "High-priority request has an overdue dependency."
                    ),
                    procurement_owner_name=procurement_owner_name,
                    relevant_date=follow_up_date,
                    days_outstanding=(as_of_date - follow_up_date).days,
                )
            )

    if lifecycle_status in OPEN_WORK_STATUSES:
        updated_date = _optional_local_date(
            request.get("updated_at"),
            field_name="updated_at",
        )
        if updated_date is not None:
            elapsed_calendar_days = (as_of_date - updated_date).days
            stale_threshold = config.ATTENTION_RULE_THRESHOLDS[
                "no_recent_update_calendar_days"
            ]
            if elapsed_calendar_days >= stale_threshold:
                results.append(
                    _result(
                        request,
                        rule_code=NO_RECENT_UPDATE,
                        reason=(
                            "Request has not been updated within the "
                            f"{stale_threshold}-calendar-day threshold."
                        ),
                        procurement_owner_name=procurement_owner_name,
                        relevant_date=updated_date,
                        days_outstanding=elapsed_calendar_days,
                    )
                )

    return results


def evaluate_requests_attention(
    requests: Iterable[Mapping[str, Any]],
    *,
    as_of: date | datetime,
) -> list[dict[str, Any]]:
    """Evaluate enriched request dictionaries and combine their results.

    Each item may include ``procurement_owner_name`` and
    ``closure_evidence_reference_count`` fields supplied by a later query
    layer. Those enrichment fields are not required database columns.
    """
    combined_results: list[dict[str, Any]] = []
    for request in requests:
        combined_results.extend(
            evaluate_request_attention(
                request,
                as_of=as_of,
                procurement_owner_name=request.get(
                    "procurement_owner_name"
                ),
                closure_evidence_reference_count=request.get(
                    "closure_evidence_reference_count",
                    0,
                ),
            )
        )
    return combined_results
