from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent
from app.agents.gmail_agent import GmailAgent
from app.agents.gcal_agent import GCalAgent
from app.agents.drive_agent import DriveAgent
from app.schemas.query import ExecutionPlan, ExecutionStep, StepResult

logger = logging.getLogger(__name__)

STEP_TIMEOUT = 10.0  # seconds per step


class ServiceOrchestrator:
    """Executes an ExecutionPlan by running steps in parallel groups."""

    def __init__(self, user_id: UUID, access_token: str, db: AsyncSession):
        self.user_id = user_id
        self.access_token = access_token
        self.db = db
        self.agents: dict[str, BaseAgent] = {
            "gmail": GmailAgent(access_token=access_token, user_id=user_id, db=db),
            "gcal": GCalAgent(access_token=access_token, user_id=user_id, db=db),
            "drive": DriveAgent(access_token=access_token, user_id=user_id, db=db),
        }
        self.results: dict[str, StepResult] = {}

    async def execute(self, plan: ExecutionPlan) -> list[StepResult]:
        step_map = {s.id: s for s in plan.steps}

        for group in plan.parallel_groups:
            tasks = []
            for step_id in group:
                step = step_map[step_id]
                tasks.append(self._execute_step(step))

            group_results = await asyncio.gather(*tasks, return_exceptions=True)

            for step_id, result in zip(group, group_results):
                if isinstance(result, Exception):
                    self.results[step_id] = StepResult(
                        step_id=step_id,
                        agent=step_map[step_id].agent,
                        action=step_map[step_id].action,
                        status="failed",
                        error=str(result),
                    )
                else:
                    self.results[step_id] = result

        return list(self.results.values())

    async def _execute_step(self, step: ExecutionStep) -> StepResult:
        agent = self.agents.get(step.agent)
        if agent is None:
            return StepResult(
                step_id=step.id,
                agent=step.agent,
                action=step.action,
                status="failed",
                error=f"Unknown agent: {step.agent}",
            )

        # Inject context from dependency results into params
        params = dict(step.params)
        for dep_id in step.depends_on:
            dep_result = self.results.get(dep_id)
            if dep_result and dep_result.status == "success" and dep_result.data:
                params["_context"] = params.get("_context", {})
                params["_context"][dep_id] = dep_result.data

        try:
            result = await asyncio.wait_for(
                agent.execute_action(step.action, params),
                timeout=STEP_TIMEOUT,
            )
            return StepResult(
                step_id=step.id,
                agent=step.agent,
                action=step.action,
                status="success",
                data=result,
            )
        except asyncio.TimeoutError:
            logger.error("Step %s timed out after %ss", step.id, STEP_TIMEOUT)
            return StepResult(
                step_id=step.id,
                agent=step.agent,
                action=step.action,
                status="failed",
                error=f"Timeout after {STEP_TIMEOUT}s",
            )
        except Exception as e:
            logger.exception("Step %s failed: %s", step.id, e)
            return StepResult(
                step_id=step.id,
                agent=step.agent,
                action=step.action,
                status="failed",
                error=str(e),
            )
