"""DuckDB persistence and validation for the ProcureFlow MVP.

This module implements the approved four-table design only:

* app_users
* procurement_requests
* request_references
* request_history
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import duckdb

from src import config


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "database" / "procureflow.duckdb"
APP_TIMEZONE = ZoneInfo(config.APPLICATION_TIMEZONE)


class ValidationError(ValueError):
    """Raised when a requested write violates an MVP business rule."""


def now_local() -> datetime:
    """Return an application timestamp in the configured Toronto timezone."""

    return datetime.now(APP_TIMEZONE)


def connect_database(
    database_path: str | Path = DEFAULT_DATABASE_PATH,
) -> duckdb.DuckDBPyConnection:
    """Open a DuckDB connection configured for the application timezone."""

    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(path))
    connection.execute(f"SET TimeZone = '{config.APPLICATION_TIMEZONE}'")
    return connection


def _sql_values(values: Iterable[str]) -> str:
    return ", ".join("'" + value.replace("'", "''") + "'" for value in values)


def initialize_database(
    database_path: str | Path = DEFAULT_DATABASE_PATH,
    *,
    reset: bool = False,
) -> Path:
    """Create the approved schema and optionally reset only its four tables."""

    path = Path(database_path)
    connection = connect_database(path)
    try:
        if reset:
            for table_name in (
                "request_history",
                "request_references",
                "procurement_requests",
                "app_users",
            ):
                connection.execute(f"DROP TABLE IF EXISTS {table_name}")

        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS app_users (
                user_id UUID PRIMARY KEY,
                display_name VARCHAR NOT NULL,
                email VARCHAR NOT NULL UNIQUE,
                role VARCHAR NOT NULL
                    CHECK (role IN ({_sql_values(config.ROLES)})),
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL
            )
            """
        )

        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS procurement_requests (
                request_id UUID PRIMARY KEY,
                request_number VARCHAR NOT NULL UNIQUE,
                request_title VARCHAR NOT NULL,
                requestor_name VARCHAR NOT NULL,
                business_unit VARCHAR NOT NULL,
                request_category VARCHAR NOT NULL,
                description VARCHAR NOT NULL,
                estimated_value DECIMAL(18, 2)
                    CHECK (estimated_value IS NULL OR estimated_value >= 0),
                priority VARCHAR NOT NULL
                    CHECK (priority IN ({_sql_values(config.PRIORITIES)})),
                required_by_date DATE NOT NULL,
                submitted_at TIMESTAMPTZ NOT NULL,
                lifecycle_status VARCHAR NOT NULL DEFAULT 'Submitted'
                    CHECK (
                        lifecycle_status IN
                        ({_sql_values(config.LIFECYCLE_STATUSES)})
                    ),
                procurement_owner_user_id UUID,
                assignment_date TIMESTAMPTZ,
                assigned_by_user_id UUID,
                procurement_route VARCHAR,
                dependency_type VARCHAR,
                current_dependency VARCHAR,
                dependency_owner VARCHAR,
                next_action VARCHAR,
                follow_up_date DATE,
                target_completion_date DATE,
                officer_note VARCHAR,
                approval_required BOOLEAN NOT NULL DEFAULT FALSE,
                approval_requirement VARCHAR,
                approval_status VARCHAR NOT NULL DEFAULT 'Not Required'
                    CHECK (
                        approval_status IN
                        ({_sql_values(config.APPROVAL_STATUSES)})
                    ),
                approval_source VARCHAR,
                approval_reference VARCHAR,
                approval_confirmation_date TIMESTAMPTZ,
                approval_notes VARCHAR,
                closure_evidence_required BOOLEAN NOT NULL DEFAULT FALSE,
                closure_evidence_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
                closure_note VARCHAR,
                completion_date TIMESTAMPTZ,
                cancellation_date TIMESTAMPTZ,
                cancellation_reason VARCHAR,
                created_at TIMESTAMPTZ NOT NULL,
                created_by_user_id UUID NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL,
                updated_by_user_id UUID NOT NULL,
                FOREIGN KEY (procurement_owner_user_id)
                    REFERENCES app_users(user_id),
                FOREIGN KEY (assigned_by_user_id)
                    REFERENCES app_users(user_id),
                FOREIGN KEY (created_by_user_id)
                    REFERENCES app_users(user_id),
                FOREIGN KEY (updated_by_user_id)
                    REFERENCES app_users(user_id)
            )
            """
        )

        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS request_references (
                reference_id UUID PRIMARY KEY,
                request_id UUID NOT NULL,
                reference_type VARCHAR NOT NULL
                    CHECK (
                        reference_type IN
                        ({_sql_values(config.REFERENCE_TYPES)})
                    ),
                reference_number VARCHAR NOT NULL,
                source_system_or_process VARCHAR NOT NULL,
                reference_link VARCHAR,
                is_closure_evidence BOOLEAN NOT NULL DEFAULT FALSE,
                note VARCHAR,
                added_at TIMESTAMPTZ NOT NULL,
                added_by_user_id UUID NOT NULL,
                FOREIGN KEY (added_by_user_id)
                    REFERENCES app_users(user_id),
                UNIQUE (
                    request_id,
                    reference_type,
                    reference_number,
                    source_system_or_process
                )
            )
            """
        )

        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS request_history (
                history_id UUID PRIMARY KEY,
                request_id UUID NOT NULL,
                event_type VARCHAR NOT NULL
                    CHECK (
                        event_type IN
                        ({_sql_values(config.HISTORY_EVENT_TYPES)})
                    ),
                event_summary VARCHAR NOT NULL,
                field_name VARCHAR,
                previous_value VARCHAR,
                new_value VARCHAR,
                event_at TIMESTAMPTZ NOT NULL,
                event_by_user_id UUID NOT NULL,
                FOREIGN KEY (event_by_user_id)
                    REFERENCES app_users(user_id)
            )
            """
        )
    finally:
        connection.close()

    return path


def _transaction(connection: duckdb.DuckDBPyConnection, operation):
    connection.execute("BEGIN TRANSACTION")
    try:
        result = operation()
        connection.execute("COMMIT")
        return result
    except Exception:
        connection.execute("ROLLBACK")
        raise


def _fetch_one_dict(
    connection: duckdb.DuckDBPyConnection,
    query: str,
    parameters: Iterable[Any] = (),
) -> dict[str, Any] | None:
    cursor = connection.execute(query, list(parameters))
    row = cursor.fetchone()
    if row is None:
        return None
    columns = [item[0] for item in cursor.description]
    return dict(zip(columns, row))


def _require_text(value: Any, field_name: str) -> str:
    if value is None or not str(value).strip():
        raise ValidationError(f"{field_name} is required.")
    return str(value).strip()


def _validate_controlled(
    value: str | None,
    allowed_values: Iterable[str],
    field_name: str,
    *,
    required: bool = True,
) -> None:
    if value is None or not str(value).strip():
        if required:
            raise ValidationError(f"{field_name} is required.")
        return
    if value not in allowed_values:
        raise ValidationError(
            f"{field_name} must be one of: {', '.join(allowed_values)}."
        )


def _as_uuid(value: UUID | str, field_name: str) -> UUID:
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field_name} must be a valid UUID.") from exc


def _get_user(
    connection: duckdb.DuckDBPyConnection,
    user_id: UUID | str,
) -> dict[str, Any]:
    parsed_id = _as_uuid(user_id, "user_id")
    user = _fetch_one_dict(
        connection,
        "SELECT * FROM app_users WHERE user_id = ?",
        [parsed_id],
    )
    if user is None:
        raise ValidationError(f"User {parsed_id} does not exist.")
    return user


def _require_active_user(
    connection: duckdb.DuckDBPyConnection,
    user_id: UUID | str,
    *,
    roles: Iterable[str] | None = None,
) -> dict[str, Any]:
    user = _get_user(connection, user_id)
    if not user["is_active"]:
        raise ValidationError(f"User {user['display_name']} is inactive.")
    if roles is not None and user["role"] not in roles:
        raise ValidationError(
            f"User {user['display_name']} must have one of these roles: "
            f"{', '.join(roles)}."
        )
    return user


def _get_request(
    connection: duckdb.DuckDBPyConnection,
    request_id: UUID | str,
) -> dict[str, Any]:
    parsed_id = _as_uuid(request_id, "request_id")
    request = _fetch_one_dict(
        connection,
        "SELECT * FROM procurement_requests WHERE request_id = ?",
        [parsed_id],
    )
    if request is None:
        raise ValidationError(f"Request {parsed_id} does not exist.")
    return request


def get_request(
    connection: duckdb.DuckDBPyConnection,
    request_id: UUID | str,
) -> dict[str, Any]:
    """Return the current request record."""

    return _get_request(connection, request_id)


def _require_parent_request(
    connection: duckdb.DuckDBPyConnection,
    request_id: UUID | str,
) -> dict[str, Any]:
    """Validate the application-enforced parent side of child writes."""

    return _get_request(connection, request_id)


def _insert_history(
    connection: duckdb.DuckDBPyConnection,
    *,
    request_id: UUID,
    event_type: str,
    event_summary: str,
    event_by_user_id: UUID,
    field_name: str | None = None,
    previous_value: Any = None,
    new_value: Any = None,
) -> UUID:
    parent_request = _require_parent_request(connection, request_id)
    _validate_controlled(
        event_type,
        config.HISTORY_EVENT_TYPES,
        "event_type",
    )
    history_id = uuid4()
    connection.execute(
        """
        INSERT INTO request_history (
            history_id,
            request_id,
            event_type,
            event_summary,
            field_name,
            previous_value,
            new_value,
            event_at,
            event_by_user_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            history_id,
            parent_request["request_id"],
            event_type,
            _require_text(event_summary, "event_summary"),
            field_name,
            None if previous_value is None else str(previous_value),
            None if new_value is None else str(new_value),
            now_local(),
            event_by_user_id,
        ],
    )
    return history_id


