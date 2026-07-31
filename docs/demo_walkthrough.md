# ProcureFlow demo walkthrough

This scenario follows one fictional request from intake to completion. It shows how the operational record, validation, history, and Dashboard work together. No real client or business data is involved.

## Prepare a safe workspace

1. Open **Requests**.
2. Under **Demo workspace**, select **Create local demo workspace**.
3. Confirm that **Local writable copy active** appears in the sidebar.

All changes now go to a session copy. The starting database remains unchanged.

## 1. Create the request

Select **New request** and enter:

| Field | Value |
|---|---|
| Created by / demo submitter | Elena Brooks · Procurement Manager |
| Request title | Workplace accessibility assessment |
| Requestor name | Maya Chen |
| Business unit | Human Resources |
| Request category | Professional Services |
| Description | Independent accessibility assessment for the Toronto workplace renewal. |
| Priority | High |
| Required-by date | August 28, 2026 |
| Estimated value | CAD 24,000 |
| Closure evidence required | Yes |

Select **Create request**.

Expected result:

- the request receives number **PF-0049** in a fresh workspace;
- Request Detail opens automatically;
- status is **Submitted** and ownership is **Unassigned**;
- history begins with **Request Created**.

The intake values are working assumptions for the prototype. The selected demo submitter records attribution; it is not authentication.

## 2. Assign an officer

Open **Assign request**:

- Assigned by: **Elena Brooks · Procurement Manager**
- Procurement owner: **Alex Morgan**

Select **Assign request**. The request moves to Assigned and records the assignment date and actor.

## 3. Start work

Select **Start work**. The request moves to In Progress. Alex Morgan becomes the default demo actor because Alex owns the request.

## 4. Record the current work

Open **Update current work** and enter:

- Current dependency requires follow-up: **Yes**
- Dependency type: **Required Information**
- Current dependency: `Final workplace scope and site-access details are outstanding.`
- Dependency owner: `Facilities lead`
- Next action: `Confirm the assessment scope and site-access arrangements.`
- Follow-up date: **August 3, 2026**
- Target completion date applies: **Yes**
- Target completion date: **August 14, 2026**
- Procurement route: **Low-Value Purchase**
- Officer note: `Requestor confirmed the assessment objective and required completion window.`

Save the update. The detail view now shows what is outstanding, who needs to respond, and when the officer will follow up.

## 5. Record approval confirmation

Open **Record approval confirmation**:

- Approval is required: **Yes**
- Approval requirement: `Director spending approval`
- Approval status: **Confirmed**
- Approval source: `Finance approval process`
- Approval reference: `APR-2026-219`
- Confirmation date: **July 30, 2026**
- Approval notes: `Confirmation recorded from the finance approval process.`

ProcureFlow records the external decision and its reference. It does not grant the approval.

## 6. Add the related record

Open **Add related reference**:

- Reference type: **Approval Record**
- Reference number: `APR-2026-219`
- Source system or process: `Finance approval process`
- Reference link: `https://example.invalid/approvals/APR-2026-219`
- Use as closure evidence: **Yes**
- Reference note: `Fictional approval reference for the portfolio walkthrough.`

Only the identifier and link are stored. The official record remains in its source process.

## 7. Test completion validation

Open **Complete request** and enter this closure note:

`Accessibility assessment completed and the related approval reference recorded.`

Leave **Required closure evidence is confirmed** unchecked and select **Complete request**.

Expected result: completion is blocked because required closure evidence has not been confirmed. The request remains In Progress.

## 8. Complete the request

Open **Complete request** again, retain the closure note, select **Required closure evidence is confirmed**, and complete the request.

Expected result:

- status becomes Completed;
- the completion date is recorded;
- the request becomes read-only;
- no open-work attention condition remains.

## 9. Review the history

The chronological history should include:

- Request Created;
- Assigned;
- Status Changed;
- Dependency Updated;
- Target Date Updated;
- Route Changed;
- Approval Updated;
- Reference Added;
- Closure Evidence Updated;
- Completed.

This is a focused operational history, not a production audit log.

## 10. Check the Dashboard

Return to **Dashboard**. Because it reads the same session database, it includes the newly completed request without a separate reporting update.

Starting from the approved 48-request baseline, the completed walkthrough produces:

| Measure | Baseline | After walkthrough |
|---|---:|---:|
| Total requests | 48 | 49 |
| Open requests | 36 | 36 |
| Submitted | 8 | 8 |
| Completed | 8 | 9 |
| Unassigned open requests | 8 | 8 |

The request is briefly counted as open and unassigned after intake, then leaves open workload when completed.

## Reset

1. Return to **Requests**.
2. Select **Confirm reset to approved baseline**.
3. Select **Reset local demo workspace**.
4. Confirm that PF-0049 is removed and Dashboard values return to the 48-request baseline.
