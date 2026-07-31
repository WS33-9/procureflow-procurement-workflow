# ProcureFlow Current and Future State

## 1. Purpose

This document outlines the current-state problem behind ProcureFlow and the proposed future-state workflow.

The goal is not to move every procurement activity into one application.

It is to reduce unnecessary manual coordination and repeated data entry while giving procurement officers and managers one consistent view of ownership, progress, dependencies, follow-up, and workload.

Formal approvals, financial transactions, sourcing and contracting work, supplier communication, and official records would remain in the systems and processes responsible for them.

The proposed workflow is a starting point.

In a real implementation, I would validate the process steps, fields, rules, and responsibilities with the client before configuration begins.

## 2. Current-state problem

Procurement work may still be completed successfully, but the information needed to manage that work can be spread across email, forms, spreadsheets, collaboration tools, formal systems, and individual notes.

The problem is not that every activity happens in a different place.

Those activities do not necessarily belong in one application.

The gap is that there may be no consistent operational view showing:

- who owns the request;
- its lifecycle status;
- what is still outstanding;
- who is expected to act next;
- when follow-up is required;
- whether the target completion date has been missed;
- how workload is distributed;
- which related records exist;
- what is required before the request can be closed.

This can create several forms of operational effort:

- officers may search across emails, trackers, and formal systems to reconstruct the current position of a request;
- similar information may be entered or updated in more than one place;
- ownership and next actions may depend on individual working notes;
- managers may need to request updates from each officer;
- reports may need to be manually consolidated from several sources;
- the final report may not reflect changes made after the consolidation began.

The issue is therefore not only visibility.

It is also workflow efficiency, accountability, and the timeliness and reliability of management information.

### Current-state workflow

| Stage | How it may work today | Main impact |
|---|---|---|
| Intake | Requests arrive through email, forms, or other channels with varying levels of detail | Officers may need repeated clarification or re-enter information |
| Assignment and review | An officer reviews the requirement and considers the procurement route | Ownership and progress may be maintained in separate trackers |
| Coordination | The officer works with requestors, finance, approvers, reviewers, and suppliers | Dependencies, next actions, and follow-up dates may remain in emails or notes |
| Related records | Approvals, purchase orders, contracts, amendments, and official documents are created elsewhere | Officers may search across systems and manually copy reference information |
| Reporting and closure | Managers combine trackers and individual updates | Reporting takes time, can duplicate effort, and may not reflect the latest information |

## 3. Proposed future state

ProcureFlow would provide one shared operational record for each request.

Officers would maintain ownership, dependencies, next actions, follow-up dates, and related references in one place.

Managers would use the same operational data to view workload, progress, and requests requiring attention.

This would reduce the need to recreate the same status information across separate trackers and then consolidate it again for reporting.

ProcureFlow would manage:

- standardized request intake;
- assignment and ownership;
- lifecycle status;
- dependencies and next actions;
- follow-up and target completion dates;
- approval status and confirmation details;
- references and links to related records;
- requests requiring attention;
- workload and management reporting;
- completion, cancellation, and key operational history.

It would not replace:

- formal approval systems or approved channels;
- ERP or financial systems;
- sourcing and contracting processes;
- supplier communication;
- official document repositories.

This boundary is intentional.

ProcureFlow is meant to connect operational information around the request, not duplicate the systems and processes that already own approvals, transactions, contracts, or official records.

## 4. Proposed workflow

### Step 1 — Submit the request

A requestor or authorized user submits a request through the agreed intake channel.

Illustrative fields include:

- request title;
- requestor;
- business unit;
- request category;
- description;
- estimated value;
- required-by date;
- priority;
- submission date.

The final field list and validation rules would be confirmed during discovery.

Each field should support assignment, workflow, reporting, or closure.

### Step 2 — Assign an owner

The request is assigned to one procurement officer.

Assignment may be manual in the first phase.

ProcureFlow records:

- procurement owner;
- assignment date;
- assigned-by user.

The status moves from `Submitted` to `Assigned`.

The design does not assume that a separate triage team or triage stage exists.

That would need to be confirmed with the client.

### Step 3 — Review the request

The officer reviews the request and records:

- whether additional information is required;
- the likely procurement route;
- the current dependency;
- the dependency owner;
- the next action;
- the follow-up date;
- the target completion date.

When active work begins, the status moves to `In Progress`.

### Step 4 — Track dependencies and next actions

The request remains `In Progress` while the officer coordinates the work.

Waiting situations are tracked separately because they describe what is outstanding, not the overall stage of the request.

ProcureFlow records:

- current dependency;
- dependency owner;
- next action;
- follow-up date;
- target completion date;
- officer note;
- last updated date.

### Step 5 — Surface requests requiring attention

The dashboard highlights requests that meet agreed rules, such as:

