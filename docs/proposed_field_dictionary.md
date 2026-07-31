# Proposed field dictionary

The fields below describe the current portfolio prototype. Names, definitions, required timing, controlled values, and ownership should be confirmed during discovery.

## Request intake and identity

| Field | Meaning | Required timing | Maintained by |
|---|---|---|---|
| Request number | Human-readable identifier such as PF-0049 | Automatic at creation | System |
| Request title | Concise description of the purchase need | Submission | Submitter |
| Requestor name | External or internal business contact requesting the work | Submission | Submitter |
| Business unit | Internal department submitting the request | Submission | Submitter; controlled list |
| Request category | Type of product or service being purchased | Submission | Submitter; controlled list |
| Description | Business need and relevant context | Submission | Submitter |
| Estimated value | Indicative CAD value; not an audited financial amount | Optional | Submitter/officer |
| Priority | Low, Medium, High, or Urgent | Submission | Submitter; controlled list |
| Required-by date | Business need date; past dates are allowed | Submission | Submitter |
| Submitted at | Date and time received | Automatic | System |
| Lifecycle status | Submitted, Assigned, In Progress, Completed, or Cancelled | Automatic at creation; maintained through actions | System/user action |

## Ownership and current work

| Field | Meaning | Required timing | Maintained by |
|---|---|---|---|
| Procurement owner | One officer accountable for the request | Assignment | Manager/administrator action |
| Assignment date | When current ownership was recorded | Automatic at assignment | System |
| Assigned by | User who assigned the officer | Automatic at assignment | System |
| Procurement route | Current approach for completing the purchase | Before completion | Officer; controlled list |
| Dependency type | Category of the current outstanding item | When a dependency exists | Officer; controlled list |
| Current dependency | What is preventing or shaping the next step | Optional; complete set required when used | Officer |
| Dependency owner | Person, team, or external party expected to act | With current dependency | Officer |
| Next action | Concrete next step | With current dependency | Officer |
| Follow-up date | Date the officer will revisit the dependency | With current dependency | Officer |
| Target completion date | Planned completion date; does not change status automatically | Optional | Officer |
| Officer note | Brief operational context | Optional | Officer |

## Approval and closure

| Field | Meaning | Required timing | Maintained by |
|---|---|---|---|
| Approval required | Whether external approval confirmation must be tracked | As identified | Officer |
| Approval requirement | Description of the required approval | When approval is required | Officer |
| Approval status | Not Required, Not Confirmed, or Confirmed | Maintained during work | Officer; controlled list |
| Approval source | External process or system that owns the decision | When Confirmed | Officer |
| Approval reference | Identifier from the source process | When Confirmed | Officer |
| Approval confirmation date | When confirmation was obtained | When Confirmed | Officer |
| Approval notes | Additional confirmation context | Optional | Officer |
| Closure evidence required | Whether evidence and a marked reference are needed before completion | Set at intake; may be maintained during work | Submitter/officer |
| Closure evidence confirmed | Officer confirmation that required evidence exists | Before completion when required | Officer |
| Closure note | Summary of the completed outcome | Before completion | Officer |
| Completion date | When status became Completed | Automatic | System |
| Cancellation date | When status became Cancelled | Automatic | System |
| Cancellation reason | Why the request will not proceed | At cancellation | Procurement user; controlled list |

## References, history, and maintenance

| Field | Meaning | Required timing | Maintained by |
|---|---|---|---|
| Related reference | Type, number, source, optional link, closure marker, and note for an external record | As external records become available | Procurement user |
| Created at / by | Initial timestamp and internal demo actor | Automatic | System |
| Updated at / by | Most recent meaningful request update and actor | Automatic on shared writes | System |
| History event | Summary of an important operational change, including actor and time | Automatic on meaningful changes | System |

## Validation notes

- Submitted requests are Unassigned.
- Assigned and In Progress requests require complete assignment information.
- A current dependency requires its type, owner, next action, and follow-up date.
- Confirmed approval requires source, reference, and confirmation date.
- Completion requires a procurement route and closure note. When closure evidence is required, confirmation and at least one marked related reference are also required.
- Cancellation requires a reason and date.
- Completed and Cancelled are terminal in the prototype.