def create_user(
    connection: duckdb.DuckDBPyConnection,
    *,
    display_name: str,
    email: str,
    role: str,
    is_active: bool = True,
) -> dict[str, Any]:
    """Create an internal prototype user."""

    display_name = _require_text(display_name, "display_name")
    email = _require_text(email, "email").lower()
    _validate_controlled(role, config.ROLES, "role")
    timestamp = now_local()
    user_id = uuid4()

    def operation():
        connection.execute(
            """
            INSERT INTO app_users (
                user_id,
                display_name,
                email,
                role,
                is_active,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                user_id,
                display_name,
                email,
                role,
                bool(is_active),
                timestamp,
                timestamp,
            ],
        )
        return _get_user(connection, user_id)

    return _transaction(connection, operation)


def _next_request_number(connection: duckdb.DuckDBPyConnection) -> str:
    next_number = connection.execute(
        """
        SELECT COALESCE(
            MAX(TRY_CAST(SUBSTR(request_number, 4) AS INTEGER)),
            0
        ) + 1
        FROM procurement_requests
        WHERE request_number LIKE 'PF-%'
        """
    ).fetchone()[0]
    return f"PF-{int(next_number):04d}"


def _validate_request_state(
    connection: duckdb.DuckDBPyConnection,
    request: dict[str, Any],
) -> None:
    for field_name in (
        "request_title",
        "requestor_name",
        "business_unit",
        "request_category",
        "description",
    ):
        _require_text(request.get(field_name), field_name)

    if request.get("required_by_date") is None:
        raise ValidationError("required_by_date is required.")

    _validate_controlled(
        request.get("business_unit"),
        config.BUSINESS_UNITS,
        "business_unit",
    )
    _validate_controlled(
        request.get("request_category"),
        config.REQUEST_CATEGORIES,
        "request_category",
    )
    _validate_controlled(
        request.get("priority"),
        config.PRIORITIES,
        "priority",
    )
    _validate_controlled(
        request.get("lifecycle_status"),
        config.LIFECYCLE_STATUSES,
        "lifecycle_status",
    )
    _validate_controlled(
        request.get("procurement_route"),
        config.PROCUREMENT_ROUTES,
        "procurement_route",
        required=False,
    )
    _validate_controlled(
        request.get("dependency_type"),
        config.DEPENDENCY_TYPES,
        "dependency_type",
        required=False,
    )
    _validate_controlled(
        request.get("approval_status"),
        config.APPROVAL_STATUSES,
        "approval_status",
    )
    _validate_controlled(
        request.get("cancellation_reason"),
        config.CANCELLATION_REASONS,
        "cancellation_reason",
        required=False,
    )

    estimated_value = request.get("estimated_value")
    if estimated_value is not None and Decimal(str(estimated_value)) < 0:
        raise ValidationError("estimated_value cannot be negative.")

    status = request["lifecycle_status"]
    assignment_fields = (
        request.get("procurement_owner_user_id"),
        request.get("assignment_date"),
        request.get("assigned_by_user_id"),
    )
    if status == "Submitted" and any(value is not None for value in assignment_fields):
        raise ValidationError(
            "Submitted requests cannot have assignment information."
        )
    if status in ("Assigned", "In Progress", "Completed") and any(
        value is None for value in assignment_fields
    ):
        raise ValidationError(
            f"{status} requests require an owner, assignment date, "
            "and assigned-by user."
        )

    dependency = request.get("current_dependency")
    dependency_fields = {
        "dependency_type": request.get("dependency_type"),
        "dependency_owner": request.get("dependency_owner"),
        "next_action": request.get("next_action"),
        "follow_up_date": request.get("follow_up_date"),
    }
    if dependency:
        for field_name, value in dependency_fields.items():
            if value is None or (isinstance(value, str) and not value.strip()):
                raise ValidationError(
                    f"{field_name} is required when current_dependency is set."
                )
    elif any(value is not None for value in dependency_fields.values()):
        raise ValidationError(
            "Dependency details cannot be set without current_dependency."
        )

    approval_required = bool(request.get("approval_required"))
    approval_status = request.get("approval_status")
    if not approval_required and approval_status != "Not Required":
        raise ValidationError(
            "approval_status must be Not Required when approval is not required."
        )
    if approval_required:
        _require_text(
            request.get("approval_requirement"),
            "approval_requirement",
        )
        if approval_status == "Not Required":
            raise ValidationError(
                "Required approvals must use Not Confirmed or Confirmed."
            )
    if approval_status == "Confirmed":
        for field_name in ("approval_source", "approval_reference"):
            _require_text(request.get(field_name), field_name)
        if request.get("approval_confirmation_date") is None:
            raise ValidationError(
                "approval_confirmation_date is required for confirmed approval."
            )

    completion_date = request.get("completion_date")
    cancellation_date = request.get("cancellation_date")
    if status == "Completed":
        _require_text(request.get("procurement_route"), "procurement_route")
        _require_text(request.get("closure_note"), "closure_note")
        if completion_date is None:
            raise ValidationError(
                "completion_date is required for Completed requests."
            )
        if cancellation_date is not None or request.get("cancellation_reason"):
            raise ValidationError(
                "Completed requests cannot contain cancellation information."
            )
        if request.get("closure_evidence_required"):
            if not request.get("closure_evidence_confirmed"):
                raise ValidationError(
                    "Completion is blocked because required closure evidence "
                    "has not been confirmed."
                )
            evidence_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM request_references
                WHERE request_id = ?
                  AND is_closure_evidence = TRUE
                """,
                [request["request_id"]],
            ).fetchone()[0]
            if evidence_count == 0:
                raise ValidationError(
                    "Completion is blocked because no closure-evidence "
                    "reference is recorded."
                )
    elif completion_date is not None:
        raise ValidationError(
            "completion_date can only be set for Completed requests."
        )

    if status == "Cancelled":
        if cancellation_date is None:
            raise ValidationError(
                "cancellation_date is required for Cancelled requests."
            )
        _require_text(
            request.get("cancellation_reason"),
            "cancellation_reason",
        )
        if completion_date is not None:
            raise ValidationError(
                "Cancelled requests cannot contain a completion date."
            )
    elif cancellation_date is not None or request.get("cancellation_reason"):
        raise ValidationError(
            "Cancellation information can only be set for Cancelled requests."
        )


