from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    conversation_id: uuid.UUID | None = None


class ActionTaken(BaseModel):
    service: str
    action: str
    status: str  # "success" | "failed" | "skipped"
    detail: str | None = None


class QueryResponse(BaseModel):
    conversation_id: uuid.UUID
    query: str
    response: str
    actions_taken: list[ActionTaken] = []
    created_at: datetime


class ClassifiedIntent(BaseModel):
    services: list[str] = Field(description="Services needed: gmail, gcal, drive")
    intent: str = Field(description="High-level intent label")
    entities: dict = Field(default_factory=dict, description="Extracted entities")
    steps: list[str] = Field(description="Ordered step descriptions")
    ambiguities: list[str] = Field(default_factory=list, description="Detected ambiguities needing clarification")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ExecutionStep(BaseModel):
    id: str
    agent: str  # "gmail" | "gcal" | "drive"
    action: str
    params: dict = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)


class ExecutionPlan(BaseModel):
    steps: list[ExecutionStep]
    parallel_groups: list[list[str]] = Field(description="Groups of step IDs that can run in parallel")


class StepResult(BaseModel):
    step_id: str
    agent: str
    action: str
    status: str  # "success" | "failed" | "skipped"
    data: dict | list | str | None = None
    error: str | None = None


class SyncStatusResponse(BaseModel):
    service: str
    last_sync_at: datetime | None
    status: str


class SyncTriggerResponse(BaseModel):
    message: str
    services: list[str]
