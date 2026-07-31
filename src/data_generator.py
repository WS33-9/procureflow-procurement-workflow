"""Deterministic fictional demo-data generation for ProcureFlow.

Nothing is generated when this module is imported. Call
``generate_demo_data`` or invoke the module as a command with an explicit
database path and reference date.
"""

from __future__ import annotations

import argparse
import random
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator
from uuid import UUID
from zoneinfo import ZoneInfo

from src import config
from src import database as database_module
from src.database import (
    ValidationError,
    add_request_reference,
    assign_request,
    connect_database,
    create_request,
    create_user,
    initialize_database,
    transition_request_status,
    update_request,
)


DEFAULT_SEED = 20260730
APP_TIMEZONE = ZoneInfo(config.APPLICATION_TIMEZONE)
LEGACY_ISSUE_TITLE = "Legacy records-storage service completion"

USER_DEFINITIONS = (
    (
        "Alex Morgan",
        "alex.morgan@northbridge.example",
        "Procurement Officer",
    ),
    (
        "Casey Reed",
        "casey.reed@northbridge.example",
        "Procurement Officer",
    ),
    (
        "Taylor Brooks",
        "taylor.brooks@northbridge.example",
        "Procurement Officer",
    ),
    (
        "Morgan Lee",
        "morgan.lee@northbridge.example",
        "Procurement Manager",
    ),
    (
        "Elena Brooks",
        "elena.brooks@northbridge.example",
        "Procurement Manager",
    ),
    (
        "Jordan Singh",
        "jordan.singh@northbridge.example",
        "Administrator",
    ),
)

REQUEST_EXAMPLES = (
    ("Financial reporting software renewal", "Technology"),
    ("Warehouse scanner replacement", "Equipment"),
    ("Office relocation services", "Facilities"),
    ("Recruitment platform subscription", "Technology"),
    ("Network equipment refresh", "Equipment"),
    ("Employee training facilitation", "Professional Services"),
    ("Facilities maintenance support", "Facilities"),
    ("Courier services agreement", "Logistics"),
    ("Annual report design support", "Marketing"),
    (
        "Records digitization services",
        "Office and Administrative Services",
    ),
    ("Cybersecurity assessment", "Professional Services"),
    ("Meeting-room equipment purchase", "Equipment"),
    ("Regional freight coordination", "Logistics"),
    ("Benefits advisory services", "Professional Services"),
    ("Cloud backup subscription", "Technology"),
    ("Building access-card supplies", "Facilities"),
    ("Digital campaign production", "Marketing"),
    (
        "Office stationery replenishment",
        "Office and Administrative Services",
    ),
    ("Laptop docking-station purchase", "Equipment"),
    ("Contract management software renewal", "Technology"),
    ("Distribution process review", "Professional Services"),
    ("Branch signage production", "Marketing"),
    ("Loading-bay repair services", "Facilities"),
    ("Priority document delivery", "Logistics"),
    (
        "Reception support services",
        "Office and Administrative Services",
    ),
    ("Data integration consulting", "Professional Services"),
    ("Mobile device replacement", "Equipment"),
    ("Website accessibility review", "Technology"),
    ("Trade-show booth services", "Marketing"),
    ("Inventory transfer services", "Logistics"),
    ("Roof inspection support", "Facilities"),
    (
        "Secure shredding services",
        "Office and Administrative Services",
    ),
    ("Network monitoring subscription", "Technology"),
    ("Leadership workshop facilitation", "Professional Services"),
    ("Ergonomic chair replacement", "Equipment"),
    ("Community outreach materials", "Marketing"),
    (LEGACY_ISSUE_TITLE, "Office and Administrative Services"),
    ("Financial audit support", "Professional Services"),
    ("Emergency generator maintenance", "Facilities"),
    ("Procurement analytics subscription", "Technology"),
    ("Warehouse shelving purchase", "Equipment"),
    ("Customer survey campaign", "Marketing"),
    ("Interoffice shipping agreement", "Logistics"),
    (
        "Document indexing support",
        "Office and Administrative Services",
    ),
    ("Cancelled software evaluation", "Technology"),
    ("Cancelled consulting engagement", "Professional Services"),
    ("Cancelled equipment order", "Equipment"),
    ("Cancelled office-supply request", "Office and Administrative Services"),
)