def create_request(
    connection: duckdb.DuckDBPyConnection,
    *,
    created_by_user_id: UUID | str,
    request_title: str,
    requestor_name: str,
    business_unit: str,
    request_category: str,
    description: str,
    priority: str,
    required_by_date: date,
    estimated_value: Decimal | float | int | None = None,
    closure_evidence_required: bool = False,
) -> dict[str, Any]:
    """Create a validated request in Submitted status."""

    creator = _require_active_user(connection, created_by_user_id)
    timestamp = now_local()
    request_id = uuid4()
    approval_status = "Not Required"

    request = {
        "request_id": request_id,
        "request_number": None,
        "request_title": request_title,
        "requestor_name": requestor_name,
        "business_unit": business_unit,
        "request_category": request_category,
        "description": description,
        "estimated_value": estimated_value,
        "priority": priority,
        "required_by_date": required_by_date,
        "submitted_at": timestamp,
        "lifecycle_status": "Submitted",
        "procurement_owner_user_id": None,
        "assignment_date": None,
        "assigned_by_user_id": None,
        "procurement_route": None,
        "dependency_type": None,
        "current_dependency": None,
        "dependency_owner": None,
        "next_action": None,
        "follow_up_date": None,
        "target_completion_date": None,
        "officer_note": None,
        "approval_required": False,
        "approval_requirement": None,
        "approval_status": approval_status,
        "approval_source": None,
        "approval_reference": None,
        "approval_confirmation_date": None,
        "approval_notes": None,
        "closure_evidence_required": bool(closure_evidence_required),
        "closure_evidence_confirmed": False,
        "closure_note": None,
        "completion_date": None,
        "cancellation_date": None,
        "cancellation_reason": None,
        "created_at": timestamp,
        "created_by_user_id": creator["user_id"],
        "updated_at": timestamp,
        "updated_by_user_id": creator["user_id"],
    }
    _validate_request_state(connection, request)

    def operation():
        request["request_number"] = _next_request_number(connection)
        columns = list(request)
        placeholders = ", ".join("?" for _ in columns)
        connection.execute(
            f"""
            INSERT INTO procurement_requests ({", ".join(columns)})
            VALUES ({placeholders})
            """,
            [request[column] for column in columns],
        )
        _insert_history(
            connection,
            request_id=request_id,
            event_type="Request Created",
            event_summary=f"Request {request['request_number']} was submitted.",
            event_by_user_id=creator["user_id"],
            field_name="lifecycle_status",
            new_value="Submitted",
        )
        return _get_request(connection, request_id)

    return _transaction(connection, operation)


