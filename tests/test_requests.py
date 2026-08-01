"""Officer workflow, Request List, and Request Detail verification."""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from streamlit.testing.v1 import AppTest

from src import config
from src.database import (
    ValidationError,
    add_request_reference,
    assign_request,
    connect_database,
    list_table_names,
    transition_request_status,
    update_request,
)
from src.demo_workspace import (
    DemoWorkspaceError,
    create_demo_workspace,
    reset_demo_workspace,
)
from src.queries import (
    get_dashboard_summary,
    get_enriched_request,
    list_enriched_requests,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUESTS_PAGE = PROJECT_ROOT / "views" / "requests.py"
APP_PATH = PROJECT_ROOT / "app.py"
BASELINE_PATH = PROJECT_ROOT / "database" / "procureflow_demo.duckdb"
REFERENCE_DATE = date(2026, 7, 30)
APPLICATION_ZONE = ZoneInfo(config.APPLICATION_TIMEZONE)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class OfficerWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_directory.name) / "workflow.duckdb"
        shutil.copy2(BASELINE_PATH, self.database_path)
        self.previous_database_path = os.environ.get("PROCUREFLOW_DATABASE_PATH")
        os.environ["PROCUREFLOW_DATABASE_PATH"] = str(self.database_path)

    def tearDown(self):
        if self.previous_database_path is None:
            os.environ.pop("PROCUREFLOW_DATABASE_PATH", None)
        else:
            os.environ["PROCUREFLOW_DATABASE_PATH"] = self.previous_database_path
        self.temp_directory.cleanup()

    def run_requests_page(self) -> AppTest:
        return AppTest.from_file(str(REQUESTS_PAGE), default_timeout=30).run()

    @staticmethod
    def _element_by_key(elements, key):
        return next(element for element in elements if element.key == key)

    def open_intake(self, app: AppTest) -> AppTest:
        next(button for button in app.button if button.label == "Submit request").click().run()
        return app

    def fill_valid_intake(
        self,
        app: AppTest,
        *,
        required_by_date: date = date(2026, 8, 20),
        estimated_value: float | None = 18_500.0,
    ) -> None:
        self._element_by_key(app.text_input, "requests_intake_title").input(
            "Accessibility review services"
        )
        self._element_by_key(app.text_input, "requests_intake_requestor").input(
            "Morgan Lee"
        )
        self._element_by_key(app.text_area, "requests_intake_description").input(
            "External accessibility review for the public website refresh."
        )
        self._element_by_key(app.selectbox, "requests_intake_business_unit").select(
            "Technology"
        )
        self._element_by_key(app.selectbox, "requests_intake_category").select(
            "Professional Services"
        )
        self._element_by_key(app.selectbox, "requests_intake_priority").select("High")
        self._element_by_key(app.date_input, "requests_intake_required_by").set_value(
            required_by_date
        )
        if estimated_value is not None:
            self._element_by_key(
                app.number_input,
                "requests_intake_estimated_value",
            ).set_value(estimated_value)

    def connection(self):
        return connect_database(self.database_path)

    @staticmethod
    def _request(connection, request_number: str) -> dict:
        request_id = connection.execute(
            "SELECT request_id FROM procurement_requests WHERE request_number = ?",
            [request_number],
        ).fetchone()[0]
        return get_enriched_request(
            connection,
            request_id,
            as_of=REFERENCE_DATE,
        )["request"]

    @staticmethod
    def _user_id(connection, display_name: str):
        return connection.execute(
            "SELECT user_id FROM app_users WHERE display_name = ?",
            [display_name],
        ).fetchone()[0]

    def test_request_list_default_rendering_and_opening(self):
        app = self.run_requests_page()
        self.assertEqual(list(app.exception), [])
        markdown = "\n".join(item.value for item in app.markdown)
        self.assertIn("Procurement requests", markdown)
        self.assertIn("Procurement workspace", markdown)
        self.assertIn("Showing 1–12 of 36 requests", markdown)
        self.assertIn("Unassigned", markdown)
        self.assertNotIn("assignment_overdue", markdown)
        self.assertEqual(len([button for button in app.button if button.label == "Open"]), 12)

        next(button for button in app.button if button.label == "Open").click().run()
        self.assertEqual(list(app.exception), [])
        detail_markdown = "\n".join(item.value for item in app.markdown)
        self.assertIn("Request detail", detail_markdown)
        self.assertIn("Request overview", detail_markdown)

    def test_intake_entry_fields_and_baseline_protection(self):
        baseline_hash = _sha256(BASELINE_PATH)
        os.environ.pop("PROCUREFLOW_DATABASE_PATH", None)
        try:
            app = AppTest.from_file(str(REQUESTS_PAGE), default_timeout=30).run()
            self.assertEqual(list(app.exception), [])
            self.assertTrue(any(button.label == "Submit request" for button in app.button))
            self.open_intake(app)
            self.assertEqual(list(app.exception), [])
            labels = {
                element.label
                for collection in (
                    app.selectbox,
                    app.text_input,
                    app.text_area,
                    app.date_input,
                    app.number_input,
                    app.checkbox,
                )
                for element in collection
            }
            self.assertTrue(
                {
                    "Submitted by / authorized requestor *",
                    "Request title *",
                    "Requestor name *",
                    "Business unit *",
                    "Request category *",
                    "Description *",
                    "Priority *",
                    "Required-by date *",
                    "Estimated value (CAD, optional)",
                    "Closure evidence required",
                }.issubset(labels)
            )
            create_button = next(
                button for button in app.button if button.label == "Submit request"
            )
            self.assertTrue(create_button.disabled)
            self.assertTrue(
                any(
                    button.label == "Create local demo workspace"
                    for button in app.sidebar.button
                )
            )
            self.assertIn(
                "Create a local demo workspace from the sidebar to submit this request.",
                "\n".join(item.value for item in app.info),
            )
        finally:
            os.environ["PROCUREFLOW_DATABASE_PATH"] = str(self.database_path)
        self.assertEqual(_sha256(BASELINE_PATH), baseline_hash)

    def test_valid_intake_creates_detail_history_list_and_dashboard_update(self):
        connection = self.connection()
        try:
            before_count = connection.execute(
                "SELECT COUNT(*) FROM procurement_requests"
            ).fetchone()[0]
            before_summary = get_dashboard_summary(connection, as_of=REFERENCE_DATE)
        finally:
            connection.close()

        app = self.open_intake(self.run_requests_page())
        self.fill_valid_intake(app)
        next(button for button in app.button if button.label == "Submit request").click().run()
        self.assertEqual(list(app.exception), [])
        self.assertEqual(list(app.error), [])
        self.assertIn("PF-0049 submitted successfully and awaiting assignment.", [item.value for item in app.success])
        markdown = "\n".join(item.value for item in app.markdown)
        self.assertIn("Request detail", markdown)
        self.assertIn("PF-0049 · Accessibility review services", markdown)
        self.assertIn("Unassigned", markdown)
        self.assertIn("Request PF-0049 was submitted.", markdown)

        connection = self.connection()
        try:
            created = connection.execute(
                """
                SELECT request_id, request_number, lifecycle_status,
                       procurement_owner_user_id, assignment_date, assigned_by_user_id,
                       created_by_user_id, updated_by_user_id
                FROM procurement_requests
                WHERE request_title = ?
                """,
                ["Accessibility review services"],
            ).fetchall()
            self.assertEqual(len(created), 1)
            request_id, request_number, status, owner, assignment, assigned_by, creator, updater = created[0]
            self.assertEqual(request_number, "PF-0049")
            self.assertEqual(status, "Submitted")
            self.assertIsNone(owner)
            self.assertIsNone(assignment)
            self.assertIsNone(assigned_by)
            self.assertEqual(creator, updater)
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM request_history WHERE request_id = ? AND event_type = ?",
                    [request_id, "Request Created"],
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM procurement_requests").fetchone()[0],
                before_count + 1,
            )
            after_summary = get_dashboard_summary(connection, as_of=REFERENCE_DATE)
            self.assertEqual(after_summary["total_requests"], before_summary["total_requests"] + 1)
            self.assertEqual(after_summary["open_requests"], before_summary["open_requests"] + 1)
        finally:
            connection.close()

        next(button for button in app.button if button.label == "← Back to requests").click().run()
        self._element_by_key(app.text_input, "requests_search_text").input("PF-0049").run()
        self.assertIn("PF-0049", "\n".join(item.value for item in app.markdown))

    def test_intake_validation_and_cancel_do_not_write(self):
        app = self.open_intake(self.run_requests_page())
        connection = self.connection()
        try:
            before_count = connection.execute(
                "SELECT COUNT(*) FROM procurement_requests"
            ).fetchone()[0]
        finally:
            connection.close()
        next(button for button in app.button if button.label == "Submit request").click().run()
        self.assertEqual(list(app.exception), [])
        self.assertIn("request_title is required.", [item.value for item in app.error])
        connection = self.connection()
        try:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM procurement_requests").fetchone()[0],
                before_count,
            )
        finally:
            connection.close()

        self.fill_valid_intake(app, estimated_value=-1.0)
        next(button for button in app.button if button.label == "Submit request").click().run()
        self.assertEqual(list(app.exception), [])
        self.assertIn("estimated_value cannot be negative.", [item.value for item in app.error])
        connection = self.connection()
        try:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM procurement_requests WHERE request_title = ?",
                    ["Accessibility review services"],
                ).fetchone()[0],
                0,
            )
        finally:
            connection.close()

        next(button for button in app.button if button.label == "Cancel").click().run()
        self.assertEqual(list(app.exception), [])
        self.assertIn("Procurement workspace", "\n".join(item.value for item in app.markdown))

    def test_intake_accepts_past_required_by_date(self):
        app = self.open_intake(self.run_requests_page())
        past_date = date(2026, 7, 1)
        self.fill_valid_intake(app, required_by_date=past_date, estimated_value=None)
        next(button for button in app.button if button.label == "Submit request").click().run()
        self.assertEqual(list(app.exception), [])
        self.assertEqual(list(app.error), [])
        connection = self.connection()
        try:
            self.assertEqual(
                connection.execute(
                    "SELECT required_by_date FROM procurement_requests WHERE request_title = ?",
                    ["Accessibility review services"],
                ).fetchone()[0],
                past_date,
            )
        finally:
            connection.close()

    def test_request_list_search_reference_and_empty_state(self):
        connection = self.connection()
        try:
            reference_number = connection.execute(
                "SELECT reference_number FROM request_references ORDER BY reference_number LIMIT 1"
            ).fetchone()[0]
            matches = list_enriched_requests(
                connection,
                as_of=REFERENCE_DATE,
                search_text=reference_number,
            )
            self.assertTrue(matches)
            self.assertTrue(
                any(
                    connection.execute(
                        "SELECT COUNT(*) FROM request_references WHERE request_id = ? AND reference_number = ?",
                        [request["request_id"], reference_number],
                    ).fetchone()[0]
                    for request in matches
                )
            )
        finally:
            connection.close()

        app = self.run_requests_page()
        app.sidebar.text_input[0].input("definitely-no-fictional-request").run()
        self.assertEqual(list(app.exception), [])
        self.assertIn(
            "No requests match the selected filters. Reset the filters or adjust your selections to view results.",
            [item.value for item in app.info],
        )

    def test_every_request_filter_and_reset(self):
        filter_cases = (
            (0, "Submitted"),
            (1, "Urgent"),
            (2, "Finance"),
            (3, "Technology"),
            (4, "Unassigned"),
            (5, "Assignment overdue"),
        )
        for index, selection in filter_cases:
            with self.subTest(selection=selection):
                app = self.run_requests_page()
                app.sidebar.multiselect[index].select(selection).run()
                self.assertEqual(list(app.exception), [])
                self.assertTrue(any(button.label == "Open" for button in app.button))

        app = self.run_requests_page()
        app.sidebar.checkbox[0].check().run()
        self.assertEqual(list(app.exception), [])
        app.sidebar.checkbox[1].check().run()
        self.assertEqual(list(app.exception), [])

        app = self.run_requests_page()
        app.sidebar.multiselect[0].select("Submitted").run()
        next(
            button
            for button in app.sidebar.button
            if button.label == "Reset filters"
        ).click().run()
        self.assertEqual(app.sidebar.multiselect[0].value, [])

    def test_detail_renders_all_approved_sections_and_history(self):
        app = self.run_requests_page()
        next(button for button in app.button if button.label == "Open").click().run()
        self.assertEqual(list(app.exception), [])
        markdown = "\n".join(item.value for item in app.markdown)
        for section in (
            "Request overview",
            "Ownership and lifecycle",
            "Current work",
            "Approval confirmation",
            "Related references",
            "Closure",
            "Request history",
            "Procurement workflow actions",
        ):
            self.assertIn(section, markdown)
        self.assertIn("does not make the approval decision", "\n".join(x.value for x in app.caption))
        self.assertIn("Official documents remain", "\n".join(x.value for x in app.caption))
        self.assertIn("Chronological operational events", "\n".join(x.value for x in app.caption))

    def test_assignment_start_work_current_work_approval_and_reference(self):
        connection = self.connection()
        try:
            request = self._request(connection, "PF-0004")
            manager = self._user_id(connection, "Elena Brooks")
            officer = self._user_id(connection, "Alex Morgan")

            assigned = assign_request(
                connection,
                request["request_id"],
                procurement_owner_user_id=officer,
                assigned_by_user_id=manager,
            )
            self.assertEqual(assigned["lifecycle_status"], "Assigned")
            self.assertIsNotNone(assigned["assignment_date"])

            started = transition_request_status(
                connection,
                request["request_id"],
                new_status="In Progress",
                updated_by_user_id=officer,
            )
            self.assertEqual(started["lifecycle_status"], "In Progress")

            with self.assertRaises(ValidationError):
                update_request(
                    connection,
                    request["request_id"],
                    updated_by_user_id=officer,
                    current_dependency="Budget code required",
                )

            updated = update_request(
                connection,
                request["request_id"],
                updated_by_user_id=officer,
                procurement_route="Low-Value Purchase",
                dependency_type="Required Information",
                current_dependency="Budget code required",
                dependency_owner="Finance Operations",
                next_action="Confirm the approved budget code",
                follow_up_date=date(2026, 8, 3),
                target_completion_date=date(2026, 8, 7),
                officer_note="Requestor confirmed the business requirement.",
            )
            self.assertEqual(updated["dependency_type"], "Required Information")

            approved = update_request(
                connection,
                request["request_id"],
                updated_by_user_id=officer,
                approval_required=True,
                approval_requirement="Director spending approval",
                approval_status="Confirmed",
                approval_source="Finance approval process",
                approval_reference="APR-2026-184",
                approval_confirmation_date=datetime(
                    2026, 7, 30, 10, 0, tzinfo=APPLICATION_ZONE
                ),
                approval_notes="Confirmation received from the source process.",
            )
            self.assertEqual(approved["approval_status"], "Confirmed")

            reference = add_request_reference(
                connection,
                request["request_id"],
                reference_type="Approval Record",
                reference_number="APR-2026-184",
                source_system_or_process="Finance approval process",
                reference_link="https://example.invalid/approvals/APR-2026-184",
                added_by_user_id=officer,
                note="Fictional demonstration reference.",
            )
            self.assertEqual(reference["reference_number"], "APR-2026-184")

            detail = get_enriched_request(
                connection,
                request["request_id"],
                as_of=REFERENCE_DATE,
            )
            event_types = [event["event_type"] for event in detail["history"]]
            for expected in (
                "Assigned",
                "Status Changed",
                "Dependency Updated",
                "Route Changed",
                "Approval Updated",
                "Reference Added",
            ):
                self.assertIn(expected, event_types)
            self.assertEqual(
                [event["event_at"] for event in detail["history"]],
                sorted(event["event_at"] for event in detail["history"]),
            )
        finally:
            connection.close()

    def test_completion_blocked_then_succeeds_with_closure_evidence(self):
        connection = self.connection()
        try:
            request = self._request(connection, "PF-0005")
            manager = self._user_id(connection, "Elena Brooks")
            officer = self._user_id(connection, "Alex Morgan")
            assign_request(
                connection,
                request["request_id"],
                procurement_owner_user_id=officer,
                assigned_by_user_id=manager,
            )
            transition_request_status(
                connection,
                request["request_id"],
                new_status="In Progress",
                updated_by_user_id=officer,
            )
            update_request(
                connection,
                request["request_id"],
                updated_by_user_id=officer,
                procurement_route="Competitive Procurement",
                closure_note="Replacement equipment ordered and recorded.",
            )
            with self.assertRaisesRegex(ValidationError, "closure evidence"):
                transition_request_status(
                    connection,
                    request["request_id"],
                    new_status="Completed",
                    updated_by_user_id=officer,
                )

            add_request_reference(
                connection,
                request["request_id"],
                reference_type="Purchase Order",
                reference_number="PO-2026-4401",
                source_system_or_process="Financial system",
                is_closure_evidence=True,
                added_by_user_id=officer,
            )
            update_request(
                connection,
                request["request_id"],
                updated_by_user_id=officer,
                closure_evidence_confirmed=True,
            )
            completed = transition_request_status(
                connection,
                request["request_id"],
                new_status="Completed",
                updated_by_user_id=officer,
            )
            self.assertEqual(completed["lifecycle_status"], "Completed")
            self.assertIsNotNone(completed["completion_date"])
        finally:
            connection.close()

    def test_cancellation_and_terminal_read_only_protection(self):
        connection = self.connection()
        try:
            request = self._request(connection, "PF-0001")
            actor = self._user_id(connection, "Jordan Singh")
            cancelled = transition_request_status(
                connection,
                request["request_id"],
                new_status="Cancelled",
                updated_by_user_id=actor,
                cancellation_reason="Request Withdrawn",
            )
            self.assertEqual(cancelled["cancellation_reason"], "Request Withdrawn")
            with self.assertRaisesRegex(ValidationError, "terminal"):
                update_request(
                    connection,
                    request["request_id"],
                    updated_by_user_id=actor,
                    officer_note="Should be rejected",
                )
            with self.assertRaisesRegex(ValidationError, "terminal"):
                add_request_reference(
                    connection,
                    request["request_id"],
                    reference_type="Approval Record",
                    reference_number="SHOULD-NOT-WRITE",
                    source_system_or_process="Test",
                    added_by_user_id=actor,
                )
            with self.assertRaisesRegex(ValidationError, "terminal"):
                transition_request_status(
                    connection,
                    request["request_id"],
                    new_status="Assigned",
                    updated_by_user_id=actor,
                )
        finally:
            connection.close()

    def test_dashboard_reflects_shared_database_and_attention_is_not_persisted(self):
        connection = self.connection()
        try:
            before = get_dashboard_summary(connection, as_of=REFERENCE_DATE)
            request = self._request(connection, "PF-0004")
            manager = self._user_id(connection, "Elena Brooks")
            officer = self._user_id(connection, "Alex Morgan")
            assign_request(
                connection,
                request["request_id"],
                procurement_owner_user_id=officer,
                assigned_by_user_id=manager,
            )
            after = get_dashboard_summary(connection, as_of=REFERENCE_DATE)
            self.assertEqual(after["unassigned_requests"], before["unassigned_requests"] - 1)
            self.assertEqual(after["assigned_count"], before["assigned_count"] + 1)
            self.assertEqual(after["submitted_count"], before["submitted_count"] - 1)
            self.assertEqual(list_table_names(connection), [
                "app_users",
                "procurement_requests",
                "request_history",
                "request_references",
            ])
            columns = {
                row[0]
                for table in list_table_names(connection)
                for row in connection.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_name = ?",
                    [table],
                ).fetchall()
            }
            self.assertFalse(any("attention" in column for column in columns))
        finally:
            connection.close()

        dashboard = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
        self.assertEqual(list(dashboard.exception), [])
        metrics = {metric.label: metric.value for metric in dashboard.metric}
        self.assertEqual(metrics["Unassigned requests"], "7")

    def test_safe_workspace_copy_and_reset_preserve_baseline(self):
        baseline_hash = _sha256(BASELINE_PATH)
        workspace = create_demo_workspace(
            BASELINE_PATH,
            workspace_directory=self.temp_directory.name,
            workspace_name="explicit_session.duckdb",
        )
        self.assertEqual(_sha256(workspace), baseline_hash)
        connection = connect_database(workspace)
        try:
            connection.execute(
                "UPDATE procurement_requests SET request_title = ? WHERE request_number = ?",
                ["Temporary session-only title", "PF-0001"],
            )
        finally:
            connection.close()
        self.assertNotEqual(_sha256(workspace), baseline_hash)
        reset_demo_workspace(workspace, baseline_path=BASELINE_PATH)
        self.assertEqual(_sha256(workspace), baseline_hash)
        self.assertEqual(_sha256(BASELINE_PATH), baseline_hash)
        with self.assertRaises(DemoWorkspaceError):
            reset_demo_workspace(BASELINE_PATH, baseline_path=BASELINE_PATH)

    def test_navigation_contains_only_dashboard_and_requests(self):
        source = APP_PATH.read_text(encoding="utf-8")
        self.assertEqual(source.count("st.Page("), 2)
        self.assertIn('title="Dashboard"', source)
        self.assertIn('title="Requests"', source)
        self.assertNotIn("Request Detail", source)
        self.assertFalse(any((PROJECT_ROOT / "pages").glob("*.py")))

    def test_baseline_integrity_and_exact_four_tables(self):
        baseline_hash = _sha256(BASELINE_PATH)
        connection = connect_database(BASELINE_PATH)
        try:
            self.assertEqual(list_table_names(connection), [
                "app_users",
                "procurement_requests",
                "request_history",
                "request_references",
            ])
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM procurement_requests").fetchone()[0],
                48,
            )
        finally:
            connection.close()
        self.assertEqual(_sha256(BASELINE_PATH), baseline_hash)
