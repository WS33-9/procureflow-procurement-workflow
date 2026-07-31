"""Central configuration for the ProcureFlow portfolio prototype.

The prototype intentionally keeps controlled values in code. An
administrator-facing configuration interface is deferred to a production
phase.
"""

APPLICATION_TIMEZONE = "America/Toronto"

LIFECYCLE_STATUSES = (
    "Submitted",
    "Assigned",
    "In Progress",
    "Completed",
    "Cancelled",
)

TERMINAL_STATUSES = ("Completed", "Cancelled")

ALLOWED_STATUS_TRANSITIONS = {
    "Submitted": ("Assigned", "Cancelled"),
    "Assigned": ("In Progress", "Cancelled"),
    "In Progress": ("Completed", "Cancelled"),
    "Completed": (),
    "Cancelled": (),
}

ROLES = (
    "Procurement Officer",
    "Procurement Manager",
    "Administrator",
)

PRIORITIES = (
    "Low",
    "Medium",
    "High",
    "Urgent",
)

HIGH_PRIORITIES = ("High", "Urgent")

PROCUREMENT_ROUTES = (
    "Low-Value Purchase",
    "Competitive Procurement",
    "Non-Competitive Procurement",
    "Existing Contract or Agreement",
    "Contract Amendment",
    "Other",
)

BUSINESS_UNITS = (
    "Corporate Services",
    "Finance",
    "Human Resources",
    "Business Operations",
    "Technology",
)

REQUEST_CATEGORIES = (
    "Technology",
    "Professional Services",
    "Facilities",
    "Equipment",
    "Marketing",
    "Logistics",
    "Office and Administrative Services",
)

DEPENDENCY_TYPES = (
    "Required Information",
    "Approval",
    "Supplier Response",
    "Signature",
    "Internal Review",
    "System or Financial Action",
    "Other",
)

APPROVAL_STATUSES = (
    "Not Required",
    "Not Confirmed",
    "Confirmed",
)

REFERENCE_TYPES = (
    "Approval Record",
    "Purchase Requisition",
    "Purchase Order",
    "Solicitation or RFP",
    "Contract",
    "Amendment",
    "Call-Up",
    "Release",
    "Task Authorization",
    "Official Document Reference",
    "Other Procurement Record",
)

CANCELLATION_REASONS = (
    "Request Withdrawn",
    "Requirement No Longer Needed",
    "Duplicate Request",
    "Funding Not Available",
    "Replaced by Another Procurement Approach",
    "Other",
)

ATTENTION_RULE_THRESHOLDS = {
    "assignment_overdue_business_days": 1,
    "no_recent_update_calendar_days": 7,
}

HISTORY_EVENT_TYPES = (
    "Request Created",
    "Assigned",
    "Reassigned",
    "Status Changed",
    "Dependency Updated",
    "Target Date Updated",
    "Approval Updated",
    "Route Changed",
    "Reference Added",
    "Closure Evidence Updated",
    "Completed",
    "Cancelled",
)