UPDATEABLE_REQUEST_FIELDS = {
    "request_title",
    "requestor_name",
    "business_unit",
    "request_category",
    "description",
    "estimated_value",
    "priority",
    "required_by_date",
    "procurement_route",
    "dependency_type",
    "current_dependency",
    "dependency_owner",
    "next_action",
    "follow_up_date",
    "target_completion_date",
    "officer_note",
    "approval_required",
    "approval_requirement",
    "approval_status",
    "approval_source",
    "approval_reference",
    "approval_confirmation_date",
    "approval_notes",
    "closure_evidence_required",
    "closure_evidence_confirmed",
    "closure_note",
}


def _changed_fields(
    current: dict[str, Any],
    changes: dict[str, Any],
) -> dict[str, Any]:
    return {
        field_name: new_value
        for field_name, new_value in changes.items()
        if current.get(field_name) != new_value
    }


def update_request(
    connection: duckdb.DuckDBPyConnection,
    request_id: UUID | str,
    *,
    updated_by_user_id: UUID | str,
    **changes: Any,
) -> dict[str, Any]:
    """Update approved current-state fields and record meaningful history."""

    actor = _require_active_user(connection, updated_by_user_id)
    current = _get_request(connection, request_id)
    if current["lifecycle_status"] in config.TERMINAL_STATUSES:
        raise ValidationError(
            f"{current['lifecycle_status']} requests are terminal and read-only."
        )
    unknown_fields = set(changes) - UPDATEABLE_REQUEST_FIELDS
    if unknown_fields:
        raise ValidationError(
            "Unsupported request fields: " + ", ".join(sorted(unknown_fields))
        )
    changes = _changed_fields(current, changes)
    if not changes:
        return current

    candidate = dict(current)
    candidate.update(changes)
    candidate["updated_at"] = now_local()
    candidate["updated_by_user_id"] = actor["user_id"]
    _validate_request_state(connection, candidate)

    history_groups = [
        (
            {"procurement_route"},
            "Route Changed",
            "Procurement route was updated.",
        ),
        (
            {
                "dependency_type",
                "current_dependency",
                "dependency_owner",
                "next_action",
                "follow_up_date",
                "officer_note",
            },
            "Dependency Updated",
            "Current dependency or next action was updated.",
        ),
        (
            {"target_completion_date"},
            "Target Date Updated",
            "Target completion date was updated.",
        ),
        (
            {
                "approval_required",
                "approval_requirement",
                "approval_status",
                "approval_source",
                "approval_reference",
                "approval_confirmation_date",
                "approval_notes",
            },
            "Approval Updated",
            "Current approval information was updated.",
        ),
        (
            {
                "closure_evidence_required",
                "closure_evidence_confirmed",
                "closure_note",
            },
            "Closure Evidence Updated",
            "Closure evidence status was updated.",
        ),
    ]

    def operation():
        assignments = ", ".join(f"{field_name} = ?" for field_name in changes)
        parameters = [changes[field_name] for field_name in changes]
        parameters.extend(
            [
                candidate["updated_at"],
                candidate["updated_by_user_id"],
                candidate["request_id"],
            ]
        )
        connection.execute(
            f"""
            UPDATE procurement_requests
            SET {assignments},
                updated_at = ?,
                updated_by_user_id = ?
            WHERE request_id = ?
            """,
            parameters,
        )

        logged_fields: set[str] = set()
        for fields, event_type, summary in history_groups:
            affected = sorted(fields.intersection(changes))
            if not affected:
                continue
            logged_fields.update(affected)
            _insert_history(
                connection,
                request_id=candidate["request_id"],
                event_type=event_type,
                event_summary=summary,
                event_by_user_id=actor["user_id"],
                field_name=", ".join(affected),
                previous_value={
                    field: current.get(field) for field in affected
                },
                new_value={field: changes[field] for field in affected},
            )

        return _get_request(connection, candidate["request_id"])

    return _transaction(connection, operation)


