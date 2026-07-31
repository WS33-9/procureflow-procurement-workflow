"""Focused tests for the pure requests-requiring-attention rules engine."""

from __future__ import annotations

import copy
import unittest
from datetime import date, datetime, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from src.rules import (
    ASSIGNMENT_OVERDUE,
    COMPLETED_MISSING_CLOSURE_EVIDENCE,
    FOLLOW_UP_OVERDUE,
    HIGH_PRIORITY_OVERDUE_DEPENDENCY,
    NO_RECENT_UPDATE,
    REQUIRED_APPROVAL_NOT_CONFIRMED,
    REQUIRED_INFORMATION_OUTSTANDING,
    TARGET_COMPLETION_MISSED,
    AttentionRuleError,
    evaluate_request_attention,
    evaluate_requests_attention,
)


TORONTO = ZoneInfo("America/Toronto")
AS_OF = date(2026, 7, 15)


def request_record(**overrides):
    record = {
        "request_id": UUID("11111111-1111-1111-1111-111111111111"),
        "request_number": "PF-0042",
        "request_title": "Network equipment refresh",
        "lifecycle_status": "In Progress",
        "priority": "Medium",
        "submitted_at": datetime(2026, 7, 13, 9, 0, tzinfo=TORONTO),
        "updated_at": datetime(2026, 7, 14, 10, 0, tzinfo=TORONTO),
        "current_dependency": None,
        "dependency_type": None,
        "dependency_owner": None,
        "next_action": None,
        "follow_up_date": None,
        "target_completion_date": None,
        "approval_required": False,
        "approval_status": "Not Required",
        "closure_evidence_required": False,
        "closure_evidence_confirmed": False,
    }
    record.update(overrides)
    return record


def rule_codes(results):
    return [result["rule_code"] for result in results]


