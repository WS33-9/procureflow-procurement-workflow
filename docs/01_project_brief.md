# ProcureFlow Project Brief

## Project title

**ProcureFlow: Enterprise Procurement Workflow Implementation Case**

## Executive summary

ProcureFlow is a fictional enterprise SaaS implementation case designed to improve procurement workflow efficiency, clarify ownership, and provide more timely and reliable management reporting across the request lifecycle.

An organization may already have approved systems and processes for formal approvals, financial transactions, sourcing, contracting, supplier communication, and official records. However, the operational information around a procurement request may still be spread across email, forms, spreadsheets, collaboration tools, and individual notes.

As a result, procurement officers may need to enter or update similar information in several places, search across different tools to understand what is outstanding, and manually follow up with stakeholders.

Managers may also depend on separate trackers and individual updates to understand workload and progress. Preparing a report can require manual consolidation, and the information may already be outdated by the time it is presented.

This can make it difficult to answer:

- Who owns the request?
- What is still outstanding, and who needs to act next?
- Which follow-ups or target dates are overdue?
- How is workload distributed across the team?
- Can management rely on the reporting to be current and consistently maintained?

ProcureFlow proposes a configurable workflow layer that creates one shared operational view around each request without replacing the systems and processes that already perform formal procurement activities.

The project includes a lightweight Streamlit prototype, synthetic data, a DuckDB data layer, a short case deck, and supporting implementation documents.

The prototype demonstrates the proposed workflow, data fields, reporting logic, and solution boundaries. It is not a complete procurement platform or production deployment.

## Why I built this project

I chose procurement because it is a business process I understand well enough to make realistic decisions about ownership, dependencies, reporting, and implementation trade-offs.

I built the project to apply that process knowledge in an enterprise SaaS context and show how I would approach an implementation from discovery through go-live.

The questions that guided the project were:

- What is the actual business problem?
- Which assumptions need to be validated?
- What belongs in the first phase?
- Which systems and processes should remain unchanged?
- What should be configured rather than customized?
- What information should ProcureFlow store, and what should only be referenced?
- What could create delivery or adoption risk?
- How should success be measured?

As the design developed, I simplified several early assumptions.

I removed a separate blocked status, avoided assuming that a dedicated sourcing platform or triage team existed, and chose manual references before considering system integration.

The prototype is one part of the project. The main focus is how I defined the problem, made scope decisions, and approached implementation.

## Fictional client

Northbridge Holdings is a fictional Canadian organization with several business units and operating locations.

Its procurement team supports areas such as technology, professional services, facilities, equipment, marketing, logistics, and corporate operations.

Northbridge already uses approved processes and tools for formal approvals, financial transactions, sourcing and contracting work, supplier communication, and official records.

All organizations, users, suppliers, systems, data, and workflows used in this project are fictional.

## Current-state problem

A procurement request may begin through email or a shared form.

It is then assigned to a procurement officer, reviewed, clarified with the requesting team, coordinated with other stakeholders, and eventually connected to an approval, procurement instrument, financial transaction, or official record.

The individual processes may work, but together they may not provide one consistent operational view from submission through completion.

This can lead to:

- inconsistent or incomplete intake information;
- unclear request ownership;
- repeated entry of similar information across working tools;
- dependencies and next actions remaining in emails or individual notes;
- approval status sitting outside the working view;
- related records not being referenced consistently;
- time spent searching for updates and following up manually;
- management reporting that requires consolidation across separate trackers;
- reports that may not reflect the latest available information;
- incomplete closure notes or reference trails.

The result is not only limited visibility. It can also create avoidable administrative effort, unclear accountability, inconsistent follow-up, and reporting that depends on individual updates.

## Proposed solution

ProcureFlow acts as the operational workflow layer around the procurement request, giving the team one place to manage ownership, dependencies, next actions, follow-up, and reporting.

It manages:

- standardized request intake;
- assignment and ownership;
- lifecycle status;
- dependencies and next actions;
- follow-up and target completion dates;
- approval status and confirmation details;
- references and links to related records;
- rules for identifying requests requiring attention;
- workload and management reporting;
- completion, cancellation, and key operational history.

It does not replace:

- formal approval systems or approved channels;
- ERP or financial systems;
- sourcing and contracting processes;
- supplier communication;
- official document repositories.

