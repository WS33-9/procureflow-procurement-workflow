# ProcureFlow

A fictional procurement workflow implementation case built with Streamlit and
DuckDB.

ProcureFlow demonstrates how a shared operational layer can connect request
intake, ownership, follow-up, approval confirmation, related references,
closure, and management reporting without replacing formal ERP, approval,
contracting, or document systems.

The Streamlit application covers the request lifecycle from intake through assignment, active work, completion, and management reporting. It uses synthetic data and runs locally with DuckDB. Workflow changes are made in a temporary demo copy and may reset when the hosted application restarts. The synthetic baseline remains unchanged.

## The business problem

Procurement teams may already have systems for approvals, financial transactions, contracts, and official records, yet still coordinate day-to-day work through email, spreadsheets, forms, and personal notes. That makes basic questions harder to answer:

- Who owns each request?
- What is outstanding, and who needs to act next?
- Which follow-ups and target dates have been missed?
- How is work distributed across the team?
- Is management reporting based on current information?

The issue is not that every procurement activity happens in a different system. Many of those activities belong there. The gap is the lack of a consistent operational view around the request.

## The approach

ProcureFlow sits around existing procurement processes as a lightweight workflow layer. Officers maintain ownership, status, dependencies, next actions, dates, approval confirmation, and references in one request record. Managers use that same data for workload and attention reporting.

Several design choices keep the first phase focused:

- Five lifecycle statuses: Submitted, Assigned, In Progress, Completed, and Cancelled.
- Waiting stays In Progress; the dependency, owner, next action, and follow-up date explain what is holding up the work.
- Approval decisions remain in their existing process. ProcureFlow records confirmation and a reference only.
- Purchase orders, contracts, amendments, and official documents remain in their source systems. ProcureFlow stores identifiers and links.
- Attention conditions are calculated from current request data rather than maintained in a second tracker.
- Interactive changes use an isolated local copy so the synthetic baseline stays unchanged.

## What users can do

The prototype has two top-level views.

**Requests** supports the operational workflow:

1. Create a request through standardized intake.
2. Validate required information and create a Submitted, Unassigned record.
3. Assign one procurement officer and start work.
4. Maintain the current dependency, next action, follow-up date, target date, route, and officer note.
5. Record approval confirmation from an external process.
6. Add related record references and links.
7. Complete or cancel the request with closure validation.
8. Review a chronological history of important changes.

**Dashboard** supports management review:

- open, unassigned, overdue, and high-priority work;
- lifecycle and request-category distribution;
- workload by owner, including Unassigned;
- requests requiring attention, with reasons and next actions;
- filters that use the same maintained request data.

## Architecture and stack

```text
Streamlit UI
  ├── Requests: intake, list, detail, workflow actions
  └── Dashboard: management reporting
          ↓
Query and attention-rule layer
          ↓
Shared database services and validation
          ↓
DuckDB: users, requests, references, history
```

- **Python and Streamlit** for the application.
- **DuckDB** for the four-table local data layer.
- **Altair** for restrained management charts.
- **`src/database.py`** for shared writes, validation, numbering, timestamps, and history.
- **`src/rules.py`** for explainable, non-persisted attention conditions.
- **`src/queries.py`** for shared operational and reporting queries.
- **`src/config.py`** for prototype controlled values and thresholds.
- **`src/data_generator.py`** for deterministic fictional demo data.

## Run locally

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Open `http://127.0.0.1:8501` if the browser does not open automatically.

The application starts against `database/procureflow_demo.duckdb`. The fixed reporting date for the portfolio scenario is July 30, 2026.

## Use the demo workspace

The baseline opens in preview mode. On **Requests**, select **Create local demo workspace** before submitting or updating a request. ProcureFlow copies the baseline into `database/demo_sessions/` and directs all workflow writes to that session copy.

Use **Reset local demo workspace** to restore the starting data. The baseline database is not rewritten during the walkthrough.

For an isolated database supplied outside the interface, set:

```bash
export PROCUREFLOW_DATABASE_PATH=/absolute/path/to/session.duckdb
streamlit run app.py
```

## Suggested walkthrough

Use the [officer workflow walkthrough](docs/demo_walkthrough.md) for a complete scenario. It begins with a new fictional request, follows it through assignment and active work, records approval and an external reference, tests completion validation, reviews history, checks the Dashboard, and resets the workspace.

## Run the tests

With the virtual environment active:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

The suite covers the four-table schema, controlled values, validation, lifecycle transitions, attention rules, deterministic data, shared queries, Dashboard behavior, intake, officer workflow, workspace reset, and baseline integrity.

## System boundary and limitations

This is a portfolio prototype using fictional people, organizations, requests, values, and references. It is not a production procurement platform and has not been validated or accepted by a real client.

ProcureFlow does not replace formal approval channels, ERP or financial systems, sourcing and contracting processes, supplier communication, or official document repositories. It has no live integrations or production authentication. Roles are simulated for workflow and attribution; they are not access control. Controlled values are centralized in code, but code-free administrator maintenance is not implemented. Fields, roles, values, thresholds, and closure rules remain assumptions to confirm during discovery. Client UAT, training delivery, go-live execution, hosting, monitoring, backup, and recovery are outside this local prototype.

## Project documents

- [Project brief](docs/01_project_brief.md)
- [Discovery plan](docs/02_discovery_plan.md)
- [Current and future state](docs/03_current_and_future_state.md)
- [Scope and requirements](docs/04_scope_and_requirements.md)
- [Officer workflow architecture](working_source/officer_workflow_architecture.md)
- [UAT plan](working_source/uat_plan.md)
- [Training plan](working_source/training_plan.md)
- [Go-live readiness plan](working_source/go_live_readiness_plan.md)
- [Proposed field dictionary](working_source/proposed_field_dictionary.md)