REQUESTOR_NAMES = (
    "Taylor Morgan",
    "Riley Bennett",
    "Cameron Lewis",
    "Sydney Clark",
    "Jamie Rivera",
    "Quinn Foster",
    "Parker Adams",
    "Casey Nguyen",
    "Drew Martin",
    "Alexis Turner",
    "Reese Campbell",
    "Rowan Scott",
)

DEPENDENCY_DETAILS = {
    "Required Information": (
        "Business specifications remain incomplete.",
        "Business requestor",
        "Confirm the outstanding specifications.",
    ),
    "Approval": (
        "Documented approval confirmation is pending.",
        "Business sponsor",
        "Follow up on the approval record.",
    ),
    "Supplier Response": (
        "A response from the selected supplier is pending.",
        "Selected supplier",
        "Request a status update from the supplier.",
    ),
    "Signature": (
        "The agreement is awaiting an authorized signature.",
        "Signing authority",
        "Confirm when the signed agreement is available.",
    ),
    "Internal Review": (
        "Internal procurement review is still underway.",
        "Procurement review team",
        "Complete the outstanding internal review.",
    ),
    "System or Financial Action": (
        "The related financial-system action is pending.",
        "Finance operations",
        "Confirm completion of the financial-system action.",
    ),
    "Other": (
        "A supporting operational action remains unresolved.",
        "Business operations team",
        "Confirm the outstanding operational action.",
    ),
}

# Keeps 28 active requests at 10/9/9 while distributing attention-bearing
# work at 7/6/6. The small swaps preserve the deterministic rule scenarios.
ACTIVE_OWNER_INDEXES = (
    0, 1, 2, 0, 1, 2, 0, 1, 2, 0, 2, 1, 0, 1,
    2, 0, 2, 1, 0, 1, 2, 0, 2, 1, 0, 1, 2, 0,
)

ATTENTION_QUEUE_DETAIL_OVERRIDES = {
    0: (
        "Final content and print specifications are still outstanding.",
        "Confirm the final report specifications with Corporate Services.",
    ),
    2: (
        "The supplier has not confirmed the assessment start date.",
        "Follow up with the supplier and update the expected start date.",
    ),
    3: (
        "The equipment agreement is awaiting an authorized signature.",
        "Confirm when the signed equipment agreement is available.",
    ),
    7: (
        "Final card quantities and delivery locations are not confirmed.",
        "Confirm quantities and delivery locations with the requestor.",
    ),
    15: (
        "Written approval for the priority service has not been linked.",
        "Ask the business sponsor to provide the approval reference.",
    ),
    18: (
        "The replacement-device configuration is still under internal review.",
        "Complete the device configuration review.",
    ),
    27: (
        "Final distribution quantities remain unresolved.",
        "Confirm distribution quantities with the requesting team.",
    ),
}

ROUTE_DESCRIPTION_NOTES = {
    "Low-Value Purchase": (
        "The expected value supports a straightforward low-value purchase."
    ),
    "Competitive Procurement": (
        "The requirement is being prepared for a competitive sourcing process."
    ),
    "Non-Competitive Procurement": (
        "Continuity and compatibility requirements support documenting a "
        "non-competitive rationale."
    ),
    "Existing Contract or Agreement": (
        "The request is expected to use an existing contractual arrangement."
    ),
    "Contract Amendment": (
        "The requirement changes the scope or value of an existing agreement."
    ),
    "Other": (
        "The procurement team is documenting the most appropriate route."
    ),
}

REFERENCE_CONFIGURATION = {
    "Approval Record": ("APR", "Financial approval process"),
    "Purchase Requisition": ("PR", "Purchase requisition process"),
    "Purchase Order": ("PO", "ERP"),
    "Solicitation or RFP": ("RFP", "Competitive sourcing process"),
    "Contract": ("CTR", "Contract repository"),
    "Amendment": ("AMD", "Contract repository"),
    "Call-Up": ("CU", "Contract repository"),
    "Release": ("REL", "ERP"),
    "Task Authorization": ("TA", "Contract repository"),
    "Official Document Reference": ("ODR", "Email approval record"),
    "Other Procurement Record": ("OPR", "Procurement working process"),
}


class DemoDataError(ValueError):
    """Raised when deterministic demo generation cannot proceed safely."""