This boundary is intentional.

ProcureFlow is designed to improve workflow efficiency, clarify ownership, and provide more timely and reliable management reporting without duplicating the systems and processes that already own formal approvals, transactions, contracts, or official records.

## First-phase recommendation

I recommend starting with a limited first phase focused on the core workflow.

The proposed MVP includes:

- standardized intake and required-field validation;
- assignment and ownership;
- five lifecycle statuses: Submitted, Assigned, In Progress, Completed, and Cancelled;
- dependency and next-action tracking;
- follow-up and target completion dates;
- approval status and confirmation details;
- manually entered references and links;
- configurable rules for identifying requests requiring attention;
- workload and management reporting;
- completion and key history.

The implementation approach also includes:

- requirements validation;
- field definitions;
- sample field mapping;
- configuration testing;
- UAT;
- training;
- go-live readiness;
- early post-launch support.

The first phase does not assume that surrounding systems are connected to ProcureFlow.

Where another process or system creates an approval, purchase order, contract, amendment, solicitation, or official document, the procurement officer records the relevant reference number and, where available, a link.

Selected fields could be automated later where there is a clear business case.

## Key implementation decisions

### Keep the lifecycle simple

Temporary waiting situations are recorded through the dependency, dependency owner, next action, follow-up date, and target completion date rather than creating a separate status for every situation.

### Surface objective conditions

The dashboard highlights clear conditions such as:

- assignment overdue;
- follow-up overdue;
- target completion date missed;
- required information not yet received;
- required approval not yet confirmed;
- no recent update;
- high-priority request with an overdue dependency;
- completed request missing required closure evidence.

This gives managers and officers a more consistent way to identify where action is needed.

### Use configuration before customization

Categories, priorities, procurement routes, approval values, reference types, cancellation reasons, thresholds, and reporting filters should be configurable where practical.

Customization should only be considered where a confirmed requirement cannot reasonably be supported through configuration.

### Keep formal records in their existing systems

ProcureFlow stores only the operational status, confirmation details, reference, or link needed by the procurement team.

This reduces the risk of conflicting records.

### Introduce automation selectively

Automation should only be introduced after confirming:

- data ownership;
- access;
- field reliability;
- failure handling;
- correction processes;
- support responsibility.

The goal is to automate where there is clear value, not to connect every system by default.

## Expected value

The proposed future state is intended to support:

- less repeated entry and reconciliation across separate working tools;
- clearer ownership and accountability;
- better control of dependencies, next actions, and follow-up;
- a more timely and consistent view of workload and progress;
- less manual effort required to prepare management reporting;
- earlier identification of requests requiring attention;
- clearer links between requests and related records;
- more consistent request closure;
- a stronger foundation for later automation.

No percentage improvement is assumed in advance.

In a real engagement, I would first establish a baseline and agree success measures with the client.

Possible measures include:

- intake completeness;
- time from submission to assignment;
- number of overdue follow-ups;
- age of open requests by procurement route and priority;
- percentage of requests with a current owner, next action, and follow-up date;
- completion of required approval, transaction, and closure references;
- time required to prepare management reporting;
- number of manual adjustments required to prepare management reporting;
- user adoption;
- continued use of separate trackers.

## What I would validate with the client

Before configuration, I would confirm:

- intake, assignment, and lifecycle rules;
- dependency, follow-up, approval, reference, and closure requirements;
- reporting needs and user roles;
- ownership of data and configurable values;
- whether selected references should later be automated;
- UAT scenarios and go-live readiness criteria.

## Prototype limitations

The Streamlit application is a functional prototype.

It is not:

- a live enterprise system using real business data;
- a replacement for existing procurement systems or processes;
- a live enterprise integration;
- a complete enterprise security and access design;
- a complete procurement platform.

Its purpose is to demonstrate the proposed workflow, data model, reporting logic, solution boundaries, and implementation approach.

## Confidentiality statement

This is a fictional composite case created for portfolio and learning purposes.

It does not reproduce the systems, processes, data, documents, terminology, organizational structure, approval model, workflow, supplier information, or reporting model of any current or former employer.

All organizations, users, suppliers, transactions, amounts, locations, roles, and system references used in the project are fictional.