def assign_request(
    connection: duckdb.DuckDBPyConnection,
    request_id: UUID | str,
    *,
    procurement_owner_user_id: UUID | str,
    assigned_by_user_id: UUID | str,
) -> dict[str, Any]:
    """Assign or reassign one active procurement officer."""

    actor = _require_active_user(
        connection,
        assigned_by_user_id,
        roles=("Procurement Manager", "Administrator"),
    )
    owner = _require_active_user(
        connection,
        procurement_owner_user_id,
        roles=("Procurement Officer",),
    )
    current = _get_request(connection, request_id)
    if current["lifecycle_status"] in config.TERMINAL_STATUSES:
        raise ValidationError(
            f"{current['lifecycle_status']} requests are terminal."
        )

    previous_owner = current.get("procurement_owner_user_id")
    timestamp = now_local()
    candidate = dict(current)
    candidate.update(
        {
            "procurement_owner_user_id": owner["user_id"],
            "assignment_date": timestamp,
            "assigned_by_user_id": actor["user_id"],
            "lifecycle_status": (
                "Assigned"
                if current["lifecycle_status"] == "Submitted"
                else current["lifecycle_status"]
            ),
            "updated_at": timestamp,
            "updated_by_user_id": actor["user_id"],
        }
    )
    _validate_request_state(connection, candidate)

    def operation():
        connection.execute(
            """
            UPDATE procurement_requests
            SET procurement_owner_user_id = ?,
                assignment_date = ?,
                assigned_by_user_id = ?,
                lifecycle_status = ?,
                updated_at = ?,
                updated_by_user_id = ?
            WHERE request_id = ?
            """,
            [
                candidate["procurement_owner_user_id"],
                candidate["assignment_date"],
                candidate["assigned_by_user_id"],
                candidate["lifecycle_status"],
                candidate["updated_at"],
                candidate["updated_by_user_id"],
                candidate["request_id"],
            ],
        )
        event_type = "Assigned" if previous_owner is None else "Reassigned"
        _insert_history(
            connection,
            request_id=candidate["request_id"],
            event_type=event_type,
            event_summary=(
                f"Request was {event_type.lower()} to {owner['display_name']}."
            ),
            event_by_user_id=actor["user_id"],
            field_name="procurement_owner_user_id",
            previous_value=previous_owner,
            new_value=owner["user_id"],
        )
        return _get_request(connection, candidate["request_id"])

    return _transaction(connection, operation)


