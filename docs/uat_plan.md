# Proposed UAT plan

## Purpose

Use representative procurement scenarios to confirm that ProcureFlow supports the agreed first-phase workflow before any production decision. This plan has not been executed with a client.

## Participants

| Participant | Focus |
|---|---|
| Procurement officer | Intake quality, current-work maintenance, references, closure, and daily usability |
| Procurement manager | Assignment, workload, prioritization, escalation, and reporting |
| Administrator or configuration owner | Controlled values, thresholds, data ownership, and support handoff |
| Selected requestor | Submission wording and missing-information guidance |
| Approval, finance, records, or IT representative | System boundaries and reference responsibilities |

## Entry criteria

- First-phase scope and exclusions are understood.
- Required fields, lifecycle meanings, roles, routes, attention rules, and closure requirements are recorded as decisions or clearly labelled assumptions.
- Test data is fictional or approved for testing.
- The test environment and reset process are available.
- Expected results and issue owners are agreed.

## Core scenarios

| Scenario | Expected result |
|---|---|
| Submit a complete request | One Submitted, Unassigned request is created with a unique number and history. |
| Submit missing or invalid information | Clear validation appears and no request is created. |
| Assign and start work | One officer is recorded; status, dates, actor, and history update correctly. |
| Maintain a waiting request | Request remains In Progress while dependency, owner, next action, and follow-up are visible. |
| Record approval confirmation | Source, reference, and date are required for Confirmed; ProcureFlow does not make the decision. |
| Add external references | Identifiers and links are retained without storing official documents. |
| Review attention conditions | Each agreed condition triggers at its boundary and gives enough context to act. |
| Complete with missing evidence | Completion is blocked and the current state is preserved. |
| Complete or cancel valid work | Closure data and history are complete; terminal records are read-only. |
| Review management reporting | Workload, unassigned work, attention, and lifecycle totals reconcile to request records. |
| Reset the demo workspace | Session changes are removed and the baseline remains unchanged. |

## Issue handling

Record the scenario, expected result, actual result, severity, owner, and retest status. A failed business rule or data-integrity check blocks sign-off. Copy or layout issues may be accepted with an owner and target date if they do not prevent the task.

## Exit criteria

- Critical scenarios pass.
- No unresolved issue threatens data integrity, ownership, closure, or reporting consistency.
- Remaining assumptions and deferred items are visible.
- Business and technical owners agree whether the solution is ready for the next implementation stage.
- Sign-off records what was tested; it does not imply production security, scale, or integration readiness.