class _ScheduledClock:
    def __init__(self, initial_value: datetime):
        self._current = initial_value

    def set(self, value: datetime) -> None:
        if value.tzinfo is None or value.utcoffset() is None:
            raise DemoDataError("Scheduled timestamps must be timezone-aware.")
        self._current = value.astimezone(APP_TIMEZONE)

    def __call__(self) -> datetime:
        return self._current


def _local_datetime(
    local_date: date,
    hour: int,
    minute: int = 0,
) -> datetime:
    return datetime.combine(
        local_date,
        time(hour, minute),
        tzinfo=APP_TIMEZONE,
    )


@contextmanager
def _deterministic_database_runtime(
    *,
    seed: int,
    initial_timestamp: datetime,
) -> Iterator[_ScheduledClock]:
    """Temporarily supply deterministic UUIDs and timestamps to shared writes."""
    clock = _ScheduledClock(initial_timestamp)
    uuid_random = random.Random(seed + 10_000)

    def deterministic_uuid4() -> UUID:
        return UUID(int=uuid_random.getrandbits(128), version=4)

    original_clock = database_module.now_local
    original_uuid4 = database_module.uuid4
    database_module.now_local = clock
    database_module.uuid4 = deterministic_uuid4
    try:
        yield clock
    finally:
        database_module.now_local = original_clock
        database_module.uuid4 = original_uuid4


def _require_empty_database(connection) -> None:
    populated = []
    for table_name in (
        "app_users",
        "procurement_requests",
        "request_references",
        "request_history",
    ):
        count = connection.execute(
            f"SELECT COUNT(*) FROM {table_name}"
        ).fetchone()[0]
        if count:
            populated.append(f"{table_name} ({count})")
    if populated:
        raise DemoDataError(
            "Demo generation requires an empty database. Use reset=True. "
            "Populated tables: "
            + ", ".join(populated)
        )


def _description_for(
    title: str,
    category: str,
    route: str | None,
) -> str:
    description = (
        f"Northbridge requires {title.lower()} to support a planned "
        f"{category.lower()} requirement."
    )
    if route:
        description += " " + ROUTE_DESCRIPTION_NOTES[route]
    return description


def _estimated_value(
    route: str | None,
    *,
    index: int,
    randomizer: random.Random,
) -> Decimal | None:
    if index % 6 == 0:
        return None
    bases = {
        None: 12_000,
        "Low-Value Purchase": 4_500,
        "Competitive Procurement": 125_000,
        "Non-Competitive Procurement": 38_000,
        "Existing Contract or Agreement": 54_000,
        "Contract Amendment": 27_000,
        "Other": 16_000,
    }
    amount = bases[route] + randomizer.randrange(5, 85) * 250
    return Decimal(amount).quantize(Decimal("0.01"))


def _approval_changes(
    *,
    status: str,
    confirmation_timestamp: datetime,
    index: int,
) -> dict[str, Any]:
    if status == "Not Required":
        return {}
    changes: dict[str, Any] = {
        "approval_required": True,
        "approval_requirement": "Business sponsor approval confirmation",
        "approval_status": status,
        "approval_notes": (
            "ProcureFlow records confirmation from the source process; "
            "it does not make the approval decision."
        ),
    }
    if status == "Confirmed":
        changes.update(
            {
                "approval_source": "Financial approval process",
                "approval_reference": f"APR-2026-{7000 + index:04d}",
                "approval_confirmation_date": confirmation_timestamp,
            }
        )
    return changes


def _reference_values(reference_type: str, index: int) -> dict[str, str]:
    prefix, source = REFERENCE_CONFIGURATION[reference_type]
    number = f"{prefix}-2026-{5000 + index:04d}"
    return {
        "reference_number": number,
        "source_system_or_process": source,
        "reference_link": (
            "https://records.northbridge.example/"
            f"{prefix.lower()}/{number.lower()}"
        ),
    }


def _add_reference(
    connection,
    *,
    request: dict[str, Any],
    reference_type: str,
    reference_index: int,
    actor_id: UUID,
    is_closure_evidence: bool = False,
) -> dict[str, Any]:
    values = _reference_values(reference_type, reference_index)
    return add_request_reference(
        connection,
        request["request_id"],
        reference_type=reference_type,
        added_by_user_id=actor_id,
        is_closure_evidence=is_closure_evidence,
        note=(
            "External record pointer only; the official record remains in "
            "the identified source process."
        ),
        **values,
    )


