# ProcureFlow Discovery Plan

## 1. Purpose

This plan outlines how I would approach discovery for ProcureFlow.

The goal is to understand how procurement requests are handled today, where repeated entry or manual coordination creates unnecessary effort, where ownership and follow-up become difficult to manage, and how management reporting is currently produced.

Discovery would also determine what should realistically be included in the first phase.

The current design is a starting point. I would expect parts of it to change after speaking with users, reviewing recent requests, and confirming how the organization’s existing systems and processes work.

## 2. Discovery approach

I would focus discovery on three questions:

1. **How does the work happen today?**
2. **Where does the process create unnecessary effort, delay, or uncertainty?**
3. **Which changes are valuable enough to include in the first phase?**

I would not rely only on written procedures or one person’s description.

I would compare:

- the documented process;
- how procurement officers complete the work in practice;
- what requestors experience;
- how ownership and follow-up are managed;
- what managers need to oversee workload, progress, and risk;
- what existing systems and processes already handle well.

The aim is to define a future state that is clear enough to configure and test, but focused enough for users to adopt.

### Stakeholders

| Stakeholder | Main discovery focus |
|---|---|
| Procurement officers | Daily workflow, ownership, extra steps, dependencies, next actions, and closure requirements |
| Procurement manager | Assignment, workload visibility, reporting, escalation, prioritization, and adoption |
| Requestors or business clients | Submission experience, missing information, and repeated clarification |
| Finance or approval stakeholders | Approval process, evidence, timing, and financial-system responsibilities |
| Records-management stakeholders | Official records, retention, and document references |
| System owners or IT | Access, security, data ownership, technical constraints, and integration feasibility |
| Project sponsor | Business priorities, scope, decision ownership, and go-live direction |

Not every stakeholder needs to use ProcureFlow.

Approvers, for example, may continue using the existing approval process while ProcureFlow records only the status, confirmation details, and reference needed by the procurement team.

## 3. Discovery activities

### 3.1 Speak with the people doing the work

I would interview procurement officers, the procurement manager, selected requestors, and stakeholders responsible for approvals, financial systems, and official records.

I would ask about:

- what they do from submission through completion;
- which tools and channels they use;
- where the same information is entered or updated more than once;
- how much time is spent searching for information or confirming status;
- where ownership becomes unclear;
- how dependencies and follow-up are managed;
- which responsibilities are unclear;
- what they track outside formal systems;
- where the process changes by request type;
- why separate trackers are still used.

I would also examine the extra steps users have created outside the formal process.

These steps may reveal a real gap, but I would not automatically reproduce them.

If an officer maintains a personal spreadsheet, the underlying need may be better visibility of ownership, follow-up, or next actions rather than another spreadsheet-like tool.

### 3.2 Walk through recent requests

I would ask users to walk through several recent procurement requests from beginning to end.

The examples should include different procurement routes, values, priorities, and levels of complexity.

For each request, I would trace:

- how it was submitted;
- when ownership was assigned;
- what information was missing;
- which approvals or reviews were required;
- what depended on another person, group, or process;
- how next actions and follow-up dates were managed;
- where related records were created;
- how completion was confirmed;
- what information management needed afterward.

This would help distinguish recurring needs from one-off situations.

### 3.3 Review forms, trackers, fields, and reports

I would review representative forms, spreadsheets, templates, field lists, and reports.

The goal would be to determine:

- which information is genuinely needed;
- which fields are duplicated or inconsistently defined;
- which values should come from standard lists;
- which fields apply only to certain request types;
- which records should remain outside ProcureFlow;
- which references are needed for reporting or closure.

I would also prepare a sample field map.

| Current information | Proposed ProcureFlow field | Decision to confirm |
|---|---|---|
| Client or requestor name | Requestor | Confirm the source and naming format |
| Branch or department | Business unit | Confirm the standard list |
| Required completion date | Required-by date | Confirm whether it is mandatory at submission |
| Assigned officer | Procurement owner | Confirm assignment and reassignment rules |
| Purchase order number | Related reference | Confirm when it becomes required |

The field map would clarify:

- what each field means;
- where the value comes from;
- whether it is required;
- who maintains it;
- what happens when it is missing or inconsistent.

### 3.4 Review reporting needs

I would review how managers currently obtain workload and status information.

I would look at:

- which reports are prepared;
- how often they are needed;
- which trackers or systems must be combined;
- which information is re-entered manually;
- who provides the updates;
- how long report preparation takes;
- how current the information is when the report is delivered;
- which measures managers trust;
- which information is difficult to obtain;
- what decisions management needs to make from the reporting.

