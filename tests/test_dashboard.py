"""Streamlit AppTest coverage for the ProcureFlow Dashboard phase."""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from streamlit.testing.v1 import AppTest

from src import config
from src.database import (
    connect_database,
    initialize_database,
    list_table_names,
)
from src.queries import get_dashboard_summary
from src.rules import RULE_CODES
from src.ui import (
    attention_chart,
    category_chart,
    format_cad_compact,
    lifecycle_chart,
    owner_workload_chart,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "app.py"
DEMO_DATABASE_PATH = (
    PROJECT_ROOT / "database" / "procureflow_demo.duckdb"
)
REFERENCE_DATE = date(2026, 7, 30)


class DashboardAppTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_directory = tempfile.TemporaryDirectory()
        cls.test_database_path = (
            Path(cls.temp_directory.name) / "dashboard_test.duckdb"
        )
        shutil.copy2(DEMO_DATABASE_PATH, cls.test_database_path)

    @classmethod
    def tearDownClass(cls):
        cls.temp_directory.cleanup()

    def setUp(self):
        self.previous_database_path = os.environ.get(
            "PROCUREFLOW_DATABASE_PATH"
        )
        os.environ["PROCUREFLOW_DATABASE_PATH"] = str(
            self.test_database_path
        )

    def tearDown(self):
        if self.previous_database_path is None:
            os.environ.pop("PROCUREFLOW_DATABASE_PATH", None)
        else:
            os.environ[
                "PROCUREFLOW_DATABASE_PATH"
            ] = self.previous_database_path

    def run_app(self):
        return AppTest.from_file(
            str(APP_PATH),
            default_timeout=30,
        ).run()

    @staticmethod
    def metric_values(app):
        return {metric.label: metric.value for metric in app.metric}

    def test_application_imports_and_dashboard_is_default_page(self):
        app = self.run_app()
        self.assertEqual(list(app.exception), [])
        markdown = "\n".join(item.value for item in app.markdown)
        self.assertIn("ProcureFlow", markdown)
        self.assertIn(
            "Enterprise procurement workflow implementation case",
            markdown,
        )
        self.assertIn("Synthetic demo data", markdown)
        self.assertIn("Dashboard preview", markdown)
        self.assertIn(
            "Demo data snapshot · July 30, 2026",
            markdown,
        )
        self.assertIn("Implementation boundary", markdown)
        self.assertIn("Implementation context", markdown)
        self.assertIn("pf-attention-table", markdown)
        self.assertNotIn("assignment_overdue", markdown)
        self.assertEqual(len(app.get("vega_lite_chart")), 4)
        self.assertEqual(len(app.dataframe), 0)

        source = APP_PATH.read_text(encoding="utf-8")
        self.assertIn("default=True", source)
        self.assertEqual(source.count("st.Page("), 2)
        self.assertIn('title="Requests"', source)
        self.assertNotIn("3_Request_Detail", source)

    def test_demo_database_has_four_tables_and_approved_counts(self):
        connection = connect_database(self.test_database_path)
        try:
            self.assertEqual(
                list_table_names(connection),
                [
                    "app_users",
                    "procurement_requests",
                    "request_history",
                    "request_references",
                ],
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM app_users"
                ).fetchone()[0],
                6,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM procurement_requests"
                ).fetchone()[0],
                48,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM request_references"
                ).fetchone()[0],
                15,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM request_history"
                ).fetchone()[0],
                243,
            )
        finally:
            connection.close()

    def test_unfiltered_kpis_are_exact(self):
        app = self.run_app()
        self.assertEqual(
            self.metric_values(app),
            {
                "Open requests": "36",
                "Requests requiring attention": "25",
                "Unassigned requests": "8",
                "High-priority requests requiring attention": "10",
                "Overdue follow-ups": "9",
                "Missed target dates": "4",
                "Approvals not confirmed": "9",
                "Open estimated value": "CAD 1.58M",
            },
        )
        captions = "\n".join(item.value for item in app.caption)
        self.assertIn(
            "25 requests require attention, producing 40 attention conditions",
            captions,
        )
        self.assertEqual(
            captions.count(
                "25 requests require attention, producing 40 attention "
                "conditions"
            ),
            1,
        )
        self.assertEqual(format_cad_compact(1_582_250), "CAD 1.58M")

    def test_all_four_charts_receive_expected_data(self):
        connection = connect_database(self.test_database_path)
        try:
            summary = get_dashboard_summary(
                connection,
                as_of=REFERENCE_DATE,
            )
        finally:
            connection.close()

        lifecycle_values = lifecycle_chart(
            summary["counts_by_lifecycle_status"]
        ).to_dict()["data"]["values"]
        self.assertEqual(
            lifecycle_values,
            [
                {"Status": "Submitted", "Requests": 8},
                {"Status": "Assigned", "Requests": 8},
                {"Status": "In Progress", "Requests": 20},
                {"Status": "Completed", "Requests": 8},
                {"Status": "Cancelled", "Requests": 4},
            ],
        )
        lifecycle_spec = lifecycle_chart(
            summary["counts_by_lifecycle_status"]
        ).to_dict()
        self.assertFalse(
            lifecycle_spec["layer"][0]["encoding"]["x"]["axis"][
                "labelOverlap"
            ]
        )

        attention_values = attention_chart(
            summary["attention_counts_by_rule"]
        ).to_dict()["data"]["values"]
        self.assertEqual(len(attention_values), len(RULE_CODES))
        self.assertEqual(
            [item["Results"] for item in attention_values],
            [9, 9, 5, 5, 4, 4, 3, 1],
        )
        self.assertTrue(
            all(
                item["Attention condition"] not in RULE_CODES
                for item in attention_values
            )
        )
        self.assertEqual(
            attention_values[-1]["Condition type"],
            "Data-quality safeguard",
        )
        self.assertEqual(
            attention_values[-1]["Attention condition"],
            "Completed request missing closure evidence",
        )

        owner_values = owner_workload_chart(
            summary["owner_workload"]
        ).to_dict()["data"]["values"]
        self.assertEqual(len(owner_values), 8)
        self.assertEqual(
            {item["Owner"] for item in owner_values},
            {"Alex Morgan", "Casey Reed", "Taylor Brooks", "Unassigned"},
        )

        category_values = category_chart(
            summary["counts_by_request_category"]
        ).to_dict()["data"]["values"]
        self.assertEqual(len(category_values), len(config.REQUEST_CATEGORIES))
        self.assertEqual(
            {item["Request category"] for item in category_values},
            set(config.REQUEST_CATEGORIES),
        )
        self.assertEqual(
            [item["Requests"] for item in category_values],
            sorted(
                [item["Requests"] for item in category_values],
                reverse=True,
            ),
        )

    def test_filter_change_updates_dashboard_and_reset_restores_it(self):
        app = self.run_app()
        app.sidebar.multiselect[0].select("Submitted").run()
        filtered_metrics = self.metric_values(app)
        self.assertEqual(filtered_metrics["Open requests"], "8")
        self.assertEqual(
            filtered_metrics["Requests requiring attention"],
            "5",
        )
        self.assertEqual(
            filtered_metrics["Open estimated value"],
            "CAD 144.2K",
        )
        self.assertEqual(len(app.get("vega_lite_chart")), 4)

        app.sidebar.button[0].click().run()
        self.assertEqual(
            self.metric_values(app)["Open requests"],
            "36",
        )
        self.assertEqual(app.sidebar.multiselect[0].value, [])

    def test_each_dashboard_filter_remains_operational(self):
        filter_cases = (
            (0, "Submitted"),
            (1, "High"),
            (2, "Finance"),
            (3, "Technology"),
            (4, "Alex Morgan"),
        )
        for index, selection in filter_cases:
            with self.subTest(selection=selection):
                app = self.run_app()
                app.sidebar.multiselect[index].select(selection).run()
                self.assertEqual(list(app.exception), [])

        app = self.run_app()
        app.sidebar.checkbox[0].uncheck().run()
        self.assertEqual(list(app.exception), [])
        app.sidebar.checkbox[1].uncheck().run()
        self.assertEqual(list(app.exception), [])

    def test_typography_palette_and_management_copy_are_controlled(self):
        stylesheet = (
            PROJECT_ROOT / "assets" / "styles.css"
        ).read_text(encoding="utf-8")
        self.assertIn(
            'Inter, Aptos, "Segoe UI", system-ui, -apple-system, '
            "BlinkMacSystemFont",
            stylesheet,
        )
        self.assertIn("--pf-teal: #167a72", stylesheet)
        self.assertIn("--pf-amber: #b7791f", stylesheet)
        self.assertIn("--pf-red: #b54749", stylesheet)
        self.assertIn("--pf-green: #3e7c59", stylesheet)
        self.assertIn("font-size: 32px", stylesheet)
        self.assertIn("font-size: 28px", stylesheet)

        app = self.run_app()
        markdown = "\n".join(item.value for item in app.markdown)
        self.assertIn("Shared workflow record", markdown)
        self.assertIn("System boundary", markdown)
        self.assertIn("Prototype assumption", markdown)
        self.assertIn("Value created", markdown)
        self.assertIn("Next validation step", markdown)
        self.assertIn(
            "ProcureFlow is designed to improve ownership clarity",
            markdown,
        )
        self.assertIn(
            "representative users before expanding the prototype.",
            markdown,
        )
        self.assertEqual(markdown.count('class="pf-context-card"'), 5)
        self.assertIn("Operational overview", markdown)
        self.assertIn("Required information outstanding", markdown)
        self.assertIn("Approval not confirmed", markdown)
        self.assertIn("No update in 7 days", markdown)
        self.assertIn("High-priority dependency overdue", markdown)
        self.assertIn(
            "still Submitted after more than one business day",
            markdown,
        )
        self.assertIn(
            "Lifecycle status shows where the request is",
            markdown,
        )
        self.assertNotIn("single source of truth", markdown.lower())
        self.assertNotIn("real-time", markdown.lower())
        dashboard_source = (
            PROJECT_ROOT / "views" / "dashboard.py"
        ).read_text(encoding="utf-8")
        self.assertIn("How attention is determined", dashboard_source)
        self.assertIn("not an audited financial total", dashboard_source)
        self.assertIn("grid-template-columns: repeat(6", stylesheet)
        self.assertIn("grid-template-columns: repeat(2", stylesheet)
        self.assertIn("grid-template-columns: 1fr", stylesheet)

    def test_operational_overview_precedes_attention_table(self):
        app = self.run_app()
        markdown = "\n".join(item.value for item in app.markdown)
        self.assertIn("pf-kpi-marker--secondary", markdown)
        self.assertIn("pf-table-tag--urgent", markdown)
        self.assertIn("pf-table-tag--unassigned", markdown)

        dashboard_source = (
            PROJECT_ROOT / "views" / "dashboard.py"
        ).read_text(encoding="utf-8")
        table_call = dashboard_source.rfind(
            "_render_attention_table(attention_requests)"
        )
        chart_call = dashboard_source.rfind("_render_charts(summary)")
        self.assertGreaterEqual(table_call, 0)
        self.assertGreaterEqual(chart_call, 0)
        self.assertLess(chart_call, table_call)
        self.assertIn(
            "st.columns([0.9, 1.35, 0.9, 1.15])",
            dashboard_source,
        )

    def test_attention_queue_is_compact_and_exposes_all_conditions(self):
        app = self.run_app()
        markdown = "\n".join(item.value for item in app.markdown)
        headers = re.findall(r'<th scope="col">([^<]+)</th>', markdown)
        self.assertEqual(
            headers,
            [
                "Request",
                "Priority",
                "Owner",
                "Attention",
                "Next action",
                "Due",
            ],
        )
        self.assertIn("+2 more", markdown)
        self.assertIn("aria-label=", markdown)
        self.assertEqual(markdown.count("<tbody>"), 1)
        table_markup = markdown.split("<tbody>", 1)[1].split(
            "</tbody>",
            1,
        )[0]
        self.assertEqual(table_markup.count("<tr>"), 8)
        self.assertNotIn("assignment_overdue", markdown)

        stylesheet = (
            PROJECT_ROOT / "assets" / "styles.css"
        ).read_text(encoding="utf-8")
        self.assertIn("min-width: 0", stylesheet)
        self.assertIn("min-width: 760px", stylesheet)

    def test_empty_result_filter_combination_is_readable(self):
        app = self.run_app()
        app.sidebar.multiselect[0].select("Submitted")
        app.sidebar.multiselect[4].select("Alex Morgan").run()
        self.assertEqual(list(app.exception), [])
        self.assertEqual(len(app.metric), 0)
        messages = "\n".join(item.value for item in app.info)
        self.assertIn(
            "No requests match the selected filters. Reset the filters or "
            "adjust your selections to view results.",
            messages,
        )

    def test_no_attention_state_is_readable(self):
        app = self.run_app()
        app.sidebar.multiselect[0].select("Completed")
        app.sidebar.multiselect[1].select("Medium").run()
        self.assertEqual(list(app.exception), [])
        messages = "\n".join(item.value for item in app.success)
        self.assertIn(
            "No requests require attention for the selected filters.",
            messages,
        )

    def test_missing_database_state_does_not_crash_or_create_file(self):
        missing_path = (
            Path(self.temp_directory.name) / "missing.duckdb"
        )
        os.environ["PROCUREFLOW_DATABASE_PATH"] = str(missing_path)
        app = self.run_app()
        self.assertEqual(list(app.exception), [])
        self.assertFalse(missing_path.exists())
        warnings = "\n".join(item.value for item in app.warning)
        self.assertIn("demo setup is required", warnings)

    def test_empty_database_state_is_readable(self):
        empty_path = Path(self.temp_directory.name) / "empty.duckdb"
        initialize_database(empty_path, reset=True)
        os.environ["PROCUREFLOW_DATABASE_PATH"] = str(empty_path)
        app = self.run_app()
        self.assertEqual(list(app.exception), [])
        messages = "\n".join(item.value for item in app.info)
        self.assertIn(
            "No requests match the selected filters. Reset the filters or "
            "adjust your selections to view results.",
            messages,
        )

    def test_dashboard_loading_is_read_only(self):
        connection = connect_database(self.test_database_path)
        try:
            tables_before = list_table_names(connection)
            counts_before = {
                table_name: connection.execute(
                    f"SELECT COUNT(*) FROM {table_name}"
                ).fetchone()[0]
                for table_name in tables_before
            }
        finally:
            connection.close()

        app = self.run_app()
        self.assertEqual(list(app.exception), [])

        connection = connect_database(self.test_database_path)
        try:
            tables_after = list_table_names(connection)
            counts_after = {
                table_name: connection.execute(
                    f"SELECT COUNT(*) FROM {table_name}"
                ).fetchone()[0]
                for table_name in tables_after
            }
        finally:
            connection.close()

        self.assertEqual(tables_before, tables_after)
        self.assertEqual(counts_before, counts_after)
        self.assertEqual(len(tables_after), 4)

    def test_navigation_exposes_only_implemented_pages(self):
        self.assertFalse(any((PROJECT_ROOT / "pages").glob("*.py")))
        source = APP_PATH.read_text(encoding="utf-8")
        self.assertEqual(source.count("st.Page("), 2)
        self.assertIn('title="Dashboard"', source)
        self.assertIn('title="Requests"', source)
        self.assertNotIn("Request Detail", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
