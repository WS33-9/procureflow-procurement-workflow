# Officer workflow architecture

## Scope boundary

This increment adds a Request List, a routed Request Detail state, controlled
workflow actions, request-history visibility, and shared navigation with the
approved Dashboard. It does not add authentication, role-based access control,
integrations, file upload, notifications, configuration screens, or new data
tables.

## Page and route design

- `app.py` imports page compositions from `views/` and exposes two implemented
  navigation destinations only: Dashboard and Requests. The reserved
  Streamlit `pages/` directory contains no Python pages, preventing automatic
  discovery of internal modules as extra routes.
- Requests opens the Request List by default.
- Request Detail is a state within Requests, selected from a list row. This
  avoids a third placeholder page and keeps navigation restrained.
- The selected request identifier is held in Streamlit session state. A Back to
  requests action clears it.

## Shared application state

- Both pages resolve the active database through `src/ui.py`.
- Automated tests can continue to provide an isolated database through the
  existing `PROCUREFLOW_DATABASE_PATH` environment variable.
- An interactive reviewer begins on the immutable approved baseline. Workflow
  actions are disabled until they explicitly create a local demo workspace.
- Creating a workspace copies the approved baseline to a uniquely named local
  session database and stores that path in Streamlit session state.
- Resetting requires explicit confirmation and replaces only the active session
  copy with the approved baseline. Application startup never creates, resets,
  or regenerates data.

## Read and write paths

- Request List and Request Detail reuse `src/queries.py` and derived attention
  rules from `src/rules.py`.
- Reference-number search is added to the existing request query as an
  `EXISTS` condition against `request_references`; no denormalized field or
  search table is introduced.
- Workflow forms call the shared functions in `src/database.py` for assignment,
  lifecycle changes, current-state updates, approval confirmation, and related
  references.
- Every action reloads Request Detail from the same active database. Returning
  to Dashboard therefore reflects the same maintained request state.
- Attention conditions remain calculated at query time and are never written to
  the database.

## Demo actor boundary

The interface includes a clearly labelled demo actor selector so history can
show who performed a simulated action. It is not authentication or access
control. Existing database validation still enforces that assignment is
performed by a manager or administrator and that owners are procurement
officers.

## Data-model impact

No schema change is required. The four approved tables remain:

1. `app_users`
2. `procurement_requests`
3. `request_references`
4. `request_history`

The approved baseline database and deterministic totals remain unchanged.
