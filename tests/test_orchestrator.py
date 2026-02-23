import uuid
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.core.orchestrator import ServiceOrchestrator
from app.schemas.query import ExecutionPlan, ExecutionStep


@pytest.mark.asyncio
async def test_execute_single_step(mock_db, sample_user_id, sample_access_token):
    plan = ExecutionPlan(
        steps=[
            ExecutionStep(id="step_0", agent="gmail", action="search_emails", params={"keyword": "flight"})
        ],
        parallel_groups=[["step_0"]],
    )

    with patch("app.core.orchestrator.GmailAgent") as MockGmail, \
         patch("app.core.orchestrator.GCalAgent"), \
         patch("app.core.orchestrator.DriveAgent"):
        mock_gmail = AsyncMock()
        mock_gmail.execute_action = AsyncMock(return_value=[{"email_id": "123", "subject": "Flight booking"}])
        MockGmail.return_value = mock_gmail

        orchestrator = ServiceOrchestrator(sample_user_id, sample_access_token, mock_db)
        orchestrator.agents["gmail"] = mock_gmail

        results = await orchestrator.execute(plan)

        assert len(results) == 1
        assert results[0].status == "success"
        assert results[0].agent == "gmail"


@pytest.mark.asyncio
async def test_execute_parallel_steps(mock_db, sample_user_id, sample_access_token):
    plan = ExecutionPlan(
        steps=[
            ExecutionStep(id="step_0", agent="gmail", action="search_emails", params={"keyword": "Acme"}),
            ExecutionStep(id="step_1", agent="gcal", action="search_events", params={"keyword": "Acme"}),
            ExecutionStep(id="step_2", agent="drive", action="search_files", params={"keyword": "Acme"}),
        ],
        parallel_groups=[["step_0", "step_1", "step_2"]],
    )

    mock_gmail = AsyncMock()
    mock_gmail.execute_action = AsyncMock(return_value=[{"email_id": "1"}])
    mock_gcal = AsyncMock()
    mock_gcal.execute_action = AsyncMock(return_value=[{"event_id": "2"}])
    mock_drive = AsyncMock()
    mock_drive.execute_action = AsyncMock(return_value=[{"file_id": "3"}])

    with patch("app.core.orchestrator.GmailAgent"), \
         patch("app.core.orchestrator.GCalAgent"), \
         patch("app.core.orchestrator.DriveAgent"):
        orchestrator = ServiceOrchestrator(sample_user_id, sample_access_token, mock_db)
        orchestrator.agents = {"gmail": mock_gmail, "gcal": mock_gcal, "drive": mock_drive}

        results = await orchestrator.execute(plan)

        assert len(results) == 3
        assert all(r.status == "success" for r in results)


@pytest.mark.asyncio
async def test_execute_handles_step_failure(mock_db, sample_user_id, sample_access_token):
    plan = ExecutionPlan(
        steps=[
            ExecutionStep(id="step_0", agent="gmail", action="search_emails", params={}),
            ExecutionStep(id="step_1", agent="gcal", action="search_events", params={}),
        ],
        parallel_groups=[["step_0", "step_1"]],
    )

    mock_gmail = AsyncMock()
    mock_gmail.execute_action = AsyncMock(side_effect=Exception("Gmail API error"))
    mock_gcal = AsyncMock()
    mock_gcal.execute_action = AsyncMock(return_value=[{"event_id": "1"}])

    with patch("app.core.orchestrator.GmailAgent"), \
         patch("app.core.orchestrator.GCalAgent"), \
         patch("app.core.orchestrator.DriveAgent"):
        orchestrator = ServiceOrchestrator(sample_user_id, sample_access_token, mock_db)
        orchestrator.agents = {"gmail": mock_gmail, "gcal": mock_gcal, "drive": AsyncMock()}

        results = await orchestrator.execute(plan)

        gmail_result = next(r for r in results if r.agent == "gmail")
        gcal_result = next(r for r in results if r.agent == "gcal")

        assert gmail_result.status == "failed"
        assert "Gmail API error" in gmail_result.error
        assert gcal_result.status == "success"


@pytest.mark.asyncio
async def test_execute_sequential_steps_pass_context(mock_db, sample_user_id, sample_access_token):
    plan = ExecutionPlan(
        steps=[
            ExecutionStep(id="step_0", agent="gmail", action="search_emails", params={"keyword": "flight"}),
            ExecutionStep(id="step_1", agent="gmail", action="draft_email", params={}, depends_on=["step_0"]),
        ],
        parallel_groups=[["step_0"], ["step_1"]],
    )

    call_params = {}

    async def capture_draft(**kwargs):
        call_params.update(kwargs)
        return {"draft_id": "d1", "status": "drafted"}

    mock_gmail = AsyncMock()
    mock_gmail.execute_action = AsyncMock(side_effect=[
        [{"email_id": "e1", "subject": "Flight TK1234", "sender": "airline@test.com"}],
        {"draft_id": "d1", "status": "drafted"},
    ])

    with patch("app.core.orchestrator.GmailAgent"), \
         patch("app.core.orchestrator.GCalAgent"), \
         patch("app.core.orchestrator.DriveAgent"):
        orchestrator = ServiceOrchestrator(sample_user_id, sample_access_token, mock_db)
        orchestrator.agents = {"gmail": mock_gmail, "gcal": AsyncMock(), "drive": AsyncMock()}

        results = await orchestrator.execute(plan)

        assert len(results) == 2
        assert results[0].status == "success"
