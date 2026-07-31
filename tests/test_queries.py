"""Tests for the read-only ProcureFlow query and service layer."""

from __future__ import annotations

import tempfile
import unittest
from collections import Counter
from datetime import date
from pathlib import Path
from uuid import uuid4

from src import config
from src.data_generator import DEFAULT_SEED, generate_demo_data
from src.database import connect_database, list_table_names
from src.queries import (
    QueryValidationError,
    get_dashboard_summary,
    get_enriched_request,
    get_filter_options,
    get_owner_workload,
    list_active_procurement_officers,
    list_enriched_requests,
)
from src.rules import (
    RULE_CODES,
    evaluate_request_attention,
)


REFERENCE_DATE = date(2026, 7, 30)


class QueryLayerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_directory = tempfile.TemporaryDirectory()
        cls.database_path = (
            Path(cls.temp_directory.name) / "procureflow_queries.duckdb"
        )
        generate_demo_data(
            cls.database_path,
            reference_date=REFERENCE_DATE,
            seed=DEFAULT_SEED,
            reset=True,
        )
        cls.connection = connect_database(cls.database_path)
        cls.all_requests = list_enriched_requests(
            cls.connection,
            as_of=REFERENCE_DATE,
            sort_by="request_number",
            sort_direction="asc",
        )

    @classmethod
    def tearDownClass(cls):
        cls.connection.close()
        cls.temp_directory.cleanup()

    def request_by_number(self, request_number):
        return next(
            request
            for request in self.all_requests
            if request["request_number"] == request_number
        )

    def test_all_requests_and_required_enriched_fields(self):
        self.assertEqual(len(self.all_requests), 48)
        required_fields = {
            "request_id",
            "request_number",
            "request_title",
            "requestor_name",
            "business_unit",
            "request_category",
            "description",
            "estimated_value",
            "priority",
            "required_by_date",
            "submitted_at",
            "lifecycle_status",
            "procurement_owner_user_id",
            "procurement_owner_name",
            "assignment_date",
            "assigned_by_user_id",
            "assigned_by_name",
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
            "completion_date",
            "cancellation_date",
            "cancellation_reason",
            "created_at",
            "created_by_name",
            "updated_at",
            "updated_by_name",
            "reference_count",
            "closure_evidence_reference_count",
            "attention_rule_codes",
            "attention_reasons",
            "attention_count",
        }
        self.assertTrue(
            required_fields.issubset(self.all_requests[0])
        )

    def test_user_name_enrichment_is_correct(self):
        users = dict(
            self.connection.execute(
                "SELECT user_id, display_name FROM app_users"
            ).fetchall()
        )
        for request in self.all_requests:
            owner_id = request["procurement_owner_user_id"]
            expected_owner = users.get(owner_id)
            self.assertEqual(
                request["procurement_owner_name"],
                expected_owner,
            )
            self.assertEqual(
                request["assigned_by_name"],
                users.get(request["assigned_by_user_id"]),
            )
            self.assertEqual(
                request["created_by_name"],
                users[request["created_by_user_id"]],
            )
            self.assertEqual(
                request["updated_by_name"],
                users[request["updated_by_user_id"]],
            )

    def test_reference_and_closure_evidence_counts_are_correct(self):
        expected = {
            request_id: (reference_count, closure_count)
            for request_id, reference_count, closure_count in (
                self.connection.execute(
                    """
                    SELECT
                        request_id,
                        COUNT(*),
                        SUM(
                            CASE
                                WHEN is_closure_evidence THEN 1
                                ELSE 0
                            END
                        )
                    FROM request_references
                    GROUP BY request_id
                    """
                ).fetchall()
            )
        }
        for request in self.all_requests:
            reference_count, closure_count = expected.get(
                request["request_id"],
                (0, 0),
            )
            self.assertEqual(
                request["reference_count"],
                reference_count,
            )
            self.assertEqual(
                request["closure_evidence_reference_count"],
                closure_count,
            )

    def test_attention_matches_direct_rules_evaluation(self):
        for request in self.all_requests:
            direct = evaluate_request_attention(
                request,
                as_of=REFERENCE_DATE,
                procurement_owner_name=request[
                    "procurement_owner_name"
                ],
                closure_evidence_reference_count=request[
                    "closure_evidence_reference_count"
                ],
            )
            self.assertEqual(
                request["attention_rule_codes"],
                [item["rule_code"] for item in direct],
            )
            self.assertEqual(
                request["attention_reasons"],
                [item["reason"] for item in direct],
            )
            self.assertEqual(request["attention_count"], len(direct))

    def test_individual_filters_and_empty_lists(self):
        filter_cases = (
            ("lifecycle_statuses", "Completed", "lifecycle_status"),
            ("priorities", "Urgent", "priority"),
            (
                "business_units",
                "Business Operations",
                "business_unit",
            ),
            (
                "request_categories",
                "Professional Services",
                "request_category",
            ),
            (
                "procurement_routes",
                "Competitive Procurement",
                "procurement_route",
            ),
        )
        for argument, value, field_name in filter_cases:
            with self.subTest(filter=argument):
                results = list_enriched_requests(
                    self.connection,
                    as_of=REFERENCE_DATE,
                    **{argument: [value]},
                )
                self.assertGreater(len(results), 0)
                self.assertTrue(
                    all(
                        request[field_name] == value
                        for request in results
                    )
                )

        owner = next(
            request["procurement_owner_user_id"]
            for request in self.all_requests
            if request["procurement_owner_user_id"] is not None
        )
        owned = list_enriched_requests(
            self.connection,
            as_of=REFERENCE_DATE,
            procurement_owner_user_ids=[owner],
        )
        self.assertTrue(
            all(
                request["procurement_owner_user_id"] == owner
                for request in owned
            )
        )

        unfiltered = list_enriched_requests(
            self.connection,
            as_of=REFERENCE_DATE,
            lifecycle_statuses=[],
            priorities=[],
            business_units=[],
            request_categories=[],
            procurement_owner_user_ids=[],
            procurement_routes=[],
            attention_rule_codes=[],
        )
        self.assertEqual(len(unfiltered), 48)

        open_only = list_enriched_requests(
            self.connection,
            as_of=REFERENCE_DATE,
            include_completed=False,
            include_cancelled=False,
        )
        self.assertEqual(len(open_only), 36)

    def test_filter_or_and_logic(self):
        status_or = list_enriched_requests(
            self.connection,
            as_of=REFERENCE_DATE,
            lifecycle_statuses=["Submitted", "Cancelled"],
        )
        self.assertEqual(len(status_or), 12)
        self.assertEqual(
            {request["lifecycle_status"] for request in status_or},
            {"Submitted", "Cancelled"},
        )

        expected = [
            request
            for request in self.all_requests
            if request["lifecycle_status"] in ("Assigned", "In Progress")
            and request["priority"] in ("High", "Urgent")
            and request["business_unit"] == "Technology"
        ]
        combined = list_enriched_requests(
            self.connection,
            as_of=REFERENCE_DATE,
            lifecycle_statuses=["Assigned", "In Progress"],
            priorities=["High", "Urgent"],
            business_units=["Technology"],
        )
        self.assertEqual(
            {request["request_id"] for request in combined},
            {request["request_id"] for request in expected},
        )

    def test_attention_rule_filter_uses_or_logic(self):
        selected_codes = ("follow_up_overdue", "assignment_overdue")
        expected_ids = {
            request["request_id"]
            for request in self.all_requests
            if set(selected_codes).intersection(
                request["attention_rule_codes"]
            )
        }
        results = list_enriched_requests(
            self.connection,
            as_of=REFERENCE_DATE,
            attention_rule_codes=selected_codes,
        )
        self.assertEqual(
            {request["request_id"] for request in results},
            expected_ids,
        )

    def test_search_is_case_insensitive_and_blank_is_ignored(self):
        searches = (
            ("pf-0001", "request_number"),
            ("CYBERSECURITY ASSESSMENT", "request_title"),
            (
                self.all_requests[4]["requestor_name"].swapcase(),
                "requestor_name",
            ),
            ("planned equipment requirement", "description"),
            ("BUSINESS SPECIFICATIONS", "current_dependency"),
            ("finance operations", "dependency_owner"),
            ("SIGNED AGREEMENT", "next_action"),
            ("apr-2026-", "approval_reference"),
        )
        for search_text, expected_field in searches:
            with self.subTest(field=expected_field):
                results = list_enriched_requests(
                    self.connection,
                    as_of=REFERENCE_DATE,
                    search_text=search_text,
                )
                self.assertGreater(len(results), 0)

        self.assertEqual(
            len(
                list_enriched_requests(
                    self.connection,
                    as_of=REFERENCE_DATE,
                    search_text="   ",
                )
            ),
            48,
        )
        self.assertEqual(
            list_enriched_requests(
                self.connection,
                as_of=REFERENCE_DATE,
                search_text="%' OR 1=1 --",
            ),
            [],
        )

    def test_sort_allowlist_directions_and_stable_secondary_sort(self):
        ascending = list_enriched_requests(
            self.connection,
            as_of=REFERENCE_DATE,
            sort_by="request_number",
            sort_direction="asc",
        )
        descending = list_enriched_requests(
            self.connection,
            as_of=REFERENCE_DATE,
            sort_by="request_number",
            sort_direction="desc",
        )
        ascending_numbers = [
            request["request_number"] for request in ascending
        ]
        self.assertEqual(ascending_numbers, sorted(ascending_numbers))
        self.assertEqual(
            [request["request_number"] for request in descending],
            list(reversed(ascending_numbers)),
        )

        by_priority = list_enriched_requests(
            self.connection,
            as_of=REFERENCE_DATE,
            sort_by="priority",
            sort_direction="asc",
        )
        for priority in config.PRIORITIES:
            numbers = [
                request["request_number"]
                for request in by_priority
                if request["priority"] == priority
            ]
            self.assertEqual(numbers, sorted(numbers))

        with self.assertRaises(QueryValidationError):
            list_enriched_requests(
                self.connection,
                as_of=REFERENCE_DATE,
                sort_by="description; DROP TABLE app_users",
            )
        with self.assertRaises(QueryValidationError):
            list_enriched_requests(
                self.connection,
                as_of=REFERENCE_DATE,
                sort_direction="sideways",
            )

    def test_limit_and_offset_pagination(self):
        full = list_enriched_requests(
            self.connection,
            as_of=REFERENCE_DATE,
            sort_by="request_number",
            sort_direction="asc",
        )
        page = list_enriched_requests(
            self.connection,
            as_of=REFERENCE_DATE,
            sort_by="request_number",
            sort_direction="asc",
            limit=10,
            offset=5,
        )
        self.assertEqual(
            [request["request_id"] for request in page],
            [request["request_id"] for request in full[5:15]],
        )
        self.assertEqual(
            list_enriched_requests(
                self.connection,
                as_of=REFERENCE_DATE,
                limit=0,
            ),
            [],
        )
        with self.assertRaises(QueryValidationError):
            list_enriched_requests(
                self.connection,
                as_of=REFERENCE_DATE,
                limit=-1,
            )

    def test_single_request_detail_and_missing_behavior(self):
        request = self.request_by_number("PF-0009")
        detail = get_enriched_request(
            self.connection,
            request["request_id"],
            as_of=REFERENCE_DATE,
        )
        self.assertIsNotNone(detail)
        self.assertEqual(
            set(detail),
            {
                "request",
                "references",
                "history",
                "attention_results",
            },
        )
        self.assertEqual(
            detail["request"]["request_number"],
            "PF-0009",
        )
        self.assertEqual(len(detail["references"]), 2)
        self.assertGreaterEqual(len(detail["history"]), 1)
        self.assertEqual(
            [item["added_at"] for item in detail["references"]],
            sorted(
                item["added_at"] for item in detail["references"]
            ),
        )
        self.assertEqual(
            [item["event_at"] for item in detail["history"]],
            sorted(item["event_at"] for item in detail["history"]),
        )
        self.assertEqual(
            detail["request"]["attention_rule_codes"],
            [
                item["rule_code"]
                for item in detail["attention_results"]
            ],
        )
        self.assertNotIn("references", detail["request"])
        self.assertNotIn("history", detail["request"])

        self.assertIsNone(
            get_enriched_request(
                self.connection,
                uuid4(),
                as_of=REFERENCE_DATE,
            )
        )

    def test_dashboard_summary_matches_dataset_and_direct_rules(self):
        summary = get_dashboard_summary(
            self.connection,
            as_of=REFERENCE_DATE,
        )
        self.assertEqual(summary["total_requests"], 48)
        self.assertEqual(summary["open_requests"], 36)
        self.assertEqual(summary["submitted_count"], 8)
        self.assertEqual(summary["assigned_count"], 8)
        self.assertEqual(summary["in_progress_count"], 20)
        self.assertEqual(summary["completed_count"], 8)
        self.assertEqual(summary["cancelled_count"], 4)
        self.assertEqual(
            summary["counts_by_lifecycle_status"],
            {
                "Submitted": 8,
                "Assigned": 8,
                "In Progress": 20,
                "Completed": 8,
                "Cancelled": 4,
            },
        )

        direct_attention_counts = Counter(
            code
            for request in self.all_requests
            for code in request["attention_rule_codes"]
        )
        direct_attention_requests = sum(
            request["attention_count"] > 0
            for request in self.all_requests
        )
        self.assertEqual(
            summary["requests_requiring_attention"],
            direct_attention_requests,
        )
        self.assertEqual(
            summary["total_attention_results"],
            sum(direct_attention_counts.values()),
        )
        self.assertEqual(
            summary["attention_counts_by_rule"],
            {
                rule_code: direct_attention_counts[rule_code]
                for rule_code in RULE_CODES
            },
        )
        self.assertLess(
            summary["requests_requiring_attention"],
            summary["total_attention_results"],
        )

        filtered = get_dashboard_summary(
            self.connection,
            as_of=REFERENCE_DATE,
            filters={"lifecycle_statuses": ["Completed"]},
        )
        self.assertEqual(filtered["total_requests"], 8)
        self.assertEqual(filtered["completed_count"], 8)

    def test_owner_workload_excludes_terminal_and_includes_unassigned(self):
        workload = get_owner_workload(
            self.connection,
            as_of=REFERENCE_DATE,
        )
        self.assertEqual(len(workload), 4)
        self.assertEqual(
            sum(row["open_request_count"] for row in workload),
            36,
        )
        unassigned = next(
            row for row in workload if row["owner_user_id"] is None
        )
        self.assertEqual(unassigned["owner_name"], "Unassigned")
        self.assertEqual(unassigned["open_request_count"], 8)
        self.assertEqual(unassigned["assigned_count"], 0)
        self.assertEqual(unassigned["in_progress_count"], 0)

        for row in workload:
            expected = [
                request
                for request in self.all_requests
                if request["lifecycle_status"]
                in ("Submitted", "Assigned", "In Progress")
                and request["procurement_owner_user_id"]
                == row["owner_user_id"]
            ]
            self.assertEqual(
                row["open_request_count"],
                len(expected),
            )
            self.assertEqual(
                row["attention_request_count"],
                sum(item["attention_count"] > 0 for item in expected),
            )

    def test_value_totals_ignore_nulls(self):
        summary = get_dashboard_summary(
            self.connection,
            as_of=REFERENCE_DATE,
        )
        expected_total = self.connection.execute(
            "SELECT SUM(estimated_value) FROM procurement_requests"
        ).fetchone()[0]
        expected_open = self.connection.execute(
            """
            SELECT SUM(estimated_value)
            FROM procurement_requests
            WHERE lifecycle_status IN (?, ?, ?)
            """,
            ["Submitted", "Assigned", "In Progress"],
        ).fetchone()[0]
        self.assertEqual(summary["total_estimated_value"], expected_total)
        self.assertEqual(
            summary["total_open_estimated_value"],
            expected_open,
        )

    def test_filter_options_use_config_and_active_officers(self):
        options = get_filter_options(self.connection)
        self.assertEqual(
            options["lifecycle_statuses"],
            list(config.LIFECYCLE_STATUSES),
        )
        self.assertEqual(options["priorities"], list(config.PRIORITIES))
        self.assertEqual(
            options["business_units"],
            list(config.BUSINESS_UNITS),
        )
        self.assertEqual(
            options["request_categories"],
            list(config.REQUEST_CATEGORIES),
        )
        self.assertEqual(
            options["procurement_routes"],
            list(config.PROCUREMENT_ROUTES),
        )
        self.assertEqual(
            options["attention_rule_codes"],
            list(RULE_CODES),
        )
        officers = list_active_procurement_officers(self.connection)
        self.assertEqual(len(officers), 3)
        self.assertEqual(options["procurement_officers"], officers)

    def test_query_functions_do_not_write_or_persist_attention(self):
        table_names_before = list_table_names(self.connection)
        row_counts_before = {
            table_name: self.connection.execute(
                f"SELECT COUNT(*) FROM {table_name}"
            ).fetchone()[0]
            for table_name in table_names_before
        }

        list_enriched_requests(
            self.connection,
            as_of=REFERENCE_DATE,
            search_text="network",
        )
        get_dashboard_summary(
            self.connection,
            as_of=REFERENCE_DATE,
        )
        get_owner_workload(
            self.connection,
            as_of=REFERENCE_DATE,
        )
        get_filter_options(self.connection)
        get_enriched_request(
            self.connection,
            self.all_requests[0]["request_id"],
            as_of=REFERENCE_DATE,
        )

        table_names_after = list_table_names(self.connection)
        row_counts_after = {
            table_name: self.connection.execute(
                f"SELECT COUNT(*) FROM {table_name}"
            ).fetchone()[0]
            for table_name in table_names_after
        }
        self.assertEqual(
            table_names_after,
            [
                "app_users",
                "procurement_requests",
                "request_history",
                "request_references",
            ],
        )
        self.assertEqual(table_names_before, table_names_after)
        self.assertEqual(row_counts_before, row_counts_after)


if __name__ == "__main__":
    unittest.main(verbosity=2)