def _active_final_date(reference_date: date, active_index: int) -> date:
    if active_index == 0:
        return reference_date - timedelta(days=8)
    if active_index == 1:
        return reference_date - timedelta(days=7)
    if active_index == 2:
        return reference_date - timedelta(days=6)
    return reference_date - timedelta(days=1 + (active_index % 3))


def _follow_up_date(reference_date: date, active_index: int) -> date:
    if active_index in (1, 6):
        return reference_date
    if active_index in (2, 3, 5):
        return reference_date - timedelta(days=2 + active_index % 2)
    if active_index % 3 == 0:
        return reference_date - timedelta(days=2)
    return reference_date + timedelta(days=2 + active_index % 4)


def _target_date(
    reference_date: date,
    active_index: int,
) -> date | None:
    if active_index == 1:
        return reference_date
    if active_index in (0, 3, 8, 12):
        return reference_date - timedelta(days=2 + active_index % 3)
    if active_index % 4 == 2:
        return reference_date + timedelta(days=4)
    return None


def _create_submitted_requests(
    connection,
    *,
    clock: _ScheduledClock,
    reference_date: date,
    randomizer: random.Random,
    managers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    submitted_offsets = (10, 7, 1, 0, 3, 2, 4, 1)
    requests = []
    for index in range(8):
        title, category = REQUEST_EXAMPLES[index]
        submitted_date = reference_date - timedelta(
            days=submitted_offsets[index]
        )
        clock.set(_local_datetime(submitted_date, 9, 15 + index))
        route = None
        request = create_request(
            connection,
            created_by_user_id=managers[index % len(managers)]["user_id"],
            request_title=title,
            requestor_name=REQUESTOR_NAMES[
                randomizer.randrange(len(REQUESTOR_NAMES))
            ],
            business_unit=config.BUSINESS_UNITS[
                index % len(config.BUSINESS_UNITS)
            ],
            request_category=category,
            description=_description_for(title, category, route),
            priority=config.PRIORITIES[index % len(config.PRIORITIES)],
            required_by_date=reference_date
            + timedelta(days=(index - 3) * 5),
            estimated_value=_estimated_value(
                route,
                index=index,
                randomizer=randomizer,
            ),
            closure_evidence_required=index in (4, 7),
        )
        requests.append(request)
    return requests


def _create_active_requests(
    connection,
    *,
    clock: _ScheduledClock,
    reference_date: date,
    randomizer: random.Random,
    officers: list[dict[str, Any]],
    managers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    requests = []
    for active_index in range(28):
        index = active_index + 8
        title, category = REQUEST_EXAMPLES[index]
        final_status = "Assigned" if active_index < 8 else "In Progress"
        final_date = _active_final_date(reference_date, active_index)
        submitted_date = final_date - timedelta(
            days=2 if final_status == "Assigned" else 5
        )
        assignment_date = submitted_date + timedelta(days=1)
        route = config.PROCUREMENT_ROUTES[
            active_index % len(config.PROCUREMENT_ROUTES)
        ]
        priority = config.PRIORITIES[index % len(config.PRIORITIES)]
        creator = managers[index % len(managers)]
        owner = officers[ACTIVE_OWNER_INDEXES[active_index]]

        clock.set(_local_datetime(submitted_date, 9, 5))
        request = create_request(
            connection,
            created_by_user_id=creator["user_id"],
            request_title=title,
            requestor_name=REQUESTOR_NAMES[
                randomizer.randrange(len(REQUESTOR_NAMES))
            ],
            business_unit=config.BUSINESS_UNITS[
                index % len(config.BUSINESS_UNITS)
            ],
            request_category=category,
            description=_description_for(title, category, route),
            priority=priority,
            required_by_date=reference_date
            + timedelta(days=((index % 11) - 5) * 4),
            estimated_value=_estimated_value(
                route,
                index=index,
                randomizer=randomizer,
            ),
            closure_evidence_required=index % 5 == 0,
        )

        clock.set(_local_datetime(assignment_date, 10, 10))
        request = assign_request(
            connection,
            request["request_id"],
            procurement_owner_user_id=owner["user_id"],
            assigned_by_user_id=creator["user_id"],
        )

        if final_status == "In Progress":
            clock.set(
                _local_datetime(
                    assignment_date + timedelta(days=1),
                    11,
                    20,
                )
            )
            request = transition_request_status(
                connection,
                request["request_id"],
                new_status="In Progress",
                updated_by_user_id=owner["user_id"],
            )

        dependency_changes: dict[str, Any] = {}
        if active_index % 5 != 4:
            dependency_type = config.DEPENDENCY_TYPES[
                active_index % len(config.DEPENDENCY_TYPES)
            ]
            dependency, dependency_owner, next_action = DEPENDENCY_DETAILS[
                dependency_type
            ]
            if active_index in ATTENTION_QUEUE_DETAIL_OVERRIDES:
                dependency, next_action = (
                    ATTENTION_QUEUE_DETAIL_OVERRIDES[active_index]
                )
            dependency_changes = {
                "dependency_type": dependency_type,
                "current_dependency": dependency,
                "dependency_owner": dependency_owner,
                "next_action": next_action,
                "follow_up_date": _follow_up_date(
                    reference_date,
                    active_index,
                ),
            }

        approval_status = config.APPROVAL_STATUSES[active_index % 3]
        final_timestamp = _local_datetime(final_date, 15, active_index % 40)
        state_changes = {
            "procurement_route": route,
            "target_completion_date": _target_date(
                reference_date,
                active_index,
            ),
            "officer_note": (
                "The owner has documented the current route, dependency, "
                "and next operational step."
            ),
            **dependency_changes,
            **_approval_changes(
                status=approval_status,
                confirmation_timestamp=final_timestamp
                - timedelta(hours=2),
                index=index,
            ),
        }
        clock.set(final_timestamp)
        request = update_request(
            connection,
            request["request_id"],
            updated_by_user_id=owner["user_id"],
            **state_changes,
        )

        if active_index % 6 == 0:
            reference_type = config.REFERENCE_TYPES[
                (active_index + 1) % len(config.REFERENCE_TYPES)
            ]
            clock.set(final_timestamp + timedelta(minutes=10))
            _add_reference(
                connection,
                request=request,
                reference_type=reference_type,
                reference_index=index,
                actor_id=owner["user_id"],
            )
            if active_index == 0:
                clock.set(final_timestamp + timedelta(minutes=20))
                _add_reference(
                    connection,
                    request=request,
                    reference_type="Purchase Requisition",
                    reference_index=100 + index,
                    actor_id=owner["user_id"],
                )

        requests.append(request)
    return requests


def _simulate_imported_completed_closure_issue(
    connection,
    *,
    request_id: UUID,
) -> None:
    # This one-off mutation simulates an imported or legacy data-quality issue.
    # It is intentionally private and does not weaken normal completion writes.
    connection.execute(
        """
        UPDATE procurement_requests
        SET closure_evidence_confirmed = FALSE
        WHERE request_id = ?
          AND lifecycle_status = 'Completed'
          AND closure_evidence_required = TRUE
        """,
        [request_id],
    )


def _create_completed_requests(
    connection,
    *,
    clock: _ScheduledClock,
    reference_date: date,
    randomizer: random.Random,
    officers: list[dict[str, Any]],
    managers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    requests = []
    closure_required_indices = {0, 1, 3, 5}
    for completed_index in range(8):
        index = completed_index + 36
        title, category = REQUEST_EXAMPLES[index]
        completion_date = reference_date - timedelta(
            days=12 - completed_index
        )
        submitted_date = completion_date - timedelta(days=7)
        assignment_date = completion_date - timedelta(days=5)
        route = config.PROCUREMENT_ROUTES[
            completed_index % len(config.PROCUREMENT_ROUTES)
        ]
        creator = managers[index % len(managers)]
        owner = officers[completed_index % len(officers)]
        closure_required = completed_index in closure_required_indices

        clock.set(_local_datetime(submitted_date, 8, 45))
        request = create_request(
            connection,
            created_by_user_id=creator["user_id"],
            request_title=title,
            requestor_name=REQUESTOR_NAMES[
                randomizer.randrange(len(REQUESTOR_NAMES))
            ],
            business_unit=config.BUSINESS_UNITS[
                index % len(config.BUSINESS_UNITS)
            ],
            request_category=category,
            description=_description_for(title, category, route),
            priority=config.PRIORITIES[index % len(config.PRIORITIES)],
            required_by_date=completion_date + timedelta(days=2),
            estimated_value=_estimated_value(
                route,
                index=index,
                randomizer=randomizer,
            ),
            closure_evidence_required=closure_required,
        )

        clock.set(_local_datetime(assignment_date, 9, 30))
        request = assign_request(
            connection,
            request["request_id"],
            procurement_owner_user_id=owner["user_id"],
            assigned_by_user_id=creator["user_id"],
        )
        clock.set(
            _local_datetime(
                assignment_date + timedelta(days=1),
                10,
                15,
            )
        )
        request = transition_request_status(
            connection,
            request["request_id"],
            new_status="In Progress",
            updated_by_user_id=owner["user_id"],
        )

        preparation_timestamp = _local_datetime(
            completion_date - timedelta(days=2),
            14,
            0,
        )
        approval_status = config.APPROVAL_STATUSES[completed_index % 3]
        clock.set(preparation_timestamp)
        request = update_request(
            connection,
            request["request_id"],
            updated_by_user_id=owner["user_id"],
            procurement_route=route,
            closure_note=(
                "The procurement activity is complete and the related "
                "external record references have been recorded."
            ),
            officer_note=(
                "Final route and closure information were reviewed before "
                "completion."
            ),
            **_approval_changes(
                status=approval_status,
                confirmation_timestamp=preparation_timestamp
                - timedelta(hours=1),
                index=index,
            ),
        )

        reference_timestamp = _local_datetime(
            completion_date - timedelta(days=1),
            11,
            0,
        )
        reference_type = (
            "Purchase Order"
            if route in ("Low-Value Purchase", "Other")
            else (
                "Solicitation or RFP"
                if route == "Competitive Procurement"
                else (
                    "Amendment"
                    if route == "Contract Amendment"
                    else "Contract"
                )
            )
        )
        clock.set(reference_timestamp)
        _add_reference(
            connection,
            request=request,
            reference_type=reference_type,
            reference_index=index,
            actor_id=owner["user_id"],
            is_closure_evidence=closure_required,
        )
        if completed_index == 2:
            clock.set(reference_timestamp + timedelta(minutes=20))
            _add_reference(
                connection,
                request=request,
                reference_type="Approval Record",
                reference_index=100 + index,
                actor_id=owner["user_id"],
            )

        if closure_required:
            clock.set(reference_timestamp + timedelta(hours=1))
            request = update_request(
                connection,
                request["request_id"],
                updated_by_user_id=owner["user_id"],
                closure_evidence_confirmed=True,
            )

        clock.set(_local_datetime(completion_date, 16, 0))
        request = transition_request_status(
            connection,
            request["request_id"],
            new_status="Completed",
            updated_by_user_id=owner["user_id"],
        )

        if completed_index == 0:
            _simulate_imported_completed_closure_issue(
                connection,
                request_id=request["request_id"],
            )
        requests.append(request)
    return requests


def _create_cancelled_requests(
    connection,
    *,
    clock: _ScheduledClock,
    reference_date: date,
    randomizer: random.Random,
    officers: list[dict[str, Any]],
    managers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    requests = []
    for cancelled_index in range(4):
        index = cancelled_index + 44
        title, category = REQUEST_EXAMPLES[index]
        cancellation_date = reference_date - timedelta(
            days=4 - cancelled_index
        )
        submitted_date = cancellation_date - timedelta(days=3)
        route = config.PROCUREMENT_ROUTES[
            (cancelled_index + 2) % len(config.PROCUREMENT_ROUTES)
        ]
        creator = managers[index % len(managers)]
        owner = officers[cancelled_index % len(officers)]

        clock.set(_local_datetime(submitted_date, 9, 0))
        request = create_request(
            connection,
            created_by_user_id=creator["user_id"],
            request_title=title,
            requestor_name=REQUESTOR_NAMES[
                randomizer.randrange(len(REQUESTOR_NAMES))
            ],
            business_unit=config.BUSINESS_UNITS[
                index % len(config.BUSINESS_UNITS)
            ],
            request_category=category,
            description=_description_for(title, category, route),
            priority=config.PRIORITIES[index % len(config.PRIORITIES)],
            required_by_date=cancellation_date + timedelta(days=7),
            estimated_value=_estimated_value(
                route,
                index=index,
                randomizer=randomizer,
            ),
        )

        if cancelled_index >= 2:
            clock.set(
                _local_datetime(
                    submitted_date + timedelta(days=1),
                    10,
                    30,
                )
            )
            request = assign_request(
                connection,
                request["request_id"],
                procurement_owner_user_id=owner["user_id"],
                assigned_by_user_id=creator["user_id"],
            )

        clock.set(
            _local_datetime(
                cancellation_date - timedelta(days=1),
                13,
                30,
            )
        )
        request = update_request(
            connection,
            request["request_id"],
            updated_by_user_id=(
                owner["user_id"]
                if cancelled_index >= 2
                else creator["user_id"]
            ),
            procurement_route=route,
            officer_note=(
                "The request was reviewed before the cancellation decision "
                "was recorded."
            ),
        )

        clock.set(_local_datetime(cancellation_date, 15, 30))
        request = transition_request_status(
            connection,
            request["request_id"],
            new_status="Cancelled",
            updated_by_user_id=creator["user_id"],
            cancellation_reason=config.CANCELLATION_REASONS[
                cancelled_index
            ],
        )
        requests.append(request)
    return requests


def generate_demo_data(
    database_path: str | Path,
    *,
    reference_date: date,
    seed: int = DEFAULT_SEED,
    reset: bool = False,
) -> dict[str, int]:
    """Generate the approved 6-user, 48-request fictional demo dataset."""
    if isinstance(reference_date, datetime) or not isinstance(
        reference_date,
        date,
    ):
        raise DemoDataError("reference_date must be a date.")
    if not isinstance(seed, int):
        raise DemoDataError("seed must be an integer.")

    path = Path(database_path)
    initialize_database(path, reset=reset)
    connection = connect_database(path)
    randomizer = random.Random(seed)
    initial_timestamp = _local_datetime(
        reference_date - timedelta(days=180),
        9,
        0,
    )

    try:
        _require_empty_database(connection)
        with _deterministic_database_runtime(
            seed=seed,
            initial_timestamp=initial_timestamp,
        ) as clock:
            users = []
            for user_index, (display_name, email, role) in enumerate(
                USER_DEFINITIONS
            ):
                clock.set(initial_timestamp + timedelta(minutes=user_index))
                users.append(
                    create_user(
                        connection,
                        display_name=display_name,
                        email=email,
                        role=role,
                    )
                )

            officers = [
                user
                for user in users
                if user["role"] == "Procurement Officer"
            ]
            managers = [
                user
                for user in users
                if user["role"] == "Procurement Manager"
            ]

            requests = []
            requests.extend(
                _create_submitted_requests(
                    connection,
                    clock=clock,
                    reference_date=reference_date,
                    randomizer=randomizer,
                    managers=managers,
                )
            )
            requests.extend(
                _create_active_requests(
                    connection,
                    clock=clock,
                    reference_date=reference_date,
                    randomizer=randomizer,
                    officers=officers,
                    managers=managers,
                )
            )
            requests.extend(
                _create_completed_requests(
                    connection,
                    clock=clock,
                    reference_date=reference_date,
                    randomizer=randomizer,
                    officers=officers,
                    managers=managers,
                )
            )
            requests.extend(
                _create_cancelled_requests(
                    connection,
                    clock=clock,
                    reference_date=reference_date,
                    randomizer=randomizer,
                    officers=officers,
                    managers=managers,
                )
            )

        if len(users) != 6 or len(requests) != 48:
            raise DemoDataError(
                "Internal generation error: expected 6 users and 48 requests."
            )

        return {
            "app_users": connection.execute(
                "SELECT COUNT(*) FROM app_users"
            ).fetchone()[0],
            "procurement_requests": connection.execute(
                "SELECT COUNT(*) FROM procurement_requests"
            ).fetchone()[0],
            "request_references": connection.execute(
                "SELECT COUNT(*) FROM request_references"
            ).fetchone()[0],
            "request_history": connection.execute(
                "SELECT COUNT(*) FROM request_history"
            ).fetchone()[0],
        }
    except ValidationError as exc:
        raise DemoDataError(
            f"Approved database validation rejected generated data: {exc}"
        ) from exc
    finally:
        connection.close()


def _parse_reference_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "reference date must use YYYY-MM-DD"
        ) from exc


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate deterministic fictional ProcureFlow demo data."
    )
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument(
        "--reference-date",
        required=True,
        type=_parse_reference_date,
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--reset", action="store_true")
    arguments = parser.parse_args()

    counts = generate_demo_data(
        arguments.database,
        reference_date=arguments.reference_date,
        seed=arguments.seed,
        reset=arguments.reset,
    )
    for table_name, count in counts.items():
        print(f"{table_name}: {count}")


if __name__ == "__main__":
    main()