class AttentionRulesTest(unittest.TestCase):
    def evaluate(self, request, **kwargs):
        return evaluate_request_attention(
            request,
            as_of=kwargs.pop("as_of", AS_OF),
            procurement_owner_name=kwargs.pop(
                "procurement_owner_name",
                "Alex Morgan",
            ),
            **kwargs,
        )

    def test_assignment_overdue_triggers_and_result_shape(self):
        results = self.evaluate(
            request_record(
                lifecycle_status="Submitted",
                submitted_at=datetime(
                    2026,
                    7,
                    13,
                    9,
                    0,
                    tzinfo=TORONTO,
                ),
            )
        )
        self.assertEqual(rule_codes(results), [ASSIGNMENT_OVERDUE])
        self.assertEqual(
            set(results[0]),
            {
                "rule_code",
                "reason",
                "request_id",
                "request_number",
                "request_title",
                "lifecycle_status",
                "procurement_owner_name",
                "dependency_owner",
                "next_action",
                "relevant_date",
                "days_outstanding",
                "priority",
            },
        )
        self.assertEqual(results[0]["relevant_date"], date(2026, 7, 13))
        self.assertEqual(results[0]["days_outstanding"], 1)

    def test_assignment_overdue_weekday_boundaries(self):
        monday_submission = request_record(
            lifecycle_status="Submitted",
            submitted_at=datetime(
                2026,
                7,
                13,
                9,
                0,
                tzinfo=TORONTO,
            ),
            updated_at=datetime(
                2026,
                7,
                13,
                9,
                0,
                tzinfo=TORONTO,
            ),
        )
        self.assertNotIn(
            ASSIGNMENT_OVERDUE,
            rule_codes(
                self.evaluate(
                    monday_submission,
                    as_of=date(2026, 7, 14),
                )
            ),
        )
        self.assertIn(
            ASSIGNMENT_OVERDUE,
            rule_codes(
                self.evaluate(
                    monday_submission,
                    as_of=date(2026, 7, 15),
                )
            ),
        )

    def test_assignment_overdue_weekend_boundaries(self):
        friday_submission = request_record(
            lifecycle_status="Submitted",
            submitted_at=datetime(
                2026,
                7,
                10,
                16,
                0,
                tzinfo=TORONTO,
            ),
            updated_at=datetime(
                2026,
                7,
                10,
                16,
                0,
                tzinfo=TORONTO,
            ),
        )
        self.assertNotIn(
            ASSIGNMENT_OVERDUE,
            rule_codes(
                self.evaluate(
                    friday_submission,
                    as_of=date(2026, 7, 13),
                )
            ),
        )
        self.assertIn(
            ASSIGNMENT_OVERDUE,
            rule_codes(
                self.evaluate(
                    friday_submission,
                    as_of=date(2026, 7, 14),
                )
            ),
        )

    def test_assignment_not_triggered_for_non_submitted_request(self):
        results = self.evaluate(
            request_record(
                lifecycle_status="Assigned",
                submitted_at=datetime(
                    2026,
                    7,
                    1,
                    9,
                    0,
                    tzinfo=TORONTO,
                ),
            )
        )
        self.assertNotIn(ASSIGNMENT_OVERDUE, rule_codes(results))

    def test_follow_up_overdue_and_due_today_boundaries(self):
        overdue = request_record(
            current_dependency="Supplier response pending",
            dependency_type="Supplier Response",
            follow_up_date=date(2026, 7, 14),
        )
        due_today = request_record(
            current_dependency="Supplier response pending",
            dependency_type="Supplier Response",
            follow_up_date=AS_OF,
        )
        results = self.evaluate(overdue)
        self.assertIn(FOLLOW_UP_OVERDUE, rule_codes(results))
        follow_up_result = next(
            item
            for item in results
            if item["rule_code"] == FOLLOW_UP_OVERDUE
        )
        self.assertEqual(follow_up_result["days_outstanding"], 1)
        self.assertNotIn(
            FOLLOW_UP_OVERDUE,
            rule_codes(self.evaluate(due_today)),
        )

    def test_missing_follow_up_date_is_not_overdue(self):
        results = self.evaluate(
            request_record(current_dependency="Supplier response pending")
        )
        self.assertNotIn(FOLLOW_UP_OVERDUE, rule_codes(results))
        self.assertNotIn(
            HIGH_PRIORITY_OVERDUE_DEPENDENCY,
            rule_codes(results),
        )

    def test_target_completion_missed_and_due_today_boundaries(self):
        missed = self.evaluate(
            request_record(target_completion_date=date(2026, 7, 14))
        )
        due_today = self.evaluate(
            request_record(target_completion_date=AS_OF)
        )
        self.assertIn(TARGET_COMPLETION_MISSED, rule_codes(missed))
        target_result = next(
            item
            for item in missed
            if item["rule_code"] == TARGET_COMPLETION_MISSED
        )
        self.assertEqual(target_result["days_outstanding"], 1)
        self.assertNotIn(
            TARGET_COMPLETION_MISSED,
            rule_codes(due_today),
        )

    def test_required_information_outstanding_does_not_need_overdue_date(self):
        results = self.evaluate(
            request_record(
                current_dependency="Missing technical specifications",
                dependency_type="Required Information",
                follow_up_date=date(2026, 7, 20),
            )
        )
        self.assertIn(
            REQUIRED_INFORMATION_OUTSTANDING,
            rule_codes(results),
        )
        self.assertNotIn(FOLLOW_UP_OVERDUE, rule_codes(results))

    def test_required_information_absence_does_not_trigger(self):
        no_dependency = self.evaluate(
            request_record(dependency_type="Required Information")
        )
        different_type = self.evaluate(
            request_record(
                current_dependency="Awaiting supplier",
                dependency_type="Supplier Response",
            )
        )
        self.assertNotIn(
            REQUIRED_INFORMATION_OUTSTANDING,
            rule_codes(no_dependency),
        )
        self.assertNotIn(
            REQUIRED_INFORMATION_OUTSTANDING,
            rule_codes(different_type),
        )

    def test_required_approval_not_confirmed_and_confirmed_boundaries(self):
        not_confirmed = self.evaluate(
            request_record(
                approval_required=True,
                approval_status="Not Confirmed",
            )
        )
        confirmed = self.evaluate(
            request_record(
                approval_required=True,
                approval_status="Confirmed",
            )
        )
        self.assertIn(
            REQUIRED_APPROVAL_NOT_CONFIRMED,
            rule_codes(not_confirmed),
        )
        self.assertNotIn(
            REQUIRED_APPROVAL_NOT_CONFIRMED,
            rule_codes(confirmed),
        )

    def test_no_recent_update_six_and_seven_day_boundary(self):
        six_days = self.evaluate(
            request_record(
                updated_at=datetime(
                    2026,
                    7,
                    9,
                    23,
                    30,
                    tzinfo=TORONTO,
                )
            )
        )
        seven_days = self.evaluate(
            request_record(
                updated_at=datetime(
                    2026,
                    7,
                    8,
                    23,
                    30,
                    tzinfo=TORONTO,
                )
            )
        )
        self.assertNotIn(NO_RECENT_UPDATE, rule_codes(six_days))
        self.assertIn(NO_RECENT_UPDATE, rule_codes(seven_days))
        stale_result = next(
            item
            for item in seven_days
            if item["rule_code"] == NO_RECENT_UPDATE
        )
        self.assertEqual(stale_result["days_outstanding"], 7)

    def test_no_recent_update_not_triggered_for_fresh_request(self):
        results = self.evaluate(
            request_record(
                updated_at=datetime(
                    2026,
                    7,
                    14,
                    8,
                    0,
                    tzinfo=TORONTO,
                )
            )
        )
        self.assertNotIn(NO_RECENT_UPDATE, rule_codes(results))

    def test_high_and_urgent_qualify_but_medium_does_not(self):
        common = {
            "current_dependency": "Supplier response pending",
            "dependency_type": "Supplier Response",
            "follow_up_date": date(2026, 7, 14),
        }
        for priority in ("High", "Urgent"):
            with self.subTest(priority=priority):
                results = self.evaluate(
                    request_record(priority=priority, **common)
                )
                self.assertIn(
                    HIGH_PRIORITY_OVERDUE_DEPENDENCY,
                    rule_codes(results),
                )

        medium_results = self.evaluate(
            request_record(priority="Medium", **common)
        )
        self.assertNotIn(
            HIGH_PRIORITY_OVERDUE_DEPENDENCY,
            rule_codes(medium_results),
        )

    def test_follow_up_and_high_priority_rules_can_overlap(self):
        results = self.evaluate(
            request_record(
                priority="Urgent",
                current_dependency="Supplier response pending",
                dependency_type="Supplier Response",
                follow_up_date=date(2026, 7, 12),
            )
        )
        self.assertIn(FOLLOW_UP_OVERDUE, rule_codes(results))
        self.assertIn(
            HIGH_PRIORITY_OVERDUE_DEPENDENCY,
            rule_codes(results),
        )

    def test_completed_request_is_excluded_from_open_work_rules(self):
        results = self.evaluate(
            request_record(
                lifecycle_status="Completed",
                priority="Urgent",
                current_dependency="Old dependency",
                dependency_type="Required Information",
                follow_up_date=date(2026, 7, 1),
                target_completion_date=date(2026, 7, 1),
                approval_required=True,
                approval_status="Not Confirmed",
                updated_at=datetime(
                    2026,
                    7,
                    1,
                    9,
                    0,
                    tzinfo=TORONTO,
                ),
            ),
            closure_evidence_reference_count=1,
        )
        self.assertEqual(results, [])

    def test_cancelled_request_triggers_no_rules(self):
        results = self.evaluate(
            request_record(
                lifecycle_status="Cancelled",
                priority="Urgent",
                current_dependency="Old dependency",
                dependency_type="Required Information",
                follow_up_date=date(2026, 7, 1),
                target_completion_date=date(2026, 7, 1),
                approval_required=True,
                approval_status="Not Confirmed",
                closure_evidence_required=True,
                updated_at=datetime(
                    2026,
                    7,
                    1,
                    9,
                    0,
                    tzinfo=TORONTO,
                ),
            )
        )
        self.assertEqual(results, [])

    def test_closure_safeguard_when_confirmation_is_missing(self):
        results = self.evaluate(
            request_record(
                lifecycle_status="Completed",
                closure_evidence_required=True,
                closure_evidence_confirmed=False,
            ),
            closure_evidence_reference_count=1,
        )
        self.assertEqual(
            rule_codes(results),
            [COMPLETED_MISSING_CLOSURE_EVIDENCE],
        )

    def test_closure_safeguard_when_evidence_reference_is_missing(self):
        results = self.evaluate(
            request_record(
                lifecycle_status="Completed",
                closure_evidence_required=True,
                closure_evidence_confirmed=True,
            ),
            closure_evidence_reference_count=0,
        )
        self.assertEqual(
            rule_codes(results),
            [COMPLETED_MISSING_CLOSURE_EVIDENCE],
        )

    def test_properly_completed_request_does_not_trigger_safeguard(self):
        results = self.evaluate(
            request_record(
                lifecycle_status="Completed",
                closure_evidence_required=True,
                closure_evidence_confirmed=True,
            ),
            closure_evidence_reference_count=1,
        )
        self.assertEqual(results, [])

    def test_naive_datetimes_are_rejected(self):
        with self.assertRaisesRegex(
            AttentionRuleError,
            "as_of must be timezone-aware",
        ):
            self.evaluate(
                request_record(),
                as_of=datetime(2026, 7, 15, 9, 0),
            )

        with self.assertRaisesRegex(
            AttentionRuleError,
            "updated_at must be timezone-aware",
        ):
            self.evaluate(
                request_record(
                    updated_at=datetime(2026, 7, 14, 9, 0)
                )
            )

    def test_timezone_aware_datetimes_are_normalized_to_toronto(self):
        as_of_utc = datetime(
            2026,
            7,
            16,
            2,
            0,
            tzinfo=timezone.utc,
        )
        results = self.evaluate(
            request_record(
                current_dependency="Supplier response pending",
                follow_up_date=date(2026, 7, 15),
            ),
            as_of=as_of_utc,
        )
        self.assertNotIn(FOLLOW_UP_OVERDUE, rule_codes(results))

    def test_batch_helper_combines_enriched_results(self):
        requests = [
            request_record(
                request_number="PF-0042",
                lifecycle_status="Submitted",
                submitted_at=datetime(
                    2026,
                    7,
                    13,
                    9,
                    0,
                    tzinfo=TORONTO,
                ),
                procurement_owner_name=None,
            ),
            request_record(
                request_id=UUID(
                    "22222222-2222-2222-2222-222222222222"
                ),
                request_number="PF-0043",
                approval_required=True,
                approval_status="Not Confirmed",
                procurement_owner_name="Alex Morgan",
            ),
        ]
        results = evaluate_requests_attention(requests, as_of=AS_OF)
        self.assertEqual(
            rule_codes(results),
            [ASSIGNMENT_OVERDUE, REQUIRED_APPROVAL_NOT_CONFIRMED],
        )
        self.assertEqual(
            results[1]["procurement_owner_name"],
            "Alex Morgan",
        )

    def test_evaluation_is_pure_and_results_are_not_persisted(self):
        request = request_record(
            priority="High",
            current_dependency="Supplier response pending",
            dependency_type="Supplier Response",
            follow_up_date=date(2026, 7, 14),
        )
        original = copy.deepcopy(request)

        first_results = self.evaluate(request)
        first_results[0]["reason"] = "Caller-local change"
        second_results = self.evaluate(request)

        self.assertEqual(request, original)
        self.assertNotEqual(
            first_results[0]["reason"],
            second_results[0]["reason"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
