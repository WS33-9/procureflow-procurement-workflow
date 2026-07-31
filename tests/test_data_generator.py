"""Verification tests for deterministic fictional ProcureFlow demo data."""

from __future__ import annotations

import tempfile
import unittest
from collections import Counter
from datetime import date
from pathlib import Path

from src import config
from src.data_generator import (
    DEFAULT_SEED,
    LEGACY_ISSUE_TITLE,
    generate_demo_data,
)
from src.database import connect_database, list_table_names
from src.rules import (
    ASSIGNMENT_OVERDUE,
    COMPLETED_MISSING_CLOSURE_EVIDENCE,
    FOLLOW_UP_OVERDUE,
    HIGH_PRIORITY_OVERDUE_DEPENDENCY,
    NO_RECENT_UPDATE,
    REQUIRED_APPROVAL_NOT_CONFIRMED,
    REQUIRED_INFORMATION_OUTSTANDING,
    TARGET_COMPLETION_MISSED,
    evaluate_request_attention,
    evaluate_requests_attention,
)


REFERENCE_DATE = date(2026, 7, 30)
OPEN_WORK_RULE_CODES = {
    ASSIGNMENT_OVERDUE,
    FOLLOW_UP_OVERDUE,
    TARGET_COMPLETION_MISSED,
    REQUIRED_INFORMATION_OUTSTANDING,
    REQUIRED_APPROVAL_NOT_CONFIRMED,
    NO_RECENT_UPDATE,
    HIGH_PRIORITY_OVERDUE_DEPENDENCY,
}


def _fetch_dicts(connection, query, parameters=()):
    cursor = connection.execute(query, list(parameters))
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _table_snapshot(connection):
    snapshot = {}
    primary_keys = {
        "app_users": "user_id",
        "procurement_requests": "request_id",
        "request_references": "reference_id",
        "request_history": "history_id",
    }
    for table_name, primary_key in primary_keys.items():
        snapshot[table_name] = connection.execute(
            f"SELECT * FROM {table_name} ORDER BY {primary_key}"
        ).fetchall()
    return snapshot


class DemoDataGeneratorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_directory = tempfile.TemporaryDirectory()
        cls.database_path = (
            Path(cls.temp_directory.name) / "procureflow_demo.duckdb"
        )
        cls.generated_counts = generate_demo_data(
            cls.database_path,
            reference_date=REFERENCE_DATE,
            seed=DEFAULT_SEED,
            reset=True,
        )
        cls.connection = connect_database(cls.database_path)
        cls.requests = _fetch_dicts(
            cls.connection,
            """
            SELECT
                r.*,
                u.display_name AS procurement_owner_name,
                (
                    SELECT COUNT(*)
                    FROM request_references rr
                    WHERE rr.request_id = r.request_id
                      AND rr.is_closure_evidence = TRUE
                ) AS closure_evidence_reference_count
            FROM procurement_requests r
            LEFT JOIN app_users u
              ON u.user_id = r.procurement_owner_user_id
            ORDER BY r.request_number
            """,
        )
        cls.results = evaluate_requests_attention(
            cls.requests,
            as_of=REFERENCE_DATE,
        )
        cls.rule_counts = Counter(
            result["rule_code"] for result in cls.results
        )

    @classmethod
    def tearDownClass(cls):
        cls.connection.close()
        cls.temp_directory.cleanup()

    def request_matching(self, predicate):
        return next(
            request for request in self.requests if predicate(request)
        )

    def evaluate_one(self, request):
        return evaluate_request_attention(
            request,
            as_of=REFERENCE_DATE,
            procurement_owner_name=request.get(
                "procurement_owner_name"
            ),
            closure_evidence_reference_count=request.get(
                "closure_evidence_reference_count",
                0,
            ),
        )

    def test_same_seed_and_reference_date_are_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            first_path = Path(directory) / "first.duckdb"
            second_path = Path(directory) / "second.duckdb"
            generate_demo_data(
                first_path,
                reference_date=REFERENCE_DATE,
                seed=DEFAULT_SEED,
                reset=True,
            )
            generate_demo_data(
                second_path,
                reference_date=REFERENCE_DATE,
                seed=DEFAULT_SEED,
                reset=True,
            )
            first_connection = connect_database(first_path)
            second_connection = connect_database(second_path)
            try:
                self.assertEqual(
                    _table_snapshot(first_connection),
                    _table_snapshot(second_connection),
                )
            finally:
                first_connection.close()
                second_connection.close()

    def test_reset_mode_recreates_without_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reset.duckdb"
            first = generate_demo_data(
                path,
                reference_date=REFERENCE_DATE,
                seed=DEFAULT_SEED,
                reset=True,
            )
            second = generate_demo_data(
                path,
                reference_date=REFERENCE_DATE,
                seed=DEFAULT_SEED,
                reset=True,
            )
            self.assertEqual(first, second)
            self.assertEqual(second["app_users"], 6)
            self.assertEqual(second["procurement_requests"], 48)

    def test_exact_user_and_request_counts(self):
        self.assertEqual(self.generated_counts["app_users"], 6)
        self.assertEqual(
            self.generated_counts["procurement_requests"],
            48,
        )
        role_counts = dict(
            self.connection.execute(
                """
                SELECT role, COUNT(*)
                FROM app_users
                GROUP BY role
                """
            ).fetchall()
        )
        self.assertEqual(
            role_counts,
            {
                "Procurement Officer": 3,
                "Procurement Manager": 2,
                "Administrator": 1,
            },
        )
        emails = [
            row[0]
            for row in self.connection.execute(
                "SELECT email FROM app_users"
            ).fetchall()
        ]
        self.assertTrue(
            all(email.endswith("@northbridge.example") for email in emails)
        )
        officers = self.connection.execute(
            """
            SELECT display_name, email
            FROM app_users
            WHERE role = 'Procurement Officer'
            ORDER BY display_name
            """
        ).fetchall()
        self.assertEqual(
            officers,
            [
                ("Alex Morgan", "alex.morgan@northbridge.example"),
                ("Casey Reed", "casey.reed@northbridge.example"),
                ("Taylor Brooks", "taylor.brooks@northbridge.example"),
            ],
        )

    def test_open_workload_and_attention_are_reasonably_balanced(self):
        open_requests = [
            request
            for request in self.requests
            if request["lifecycle_status"]
            in ("Submitted", "Assigned", "In Progress")
        ]
        attention_request_numbers = {
            result["request_number"] for result in self.results
        }
        workload = Counter(
            request["procurement_owner_name"] or "Unassigned"
            for request in open_requests
        )
        attention = Counter(
            request["procurement_owner_name"] or "Unassigned"
            for request in open_requests
            if request["request_number"] in attention_request_numbers
        )
        self.assertEqual(
            workload,
            {
                "Alex Morgan": 10,
                "Casey Reed": 9,
                "Taylor Brooks": 9,
                "Unassigned": 8,
            },
        )
        self.assertEqual(
            attention,
            {
                "Alex Morgan": 7,
                "Casey Reed": 6,
                "Taylor Brooks": 6,
                "Unassigned": 5,
            },
        )

    def test_default_attention_queue_copy_is_targeted_and_specific(self):
        expected = {
            "PF-0009": (
                "Final content and print specifications are still outstanding.",
                "Confirm the final report specifications with Corporate Services.",
            ),
            "PF-0011": (
                "The supplier has not confirmed the assessment start date.",
                "Follow up with the supplier and update the expected start date.",
            ),
            "PF-0012": (
                "The equipment agreement is awaiting an authorized signature.",
                "Confirm when the signed equipment agreement is available.",
            ),
            "PF-0016": (
                "Final card quantities and delivery locations are not confirmed.",
                "Confirm quantities and delivery locations with the requestor.",
            ),
            "PF-0024": (
                "Written approval for the priority service has not been linked.",
                "Ask the business sponsor to provide the approval reference.",
            ),
            "PF-0027": (
                "The replacement-device configuration is still under internal review.",
                "Complete the device configuration review.",
            ),
            "PF-0036": (
                "Final distribution quantities remain unresolved.",
                "Confirm distribution quantities with the requesting team.",
            ),
        }
        by_number = {
            request["request_number"]: request for request in self.requests
        }
        for request_number, (dependency, next_action) in expected.items():
            with self.subTest(request_number=request_number):
                request = by_number[request_number]
                self.assertEqual(request["current_dependency"], dependency)
                self.assertEqual(request["next_action"], next_action)

    def test_lifecycle_distribution_is_exact(self):
        counts = Counter(
            request["lifecycle_status"] for request in self.requests
        )
        self.assertEqual(
            counts,
            {
                "Submitted": 8,
                "Assigned": 8,
                "In Progress": 20,
                "Completed": 8,
                "Cancelled": 4,
            },
        )

    def test_all_controlled_values_and_dataset_variants_are_covered(self):
        self.assertEqual(
            {request["business_unit"] for request in self.requests},
            set(config.BUSINESS_UNITS),
        )
        self.assertEqual(
            {request["request_category"] for request in self.requests},
            set(config.REQUEST_CATEGORIES),
        )
        self.assertEqual(
            {request["priority"] for request in self.requests},
            set(config.PRIORITIES),
        )
        self.assertEqual(
            {
                request["procurement_route"]
                for request in self.requests
                if request["procurement_route"] is not None
            },
            set(config.PROCUREMENT_ROUTES),
        )
        self.assertEqual(
            {
                request["dependency_type"]
                for request in self.requests
                if request["dependency_type"] is not None
            },
            set(config.DEPENDENCY_TYPES),
        )
        self.assertEqual(
            {request["approval_status"] for request in self.requests},
            set(config.APPROVAL_STATUSES),
        )

        for request in self.requests:
            if request["approval_required"]:
                self.assertIn(
                    request["approval_status"],
                    ("Not Confirmed", "Confirmed"),
                )
            else:
                self.assertEqual(
                    request["approval_status"],
                    "Not Required",
                )

        self.assertTrue(
            any(
                request["procurement_owner_user_id"] is None
                for request in self.requests
            )
        )
        self.assertGreaterEqual(
            len(
                {
                    request["procurement_owner_user_id"]
                    for request in self.requests
                    if request["procurement_owner_user_id"] is not None
                }
            ),
            3,
        )
        self.assertTrue(
            any(
                request["estimated_value"] is None
                for request in self.requests
            )
        )
        self.assertTrue(
            any(
                request["estimated_value"] is not None
                for request in self.requests
            )
        )
        self.assertTrue(
            any(
                request["required_by_date"] < REFERENCE_DATE
                for request in self.requests
            )
        )
        self.assertTrue(
            any(
                request["required_by_date"] > REFERENCE_DATE
                for request in self.requests
            )
        )
        self.assertTrue(
            any(
                request["closure_evidence_required"]
                for request in self.requests
            )
        )
        self.assertTrue(
            any(
                not request["closure_evidence_required"]
                for request in self.requests
            )
        )

        reference_type_count = self.connection.execute(
            """
            SELECT COUNT(DISTINCT reference_type)
            FROM request_references
            """
        ).fetchone()[0]
        self.assertGreaterEqual(reference_type_count, 5)

    def test_seven_open_work_rules_trigger_at_least_twice(self):
        for rule_code in OPEN_WORK_RULE_CODES:
            with self.subTest(rule_code=rule_code):
                self.assertGreaterEqual(self.rule_counts[rule_code], 2)

    def test_closure_safeguard_triggers_exactly_once(self):
        self.assertEqual(
            self.rule_counts[COMPLETED_MISSING_CLOSURE_EVIDENCE],
            1,
        )
        closure_results = [
            result
            for result in self.results
            if result["rule_code"]
            == COMPLETED_MISSING_CLOSURE_EVIDENCE
        ]
        self.assertEqual(
            closure_results[0]["request_title"],
            LEGACY_ISSUE_TITLE,
        )

    def test_every_rule_has_a_clear_negative_control(self):
        recent_submitted = self.request_matching(
            lambda request: request["lifecycle_status"] == "Submitted"
            and (
                REFERENCE_DATE
                - request["submitted_at"]
                .astimezone(configured_zone())
                .date()
            ).days
            <= 1
        )
        self.assertNotIn(
            ASSIGNMENT_OVERDUE,
            rule_codes(self.evaluate_one(recent_submitted)),
        )

        follow_up_due_today = self.request_matching(
            lambda request: request["lifecycle_status"]
            in ("Assigned", "In Progress")
            and request["current_dependency"]
            and request["follow_up_date"] == REFERENCE_DATE
        )
        self.assertNotIn(
            FOLLOW_UP_OVERDUE,
            rule_codes(self.evaluate_one(follow_up_due_today)),
        )

        target_due_today = self.request_matching(
            lambda request: request["lifecycle_status"]
            in ("Assigned", "In Progress")
            and request["target_completion_date"] == REFERENCE_DATE
        )
        self.assertNotIn(
            TARGET_COMPLETION_MISSED,
            rule_codes(self.evaluate_one(target_due_today)),
        )

        other_dependency = self.request_matching(
            lambda request: request["lifecycle_status"]
            in ("Assigned", "In Progress")
            and request["current_dependency"]
            and request["dependency_type"] != "Required Information"
        )
        self.assertNotIn(
            REQUIRED_INFORMATION_OUTSTANDING,
            rule_codes(self.evaluate_one(other_dependency)),
        )

        confirmed_approval = self.request_matching(
            lambda request: request["lifecycle_status"]
            in ("Assigned", "In Progress")
            and request["approval_required"]
            and request["approval_status"] == "Confirmed"
        )
        self.assertNotIn(
            REQUIRED_APPROVAL_NOT_CONFIRMED,
            rule_codes(self.evaluate_one(confirmed_approval)),
        )

        six_day_update = self.request_matching(
            lambda request: request["lifecycle_status"]
            in ("Submitted", "Assigned", "In Progress")
            and (
                REFERENCE_DATE
                - request["updated_at"]
                .astimezone(configured_zone())
                .date()
            ).days
            == 6
        )
        self.assertNotIn(
            NO_RECENT_UPDATE,
            rule_codes(self.evaluate_one(six_day_update)),
        )

        medium_overdue_dependency = self.request_matching(
            lambda request: request["lifecycle_status"]
            in ("Assigned", "In Progress")
            and request["priority"] == "Medium"
            and request["current_dependency"]
            and request["follow_up_date"] < REFERENCE_DATE
        )
        medium_codes = rule_codes(
            self.evaluate_one(medium_overdue_dependency)
        )
        self.assertIn(FOLLOW_UP_OVERDUE, medium_codes)
        self.assertNotIn(HIGH_PRIORITY_OVERDUE_DEPENDENCY, medium_codes)

        valid_completed = self.request_matching(
            lambda request: request["lifecycle_status"] == "Completed"
            and request["closure_evidence_required"]
            and request["request_title"] != LEGACY_ISSUE_TITLE
        )
        self.assertNotIn(
            COMPLETED_MISSING_CLOSURE_EVIDENCE,
            rule_codes(self.evaluate_one(valid_completed)),
        )

    def test_all_other_completed_requests_are_valid(self):
        completed = [
            request
            for request in self.requests
            if request["lifecycle_status"] == "Completed"
        ]
        self.assertEqual(len(completed), 8)

        for request in completed:
            self.assertIsNotNone(request["closure_note"])
            self.assertIsNotNone(request["completion_date"])
            self.assertIsNone(request["cancellation_date"])
            if request["request_title"] == LEGACY_ISSUE_TITLE:
                self.assertTrue(request["closure_evidence_required"])
                self.assertFalse(request["closure_evidence_confirmed"])
                continue
            if request["closure_evidence_required"]:
                self.assertTrue(request["closure_evidence_confirmed"])
                self.assertGreaterEqual(
                    request["closure_evidence_reference_count"],
                    1,
                )

    def test_cancelled_and_terminal_request_rules(self):
        cancelled = [
            request
            for request in self.requests
            if request["lifecycle_status"] == "Cancelled"
        ]
        self.assertEqual(len(cancelled), 4)
        for request in cancelled:
            self.assertIsNotNone(request["cancellation_date"])
            self.assertIn(
                request["cancellation_reason"],
                config.CANCELLATION_REASONS,
            )
            self.assertEqual(self.evaluate_one(request), [])

        for request in self.requests:
            if request["lifecycle_status"] not in ("Completed", "Cancelled"):
                continue
            result_codes = set(rule_codes(self.evaluate_one(request)))
            self.assertTrue(result_codes.isdisjoint(OPEN_WORK_RULE_CODES))

    def test_request_numbers_and_reference_parents_are_valid(self):
        numbers = [
            request["request_number"] for request in self.requests
        ]
        self.assertEqual(len(numbers), len(set(numbers)))
        self.assertEqual(numbers[0], "PF-0001")
        self.assertEqual(numbers[-1], "PF-0048")

        orphan_count = self.connection.execute(
            """
            SELECT COUNT(*)
            FROM request_references rr
            LEFT JOIN procurement_requests r
              ON r.request_id = rr.request_id
            WHERE r.request_id IS NULL
            """
        ).fetchone()[0]
        self.assertEqual(orphan_count, 0)

        multiple_reference_count = self.connection.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT request_id
                FROM request_references
                GROUP BY request_id
                HAVING COUNT(*) > 1
            )
            """
        ).fetchone()[0]
        self.assertGreaterEqual(multiple_reference_count, 2)

    def test_timestamps_and_history_are_chronologically_coherent(self):
        timestamp_fields = (
            "submitted_at",
            "assignment_date",
            "approval_confirmation_date",
            "completion_date",
            "cancellation_date",
            "created_at",
            "updated_at",
        )
        for request in self.requests:
            for field_name in timestamp_fields:
                value = request[field_name]
                if value is not None:
                    self.assertIsNotNone(
                        value.tzinfo,
                        f"{request['request_number']} {field_name}",
                    )

            self.assertEqual(
                request["submitted_at"],
                request["created_at"],
            )
            if request["assignment_date"] is not None:
                self.assertLessEqual(
                    request["submitted_at"],
                    request["assignment_date"],
                )
            terminal_date = (
                request["completion_date"]
                or request["cancellation_date"]
            )
            if terminal_date is not None and request["assignment_date"]:
                self.assertLessEqual(
                    request["assignment_date"],
                    terminal_date,
                )
            if request["lifecycle_status"] in (
                "Submitted",
                "Assigned",
                "In Progress",
            ):
                self.assertIsNone(request["completion_date"])
                self.assertIsNone(request["cancellation_date"])

            history = _fetch_dicts(
                self.connection,
                """
                SELECT *
                FROM request_history
                WHERE request_id = ?
                ORDER BY event_at, history_id
                """,
                [request["request_id"]],
            )
            self.assertGreaterEqual(len(history), 1)
            self.assertEqual(history[0]["event_type"], "Request Created")
            event_times = [item["event_at"] for item in history]
            self.assertEqual(event_times, sorted(event_times))
            self.assertTrue(
                all(item.tzinfo is not None for item in event_times)
            )
            self.assertGreaterEqual(
                min(event_times),
                request["submitted_at"],
            )
            self.assertEqual(max(event_times), request["updated_at"])

            event_types = [item["event_type"] for item in history]
            if request["assignment_date"] is not None:
                self.assertIn("Assigned", event_types)
            if request["lifecycle_status"] == "Completed":
                self.assertEqual(event_types[-1], "Completed")
            if request["lifecycle_status"] == "Cancelled":
                self.assertEqual(event_types[-1], "Cancelled")

        for table_name, timestamp_fields_for_table in {
            "app_users": ("created_at", "updated_at"),
            "request_references": ("added_at",),
            "request_history": ("event_at",),
        }.items():
            rows = _fetch_dicts(
                self.connection,
                f"SELECT * FROM {table_name}",
            )
            for row in rows:
                for field_name in timestamp_fields_for_table:
                    self.assertIsNotNone(row[field_name].tzinfo)

    def test_only_four_tables_and_no_attention_persistence(self):
        before_counts = {
            table_name: self.connection.execute(
                f"SELECT COUNT(*) FROM {table_name}"
            ).fetchone()[0]
            for table_name in list_table_names(self.connection)
        }
        evaluate_requests_attention(
            self.requests,
            as_of=REFERENCE_DATE,
        )
        after_counts = {
            table_name: self.connection.execute(
                f"SELECT COUNT(*) FROM {table_name}"
            ).fetchone()[0]
            for table_name in list_table_names(self.connection)
        }
        self.assertEqual(
            list_table_names(self.connection),
            [
                "app_users",
                "procurement_requests",
                "request_history",
                "request_references",
            ],
        )
        self.assertEqual(before_counts, after_counts)


def configured_zone():
    from zoneinfo import ZoneInfo

    return ZoneInfo(config.APPLICATION_TIMEZONE)


def rule_codes(results):
    return [result["rule_code"] for result in results]


if __name__ == "__main__":
    unittest.main(verbosity=2)
