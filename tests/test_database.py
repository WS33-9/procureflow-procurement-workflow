"""Verification tests for the approved ProcureFlow database MVP."""

from __future__ import annotations

import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from src import config
from src.database import (
    ValidationError,
    _insert_history,
    add_request_reference,
    assign_request,
    connect_database,
    create_request,
    create_user,
    get_request,
    initialize_database,
    list_request_history,
    list_table_names,
    now_local,
    transition_request_status,
    update_request,
)


class DatabaseWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temp_directory.name) / "procureflow_test.duckdb"
        )
        initialize_database(self.database_path, reset=True)
        self.connection = connect_database(self.database_path)

        self.manager = create_user(
            self.connection,
            display_name="Morgan Lee",
            email="morgan.lee@northbridge.example",
            role="Procurement Manager",
        )
        self.officer = create_user(
            self.connection,
            display_name="Alex Morgan",
            email="alex.morgan@northbridge.example",
            role="Procurement Officer",
        )
        self.administrator = create_user(
            self.connection,
            display_name="Jordan Singh",
            email="jordan.singh@northbridge.example",
            role="Administrator",
        )

    def tearDown(self):
        self.connection.close()
        self.temp_directory.cleanup()

    def create_valid_request(self, **overrides):
        values = {
            "created_by_user_id": self.manager["user_id"],
            "request_title": "Network equipment refresh",
            "requestor_name": "Taylor Morgan",
            "business_unit": "Technology",
            "request_category": "Technology",
            "description": "Replace aging network equipment at the Toronto office.",
            "priority": "High",
            "required_by_date": now_local().date() + timedelta(days=30),
            "estimated_value": 45000,
            "closure_evidence_required": True,
        }
        values.update(overrides)
        return create_request(self.connection, **values)

    def test_approved_four_table_schema_only(self):
        self.assertEqual(
            list_table_names(self.connection),
            [
                "app_users",
                "procurement_requests",
                "request_history",
                "request_references",
            ],
        )

    def test_complete_verified_workflow(self):
        request = self.create_valid_request()
        self.assertEqual(request["request_number"], "PF-0001")
        self.assertEqual(request["lifecycle_status"], "Submitted")
        self.assertIsNotNone(request["submitted_at"].tzinfo)

        request = assign_request(
            self.connection,
            request["request_id"],
            procurement_owner_user_id=self.officer["user_id"],
            assigned_by_user_id=self.manager["user_id"],
        )
        self.assertEqual(request["lifecycle_status"], "Assigned")
        self.assertIsNotNone(request["assignment_date"].tzinfo)
        self.assertEqual(
            request["procurement_owner_user_id"],
            self.officer["user_id"],
        )

        request = transition_request_status(
            self.connection,
            request["request_id"],
            new_status="In Progress",
            updated_by_user_id=self.officer["user_id"],
        )
        self.assertEqual(request["lifecycle_status"], "In Progress")

        request = update_request(
            self.connection,
            request["request_id"],
            updated_by_user_id=self.officer["user_id"],
            procurement_route="Low-Value Purchase",
            closure_note="Purchase order issued and linked to the request.",
        )

        reference = add_request_reference(
            self.connection,
            request["request_id"],
            reference_type="Purchase Order",
            reference_number="PO-2026-0042",
            source_system_or_process="ERP",
            reference_link="https://example.invalid/po/PO-2026-0042",
            is_closure_evidence=True,
            note="Final purchasing record.",
            added_by_user_id=self.officer["user_id"],
        )
        self.assertTrue(reference["is_closure_evidence"])

        with self.assertRaisesRegex(
            ValidationError,
            "required closure evidence has not been confirmed",
        ):
            transition_request_status(
                self.connection,
                request["request_id"],
                new_status="Completed",
                updated_by_user_id=self.officer["user_id"],
            )

        self.assertEqual(
            get_request(
                self.connection,
                request["request_id"],
            )["lifecycle_status"],
            "In Progress",
        )

        request = update_request(
            self.connection,
            request["request_id"],
            updated_by_user_id=self.officer["user_id"],
            closure_evidence_confirmed=True,
        )
        request = transition_request_status(
            self.connection,
            request["request_id"],
            new_status="Completed",
            updated_by_user_id=self.officer["user_id"],
        )
        self.assertEqual(request["lifecycle_status"], "Completed")
        self.assertIsNotNone(request["completion_date"])
        self.assertIsNotNone(request["completion_date"].tzinfo)

        history = list_request_history(
            self.connection,
            request["request_id"],
        )
        event_types = [item["event_type"] for item in history]
        self.assertEqual(event_types[0], "Request Created")
        self.assertIn("Assigned", event_types)
        self.assertIn("Status Changed", event_types)
        self.assertIn("Reference Added", event_types)
        self.assertIn("Closure Evidence Updated", event_types)
        self.assertEqual(event_types[-1], "Completed")
        self.assertGreaterEqual(len(history), 7)

        with self.assertRaisesRegex(ValidationError, "terminal"):
            transition_request_status(
                self.connection,
                request["request_id"],
                new_status="Cancelled",
                updated_by_user_id=self.manager["user_id"],
                cancellation_reason="Request Withdrawn",
            )

    def test_request_numbering_is_unique_and_sequential(self):
        first = self.create_valid_request()
        second = self.create_valid_request(
            request_title="Facilities consulting support",
            request_category="Professional Services",
            business_unit="Corporate Services",
            priority="Medium",
            closure_evidence_required=False,
        )
        self.assertEqual(first["request_number"], "PF-0001")
        self.assertEqual(second["request_number"], "PF-0002")
        self.assertNotEqual(first["request_number"], second["request_number"])

    def test_submission_and_controlled_value_validation(self):
        with self.assertRaisesRegex(ValidationError, "request_title is required"):
            self.create_valid_request(request_title=" ")

        with self.assertRaisesRegex(
            ValidationError,
            "estimated_value cannot be negative",
        ):
            self.create_valid_request(estimated_value=-1)

        with self.assertRaisesRegex(ValidationError, "priority must be one of"):
            self.create_valid_request(priority="Critical")

        self.assertEqual(
            config.ATTENTION_RULE_THRESHOLDS[
                "assignment_overdue_business_days"
            ],
            1,
        )
        self.assertEqual(
            config.ATTENTION_RULE_THRESHOLDS[
                "no_recent_update_calendar_days"
            ],
            7,
        )
        self.assertEqual(config.APPLICATION_TIMEZONE, "America/Toronto")

    def test_revised_controlled_value_configuration(self):
        self.assertEqual(
            config.BUSINESS_UNITS,
            (
                "Corporate Services",
                "Finance",
                "Human Resources",
                "Business Operations",
                "Technology",
            ),
        )
        self.assertEqual(
            config.REQUEST_CATEGORIES,
            (
                "Technology",
                "Professional Services",
                "Facilities",
                "Equipment",
                "Marketing",
                "Logistics",
                "Office and Administrative Services",
            ),
        )
        self.assertEqual(
            config.PROCUREMENT_ROUTES,
            (
                "Low-Value Purchase",
                "Competitive Procurement",
                "Non-Competitive Procurement",
                "Existing Contract or Agreement",
                "Contract Amendment",
                "Other",
            ),
        )
        self.assertEqual(
            config.DEPENDENCY_TYPES,
            (
                "Required Information",
                "Approval",
                "Supplier Response",
                "Signature",
                "Internal Review",
                "System or Financial Action",
                "Other",
            ),
        )
        self.assertIn("Official Document Reference", config.REFERENCE_TYPES)
        self.assertNotIn("Official Document", config.REFERENCE_TYPES)
        self.assertEqual(
            config.CANCELLATION_REASONS,
            (
                "Request Withdrawn",
                "Requirement No Longer Needed",
                "Duplicate Request",
                "Funding Not Available",
                "Replaced by Another Procurement Approach",
                "Other",
            ),
        )
        self.assertNotIn("Reference Removed", config.HISTORY_EVENT_TYPES)

    def test_revised_business_unit_and_request_category_validation(self):
        request = self.create_valid_request(
            business_unit="Business Operations",
            request_category="Office and Administrative Services",
        )
        self.assertEqual(request["business_unit"], "Business Operations")
        self.assertEqual(
            request["request_category"],
            "Office and Administrative Services",
        )

        with self.assertRaisesRegex(
            ValidationError,
            "business_unit must be one of",
        ):
            self.create_valid_request(
                request_title="Retired business-unit value",
                business_unit="Operations",
            )

        with self.assertRaisesRegex(
            ValidationError,
            "request_category must be one of",
        ):
            self.create_valid_request(
                request_title="Retired request-category value",
                request_category="Corporate Operations",
            )

    def test_every_revised_route_and_dependency_type_is_accepted(self):
        request = self.create_valid_request(closure_evidence_required=False)
        request = assign_request(
            self.connection,
            request["request_id"],
            procurement_owner_user_id=self.officer["user_id"],
            assigned_by_user_id=self.manager["user_id"],
        )
        request = transition_request_status(
            self.connection,
            request["request_id"],
            new_status="In Progress",
            updated_by_user_id=self.officer["user_id"],
        )

        for route in config.PROCUREMENT_ROUTES:
            request = update_request(
                self.connection,
                request["request_id"],
                updated_by_user_id=self.officer["user_id"],
                procurement_route=route,
            )
            self.assertEqual(request["procurement_route"], route)

        dependency_values = {
            "current_dependency": "Waiting for an external action.",
            "dependency_owner": "Business requestor",
            "next_action": "Follow up and record the response.",
            "follow_up_date": now_local().date() + timedelta(days=3),
        }
        for dependency_type in config.DEPENDENCY_TYPES:
            request = update_request(
                self.connection,
                request["request_id"],
                updated_by_user_id=self.officer["user_id"],
                dependency_type=dependency_type,
                **dependency_values,
            )
            self.assertEqual(request["dependency_type"], dependency_type)

        self.assertEqual(request["dependency_type"], "Other")
        self.assertIn(
            "System or Financial Action",
            config.DEPENDENCY_TYPES,
        )

        with self.assertRaisesRegex(
            ValidationError,
            "procurement_route must be one of",
        ):
            update_request(
                self.connection,
                request["request_id"],
                updated_by_user_id=self.officer["user_id"],
                procurement_route="Existing Agreement",
            )

    def test_every_revised_reference_type_is_accepted(self):
        request = self.create_valid_request(closure_evidence_required=False)

        for index, reference_type in enumerate(
            config.REFERENCE_TYPES,
            start=1,
        ):
            reference = add_request_reference(
                self.connection,
                request["request_id"],
                reference_type=reference_type,
                reference_number=f"REF-{index:03d}",
                source_system_or_process="Approved external process",
                added_by_user_id=self.manager["user_id"],
            )
            self.assertEqual(reference["reference_type"], reference_type)

        with self.assertRaisesRegex(
            ValidationError,
            "reference_type must be one of",
        ):
            add_request_reference(
                self.connection,
                request["request_id"],
                reference_type="Official Document",
                reference_number="OLD-001",
                source_system_or_process="Document repository",
                added_by_user_id=self.manager["user_id"],
            )

    def test_every_revised_cancellation_reason_is_accepted(self):
        for index, reason in enumerate(config.CANCELLATION_REASONS, start=1):
            request = self.create_valid_request(
                request_title=f"Cancellation validation {index}",
                closure_evidence_required=False,
            )
            cancelled = transition_request_status(
                self.connection,
                request["request_id"],
                new_status="Cancelled",
                updated_by_user_id=self.manager["user_id"],
                cancellation_reason=reason,
            )
            self.assertEqual(cancelled["cancellation_reason"], reason)

        for old_reason in (
            "Budget Not Available",
            "Replaced by Another Request",
        ):
            request = self.create_valid_request(
                request_title=f"Retired value {old_reason}",
                closure_evidence_required=False,
            )
            with self.assertRaisesRegex(
                ValidationError,
                "cancellation_reason must be one of",
            ):
                transition_request_status(
                    self.connection,
                    request["request_id"],
                    new_status="Cancelled",
                    updated_by_user_id=self.manager["user_id"],
                    cancellation_reason=old_reason,
                )

    def test_past_required_by_date_is_accepted(self):
        past_date = now_local().date() - timedelta(days=10)
        request = self.create_valid_request(required_by_date=past_date)
        self.assertEqual(request["required_by_date"], past_date)
        self.assertEqual(request["lifecycle_status"], "Submitted")

    def test_approval_and_cancellation_validation(self):
        request = self.create_valid_request(closure_evidence_required=False)
        request = assign_request(
            self.connection,
            request["request_id"],
            procurement_owner_user_id=self.officer["user_id"],
            assigned_by_user_id=self.manager["user_id"],
        )
        request = transition_request_status(
            self.connection,
            request["request_id"],
            new_status="In Progress",
            updated_by_user_id=self.officer["user_id"],
        )

        with self.assertRaisesRegex(
            ValidationError,
            "approval_source is required",
        ):
            update_request(
                self.connection,
                request["request_id"],
                updated_by_user_id=self.officer["user_id"],
                approval_required=True,
                approval_requirement="Director approval",
                approval_status="Confirmed",
            )

        with self.assertRaisesRegex(
            ValidationError,
            "cancellation_reason is required",
        ):
            transition_request_status(
                self.connection,
                request["request_id"],
                new_status="Cancelled",
                updated_by_user_id=self.manager["user_id"],
            )

        cancelled = transition_request_status(
            self.connection,
            request["request_id"],
            new_status="Cancelled",
            updated_by_user_id=self.manager["user_id"],
            cancellation_reason="Request Withdrawn",
        )
        self.assertEqual(cancelled["lifecycle_status"], "Cancelled")
        self.assertIsNotNone(cancelled["cancellation_date"])

    def test_missing_parent_child_writes_are_rejected(self):
        missing_request_id = uuid4()

        with self.assertRaisesRegex(ValidationError, "does not exist"):
            _insert_history(
                self.connection,
                request_id=missing_request_id,
                event_type="Status Changed",
                event_summary="This row must not be inserted.",
                event_by_user_id=self.manager["user_id"],
                field_name="lifecycle_status",
                previous_value="Submitted",
                new_value="Assigned",
            )

        with self.assertRaisesRegex(ValidationError, "does not exist"):
            add_request_reference(
                self.connection,
                missing_request_id,
                reference_type="Purchase Order",
                reference_number="PO-MISSING",
                source_system_or_process="ERP",
                added_by_user_id=self.manager["user_id"],
            )

        history_count = self.connection.execute(
            "SELECT COUNT(*) FROM request_history"
        ).fetchone()[0]
        reference_count = self.connection.execute(
            "SELECT COUNT(*) FROM request_references"
        ).fetchone()[0]
        self.assertEqual(history_count, 0)
        self.assertEqual(reference_count, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