- assignment overdue;
- follow-up overdue;
- target completion date missed;
- required information not yet received;
- required approval not yet confirmed;
- no recent update;
- high-priority request with an overdue dependency;
- completed request missing required closure evidence.

Each item should provide enough context for the user to act, including:

- reason;
- procurement owner;
- dependency owner, where applicable;
- next action;
- relevant date;
- days outstanding;
- priority.

Prototype thresholds would be labelled as assumptions and validated with the client.

### Step 6 — Connect related records

When another system or process creates a related record, the procurement officer records the relevant reference in ProcureFlow.

Examples include:

- approval record;
- purchase requisition;
- purchase order;
- solicitation or RFP;
- contract;
- amendment;
- call-up;
- release;
- task authorization;
- official-document reference.

The first phase would use manual entry.

I chose this approach because designing an integration before confirming the source system, data owner, access, data quality, support responsibility, and failure process could add complexity before the underlying need is understood.

Selected fields could be automated later where there is a clear business case.

### Step 7 — Complete or cancel the request

A request is marked `Completed` when the agreed operational and closure requirements for its procurement route have been met.

A request is marked `Cancelled` when it will no longer proceed.

The record should include:

- completion or cancellation date;
- closure note;
- cancellation reason, where applicable;
- required references or evidence;
- last updated by.

## 5. Lifecycle and responsibilities

### Lifecycle-status model

| Status | Meaning |
|---|---|
| Submitted | Request received; no procurement officer assigned |
| Assigned | Procurement officer assigned; active work not yet started |
| In Progress | Officer is reviewing, coordinating, preparing, or completing the work |
| Completed | Agreed operational and closure requirements have been met |
| Cancelled | Request is no longer proceeding |

Waiting for information, approval, supplier response, signature, or another action does not create a separate lifecycle status.

Those situations are recorded through the dependency, dependency owner, next action, and follow-up fields.

### System and process responsibilities

| Area | Responsibility |
|---|---|
| ProcureFlow | Intake, ownership, status, dependencies, next actions, requests requiring attention, references, history, workload visibility, and operational reporting |
| Approval systems or approved channels | Formal approval decisions and approval evidence |
| ERP or financial systems | Financial transactions, commitments, purchase orders, and related financial records |
| Sourcing and contracting processes | Preparing documents, publishing opportunities where required, receiving responses, coordinating evaluations, issuing contracts or amendments, and communicating with suppliers |
| Document repository | Official records and retained documents |
| Email or collaboration tools | Communication and clarification |

## 6. What changes in the future state

| Current state | Proposed future state |
|---|---|
| Requests arrive with inconsistent information | Agreed intake fields and validation rules |
| Similar information may be entered in several working tools | One shared operational record for the request |
| Ownership may be maintained in separate trackers | One visible procurement owner and assignment date |
| Status may be interpreted differently | Simple lifecycle with agreed definitions |
| Dependencies remain in emails or notes | Dependency, owner, next action, and follow-up date recorded |
| Officers search across tools for the current position | Core operational context available in one view |
| Managers request and consolidate individual updates | Shared workload and management reporting based on the same operational data |
| Reports may be outdated after manual consolidation | More timely reporting with visible last-updated information |
| Requests requiring attention depend on individual follow-up | Configurable rules surface overdue or incomplete requests |
| Related records are difficult to trace | Reference numbers and links recorded against the request |
| Closure requirements vary or are unclear | Closure evidence defined by procurement route |
| Integration is considered before the need is clear | Manual references first; selected automation assessed later |

## 7. Expected value, assumptions, and readiness

The proposed future state is intended to support:

- less repeated entry across separate working tools;
- less time spent searching for current request information;
- clearer ownership and accountability;
- better control of dependencies, next actions, and follow-up;
- more consistent workload visibility;
- less manual effort required to prepare management reporting;
- more timely and reliable reporting based on shared operational data;
- earlier identification of requests requiring attention;
- clearer links between related records;
- more consistent closure.

I would not claim a percentage improvement before establishing a baseline.

Possible measures include:

- time from submission to assignment;
- number of systems or trackers updated for each request;
- time spent preparing recurring management reports;
- number of manual officer updates required for reporting;
- percentage of active requests with a current owner, next action, and follow-up date;
- overdue follow-ups;
- age of open requests by route and priority;
- workload distribution by owner;
- completion of required references;
- user adoption;
- continued use of separate trackers.

The current design assumes that:

- one operational request record can represent the work;
- one officer owns the request at a time;
- the five lifecycle statuses are sufficient;
- manual references are practical for the first phase;
- closure requirements can be defined by procurement route.

The design would be ready for configuration when the client confirms:

- intake fields;
- assignment approach;
- lifecycle rules;
- dependency and next-action fields;
- follow-up and target completion date rules;
- thresholds;
- procurement routes;
- approval details;
- reference and closure requirements;
- workload and reporting needs;
- user roles;
- first-phase scope.

Realistic end-to-end scenarios should also be available for testing.