def transition_request_status(
    connection: duckdb.DuckDBPyConnection,
    request_id: UUID | str,
    *,
    new_status: str,
    updated_by_user_id: UUID | str,
    cancellation_reason: str | None = None,
) -> dict[str, Any]:
    """Apply a valid lifecycle transition and record it in history."""

    actor = _require_active_user(connection, updated_by_user_id)
    _validate_controlled(
        new_status,
        config.LIFECYCLE_STATUSES,
        "new_status",
    )
    current = _get_request(connection, request_id)
    current_status = current["lifecycle_status"]
    if current_status in config.TERMINAL_STATUSES:
        raise ValidationError(f"{current_status} requests are terminal.")
    if new_status not in config.ALLOWED_STATUS_TRANSITIONS[current_status]:
        raise ValidationError(
            f"Cannot transition from {current_status} to {new_status}."
        )

    timestamp = now_local()
    candidate = dict(current)
    candidate["lifecycle_status"] = new_status
    candidate["updated_at"] = timestamp
    candidate["updated_by_user_id"] = actor["user_id"]
    if new_status == "Completed":
        candidate["completion_date"] = timestamp
    elif new_status == "Cancelled":
        _validate_controlled(
            cancellation_reason,
            config.CANCELLATION_REASONS,
            "cancellation_reason",
        )
        candidate["cancellation_date"] = timestamp
        candidate["cancellation_reason"] = cancellation_reason

    _validate_request_state(connection, candidate)

    def operation():
        connection.execute(
            """
            UPDATE procurement_requests
            SET lifecycle_status = ?,
                completion_date = ?,
                cancellation_date = ?,
                cancellation_reason = ?,
                updated_at = ?,
                updated_by_user_id = ?
            WHERE request_id = ?
            """,
            [
                candidate["lifecycle_status"],
                candidate["completion_date"],
                candidate["cancellation_date"],
                candidate["cancellation_reason"],
                candidate["updated_at"],
                candidate["updated_by_user_id"],
                candidate["request_id"],
            ],
        )
        event_type = (
            new_status if new_status in config.TERMINAL_STATUSES
            else "Status Changed"
        )
        _insert_history(
            connection,
            request_id=candidate["request_id"],
            event_type=event_type,
            event_summary=(
                f"Lifecycle status changed from {current_status} "
                f"to {new_status}."
            ),
            event_by_user_id=actor["user_id"],
            field_name="lifecycle_status",
            previous_value=current_status,
            new_value=new_status,
        )
        return _get_request(connection, candidate["request_id"])

    return _transaction(connection, operation)


