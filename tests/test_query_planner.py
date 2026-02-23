import pytest

from app.core.query_planner import build_execution_plan
from app.schemas.query import ClassifiedIntent


def test_single_step_plan():
    intent = ClassifiedIntent(
        services=["gcal"],
        intent="search_events",
        entities={"date_range": {"from": "2026-03-02", "to": "2026-03-08"}},
        steps=["search_calendar_events_next_week"],
        ambiguities=[],
        confidence=0.95,
    )
    plan = build_execution_plan(intent)

    assert len(plan.steps) == 1
    assert plan.steps[0].agent == "gcal"
    assert plan.steps[0].action == "search_events"
    assert len(plan.parallel_groups) == 1


def test_parallel_steps_no_dependencies():
    intent = ClassifiedIntent(
        services=["gcal", "gmail", "drive"],
        intent="prepare_meeting",
        entities={"company": "Acme Corp"},
        steps=["find_calendar_event_tomorrow_acme", "search_emails_acme_corp", "search_drive_acme_documents"],
        ambiguities=[],
        confidence=0.9,
    )
    plan = build_execution_plan(intent)

    assert len(plan.steps) == 3
    # All 3 steps should be in the same parallel group (no dependencies)
    assert len(plan.parallel_groups) == 1
    assert len(plan.parallel_groups[0]) == 3


def test_sequential_dependencies():
    intent = ClassifiedIntent(
        services=["gmail", "gcal"],
        intent="cancel_flight",
        entities={"airline": "Turkish Airlines"},
        steps=["search_gmail_for_booking", "find_calendar_event", "extract_booking_reference", "draft_cancellation_email"],
        ambiguities=[],
        confidence=0.9,
    )
    plan = build_execution_plan(intent)

    assert len(plan.steps) == 4

    # extract_booking_reference depends on search_gmail_for_booking
    extract_step = next(s for s in plan.steps if s.action == "get_email" and "extract" in s.id or s.id == "step_2")
    assert "step_0" in extract_step.depends_on

    # draft depends on extract
    draft_step = next(s for s in plan.steps if s.action == "draft_email")
    assert "step_0" in draft_step.depends_on or "step_2" in draft_step.depends_on

    # Should have multiple parallel groups due to deps
    assert len(plan.parallel_groups) >= 2


def test_plan_preserves_entities_as_params():
    intent = ClassifiedIntent(
        services=["gmail"],
        intent="search_emails",
        entities={"sender": "sarah@company.com", "keyword": "budget"},
        steps=["search_emails"],
        ambiguities=[],
        confidence=0.9,
    )
    plan = build_execution_plan(intent)

    assert plan.steps[0].params.get("sender") == "sarah@company.com"
    assert plan.steps[0].params.get("keyword") == "budget"


def test_plan_with_date_entities():
    intent = ClassifiedIntent(
        services=["drive"],
        intent="search_files",
        entities={"date_range": {"from": "2026-01-01", "to": "2026-01-31"}, "mime_type": "application/pdf"},
        steps=["search_drive"],
        ambiguities=[],
        confidence=0.85,
    )
    plan = build_execution_plan(intent)

    assert plan.steps[0].params.get("date_from") == "2026-01-01"
    assert plan.steps[0].params.get("date_to") == "2026-01-31"