Those decisions may include:

- balancing workload across officers;
- prioritizing high-risk or time-sensitive requests;
- escalating overdue dependencies;
- following up on missed target completion dates;
- identifying requests that require management intervention.

The future dashboard should help answer practical questions such as:

- Which requests still need an owner?
- How is workload distributed across the team?
- Which follow-ups are overdue?
- Which target completion dates have been missed?
- Which required approvals are not yet confirmed?
- Which requests have not been updated recently?
- Which completed requests are missing closure evidence?
- When was the information last updated?

The goal is to reduce manual consolidation and support workload management, prioritization, escalation, and follow-up rather than display every available metric.

### 3.5 Review findings and make decisions

After the interviews, walkthroughs, and document review, I would present the findings back to stakeholders.

The review would confirm:

- the current-state problem;
- the proposed future-state workflow;
- first-phase scope and exclusions;
- open decisions and assumptions;
- risks;
- success measures.

Where stakeholders disagree, I would document the different views, explain the impact of each option, and identify the decision owner.

I would not combine conflicting answers into a vague requirement simply to create the appearance of agreement.

## 4. Key discovery questions

### Intake and ownership

- Who can submit a request, and through which channels?
- What information is needed before assignment?
- What causes the most repeated clarification?
- Who assigns requests?
- How should reassignment be recorded?
- What ownership information should managers be able to see?

### Workflow and dependencies

- Can the proposed lifecycle statuses be applied consistently?
- What causes a request to move from one status to another?
- What commonly remains outstanding?
- What should users record as the dependency, dependency owner, and next action?
- How should follow-up and target completion dates be set and updated?
- What does completion mean for each procurement route?

### Approvals and related records

- Where do formal approvals occur?
- What confirms that approval has been obtained?
- Which references are required before closure?
- Which process or system owns each related record?
- Are manual references practical for the first phase?
- Which references may be worth automating later?

### Reporting and management decisions

- Which trackers, systems, or individual updates are currently combined?
- Where is the same information entered more than once?
- How long does it take to prepare recurring reports?
- How current is the information by the time the report is delivered?
- How is workload currently measured?
- Which requests require management attention?
- What information is needed for prioritization or escalation?
- Which measures are trusted?
- What information would allow management to act sooner?

### Adoption and go-live

- Why do users maintain separate trackers today?
- Which roles need access?
- What should each role be able to view or update?
- Which scenarios must pass UAT?
- Which unresolved issues would make the solution not ready for go-live?
- Who will own support and configurable values after launch?

## 5. Prioritization and decision management

Not every request raised during discovery should become part of the first phase.

I would consider:

- frequency and business impact;
- number of users affected;
- risk of leaving the need unresolved;
- whether another system already handles it;
- implementation effort;
- effect on adoption;
- whether it is required for go-live.

I would group requirements into four categories:

- **Must include:** needed for the core workflow, reliable data, ownership, reporting, adoption, compliance, or go-live.
- **Should include:** important, but the first phase could still operate without it.
- **Could include later:** useful after the core workflow is stable.
- **Do not include:** duplicates another system, adds unnecessary complexity, or does not address the agreed problem.

For example, if the organization already has an approved document repository, I would keep official documents there and store only their references and links in ProcureFlow.

I would organize decisions as:

- **Confirmed:** supported by stakeholder input and process evidence.
- **Proposed:** recommended but still requiring approval.
- **Open:** requiring a decision owner and target date.
- **Deferred:** potentially useful but outside the first phase.

This helps prevent unresolved assumptions from quietly becoming configuration decisions.

## 6. Outputs and completion criteria

Discovery would produce:

- an agreed business problem;
- current-state and proposed future-state workflows;
- first-phase scope and exclusions;
- stakeholder and role definitions;
- field definitions and sample mapping;
- current reporting sources and manual consolidation steps;
- baseline reporting effort and update frequency;
- ownership and assignment rules;
- lifecycle and dependency rules;
- approval, reference, and closure requirements;
- workload and management-reporting requirements;
- rules for identifying requests requiring attention;
- system and process responsibilities;
- recommendations for manual entry or later automation;
- a decision, risk, and assumption log;
- a UAT approach;
- go-live readiness criteria.

Discovery would be complete when the business problem, workflow, scope, fields, ownership rules, lifecycle rules, responsibilities, closure evidence, reporting requirements, and realistic end-to-end test scenarios are sufficiently clear for configuration to begin.