def _validate_link(link: str | None) -> None:
    if link is None or not link.strip():
        return
    parsed = urlparse(link)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValidationError(
            "reference_link must be an absolute HTTP or HTTPS URL."
        )


def add_request_reference(
    connection: duckdb.DuckDBPyConnection,
    request_id: UUID | str,
    *,
    reference_type: str,
    reference_number: str,
    source_system_or_process: str,
    added_by_user_id: UUID | str,
    reference_link: str | None = None,
    is_closure_evidence: bool = False,
    note: str | None = None,
) -> dict[str, Any]:
    """Attach a manually entered external record reference to a request."""

    actor = _require_active_user(connection, added_by_user_id)
    request = _require_parent_request(connection, request_id)
    if request["lifecycle_status"] in config.TERMINAL_STATUSES:
        raise ValidationError(
            f"{request['lifecycle_status']} requests are terminal and read-only."
        )
    _validate_controlled(
        reference_type,
        config.REFERENCE_TYPES,
        "reference_type",
    )
    reference_number = _require_text(
        reference_number,
        "reference_number",
    )
    source_system_or_process = _require_text(
        source_system_or_process,
        "source_system_or_process",
    )
    _validate_link(reference_link)
    reference_id = uuid4()
    timestamp = now_local()

    def operation():
        connection.execute(
            """
            INSERT INTO request_references (
                reference_id,
                request_id,
                reference_type,
                reference_number,
                source_system_or_process,
                reference_link,
                is_closure_evidence,
                note,
                added_at,
                added_by_user_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                reference_id,
                request["request_id"],
                reference_type,
                reference_number,
                source_system_or_process,
                reference_link,
                bool(is_closure_evidence),
                note,
                timestamp,
                actor["user_id"],
            ],
        )
        connection.execute(
            """
            UPDATE procurement_requests
            SET updated_at = ?, updated_by_user_id = ?
            WHERE request_id = ?
            """,
            [timestamp, actor["user_id"], request["request_id"]],
        )
        _insert_history(
            connection,
            request_id=request["request_id"],
            event_type="Reference Added",
            event_summary=(
                f"{reference_type} {reference_number} was added."
            ),
            event_by_user_id=actor["user_id"],
            field_name="request_references",
            new_value=reference_number,
        )
        return _fetch_one_dict(
            connection,
            "SELECT * FROM request_references WHERE reference_id = ?",
            [reference_id],
        )

    return _transaction(connection, operation)


def list_request_history(
    connection: duckdb.DuckDBPyConnection,
    request_id: UUID | str,
) -> list[dict[str, Any]]:
    """Return simplified history in chronological order."""

    request = _get_request(connection, request_id)
    cursor = connection.execute(
        """
        SELECT *
        FROM request_history
        WHERE request_id = ?
        ORDER BY event_at, history_id
        """,
        [request["request_id"]],
    )
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def list_table_names(
    connection: duckdb.DuckDBPyConnection,
) -> list[str]:
    """Return user table names for verification."""

    return [
        row[0]
        for row in connection.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'main'
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """
        ).fetchall()
    ]


if __name__ == "__main__":
    initialized_path = initialize_database()
    print(f"Initialized ProcureFlow database: {initialized_path}")
