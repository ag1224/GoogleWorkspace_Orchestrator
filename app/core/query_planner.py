from __future__ import annotations

import logging
from collections import defaultdict, deque

from app.schemas.query import ClassifiedIntent, ExecutionPlan, ExecutionStep

logger = logging.getLogger(__name__)

STEP_ACTION_MAP: dict[str, tuple[str, str]] = {
    "search_gmail": ("gmail", "search_emails"),
    "search_gmail_for_booking": ("gmail", "search_emails"),
    "search_emails": ("gmail", "search_emails"),
    "search_emails_acme_corp": ("gmail", "search_emails"),
    "get_email": ("gmail", "get_email"),
    "draft_email": ("gmail", "draft_email"),
    "draft_cancellation_email": ("gmail", "draft_email"),
    "send_email": ("gmail", "send_email"),

    "search_calendar": ("gcal", "search_events"),
    "search_calendar_events": ("gcal", "search_events"),
    "search_calendar_events_next_week": ("gcal", "search_events"),
    "search_calendar_events_with_john": ("gcal", "search_events"),
    "search_calendar_next_week": ("gcal", "search_events"),
    "find_calendar_event": ("gcal", "search_events"),
    "find_calendar_event_tomorrow_acme": ("gcal", "search_events"),
    "find_conflicting_events": ("gcal", "search_events"),
    "create_event": ("gcal", "create_event"),
    "update_event": ("gcal", "update_event"),
    "delete_event": ("gcal", "delete_event"),

    "search_drive": ("drive", "search_files"),
    "search_drive_acme_documents": ("drive", "search_files"),
    "search_drive_ooo_document": ("drive", "search_files"),
    "get_file": ("drive", "get_file"),
    "share_file": ("drive", "share_file"),

    "extract_booking_reference": ("gmail", "get_email"),
    "extract_ooo_dates": ("drive", "get_file"),
}

# Steps that depend on output from a prior step
DEPENDENCY_RULES: dict[str, list[str]] = {
    "draft_cancellation_email": ["search_gmail_for_booking", "extract_booking_reference"],
    "extract_booking_reference": ["search_gmail_for_booking"],
    "extract_ooo_dates": ["search_drive_ooo_document"],
    "find_conflicting_events": ["extract_ooo_dates", "search_calendar_next_week"],
}


def _resolve_step(step_name: str, intent: ClassifiedIntent) -> tuple[str, str, dict]:
    """Map a step name to (agent, action, params)."""
    if step_name in STEP_ACTION_MAP:
        agent, action = STEP_ACTION_MAP[step_name]
    else:
        # Heuristic: infer agent from step name
        if "gmail" in step_name or "email" in step_name:
            agent, action = "gmail", "search_emails"
        elif "calendar" in step_name or "event" in step_name or "gcal" in step_name:
            agent, action = "gcal", "search_events"
        elif "drive" in step_name or "file" in step_name or "doc" in step_name:
            agent, action = "drive", "search_files"
        else:
            agent, action = "gmail", "search_emails"

    params: dict = {}
    entities = intent.entities

    if "date_range" in entities:
        params["date_from"] = entities["date_range"].get("from")
        params["date_to"] = entities["date_range"].get("to")
    if "date" in entities:
        params["date"] = entities["date"]
    if "sender" in entities:
        params["sender"] = entities["sender"]
    if "attendee_name" in entities:
        params["attendee"] = entities["attendee_name"]
    if "attendee_email" in entities:
        params["attendee_email"] = entities["attendee_email"]
    if "company" in entities:
        params["keyword"] = entities["company"]
    if "airline" in entities:
        params["keyword"] = entities["airline"]
    if "keyword" in entities:
        params["keyword"] = entities["keyword"]
    if "document_type" in entities:
        params["keyword"] = entities.get("document_type", "")
    if "mime_type" in entities:
        params["mime_type"] = entities["mime_type"]

    return agent, action, params


def _topological_sort(steps: list[ExecutionStep]) -> list[list[str]]:
    """Return groups of step IDs that can be executed in parallel (topological layers)."""
    in_degree: dict[str, int] = {s.id: 0 for s in steps}
    dependents: dict[str, list[str]] = defaultdict(list)
    step_map = {s.id: s for s in steps}

    for s in steps:
        for dep in s.depends_on:
            if dep in step_map:
                in_degree[s.id] += 1
                dependents[dep].append(s.id)

    groups: list[list[str]] = []
    queue = deque([sid for sid, deg in in_degree.items() if deg == 0])

    while queue:
        current_group = list(queue)
        queue.clear()
        groups.append(current_group)

        for sid in current_group:
            for dep_id in dependents[sid]:
                in_degree[dep_id] -= 1
                if in_degree[dep_id] == 0:
                    queue.append(dep_id)

    return groups


def build_execution_plan(intent: ClassifiedIntent) -> ExecutionPlan:
    """Convert a classified intent into an executable DAG."""
    steps: list[ExecutionStep] = []

    for i, step_name in enumerate(intent.steps):
        agent, action, params = _resolve_step(step_name, intent)

        # Determine dependencies
        deps = []
        if step_name in DEPENDENCY_RULES:
            for dep_name in DEPENDENCY_RULES[step_name]:
                if dep_name in intent.steps:
                    dep_idx = intent.steps.index(dep_name)
                    deps.append(f"step_{dep_idx}")

        step = ExecutionStep(
            id=f"step_{i}",
            agent=agent,
            action=action,
            params=params,
            depends_on=deps,
        )
        steps.append(step)

    parallel_groups = _topological_sort(steps)

    return ExecutionPlan(steps=steps, parallel_groups=parallel_groups)
