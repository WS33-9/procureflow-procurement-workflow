# Proposed go-live readiness plan

## Purpose

Define the decisions and checks that would be needed before moving beyond the local portfolio prototype. This is not a production deployment plan or evidence of go-live approval.

## Readiness gates

| Area | Ready when |
|---|---|
| Scope | First-phase inclusions, exclusions, ownership, and success measures are approved. |
| Process | Intake, assignment, lifecycle, dependency, approval, reference, completion, and cancellation rules are confirmed. |
| Data | Field definitions, controlled values, ownership, correction process, and any migration approach are agreed. |
| Roles and access | A role/action matrix and production authentication/authorization design are approved. |
| Configuration | Values, thresholds, reporting filters, and code-free administration approach are tested and owned. |
| Testing | Configuration tests and representative UAT scenarios pass; accepted issues have owners and dates. |
| Training | Role-based materials are current; participants and support staff are prepared. |
| Technology | Hosting, security, monitoring, backup, recovery, retention, capacity, and support meet production requirements. |
| Integrations | Any approved integration has clear source ownership, access, data-quality checks, failure handling, and support. |
| Support | Service ownership, triage, escalation, release, and early-life support are staffed. |

## Cutover preparation

- Freeze the approved configuration and deployment version.
- Validate production users and role assignments.
- Load only agreed data and reconcile counts and required fields.
- Confirm links to external systems use the correct environment.
- Run smoke tests for intake, assignment, current work, closure, history, and reporting.
- Publish support contacts and known limitations.
- Define the decision owner and criteria for go/no-go.

## Rollback and early-life support

Before cutover, define how to stop new entries, preserve submitted data, return users to the prior process, and communicate the decision. During early-life support, monitor failed submissions, incomplete assignments, stale requests, closure errors, reporting reconciliation, adoption, and continued use of separate trackers.

## Open production decisions

The portfolio prototype does not resolve authentication, authorization, hosting, monitoring, backup, recovery, retention, scale, live integrations, or code-free configuration administration. Those items require discovery and technical design before go-live readiness can be claimed.
