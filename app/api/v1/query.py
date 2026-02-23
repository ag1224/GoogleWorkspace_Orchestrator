from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.redis_client import rate_limit_check, store_conversation_context, get_conversation_context
from app.config import get_settings
from app.core.intent_classifier import classify_intent
from app.core.orchestrator import ServiceOrchestrator
from app.core.query_planner import build_execution_plan
from app.core.response_synthesizer import synthesize_response
from app.db.database import get_db
from app.models.conversation import Conversation
from app.models.user import User
from app.schemas.query import QueryRequest, QueryResponse
from app.services.google_auth import get_valid_token

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
async def process_query(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db),
    x_user_id: str = Header(..., description="Authenticated user ID"),
):
    """Process a natural language query against Google Workspace."""
    user_id = uuid.UUID(x_user_id)

    # Rate limiting
    allowed = await rate_limit_check(str(user_id), limit=settings.max_queries_per_hour)
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")

    # Get user and valid token
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        access_token = await get_valid_token(user, db)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    # Conversation context
    context = await get_conversation_context(str(user_id))
    await store_conversation_context(str(user_id), request.query)

    # 1. Classify intent
    intent = await classify_intent(request.query, conversation_context=context)
    logger.info("Classified intent: %s (confidence=%.2f)", intent.intent, intent.confidence)

    # Handle ambiguities
    if intent.ambiguities and intent.confidence < 0.5:
        conv = Conversation(
            id=request.conversation_id or uuid.uuid4(),
            user_id=user_id,
            query=request.query,
            intent=intent.model_dump(),
            response=f"I need some clarification:\n" + "\n".join(f"- {a}" for a in intent.ambiguities),
        )
        db.add(conv)
        await db.commit()
        return QueryResponse(
            conversation_id=conv.id,
            query=request.query,
            response=conv.response,
            actions_taken=[],
            created_at=conv.created_at,
        )

    # 2. Build execution plan
    plan = build_execution_plan(intent)
    logger.info("Execution plan: %d steps, %d parallel groups", len(plan.steps), len(plan.parallel_groups))

    # 3. Execute
    orchestrator = ServiceOrchestrator(user_id=user_id, access_token=access_token, db=db)
    step_results = await orchestrator.execute(plan)

    # 4. Synthesize response
    response_text, actions_taken = await synthesize_response(request.query, step_results)

    # Persist conversation
    conv = Conversation(
        id=request.conversation_id or uuid.uuid4(),
        user_id=user_id,
        query=request.query,
        intent=intent.model_dump(),
        execution_plan=plan.model_dump(),
        response=response_text,
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)

    return QueryResponse(
        conversation_id=conv.id,
        query=request.query,
        response=response_text,
        actions_taken=actions_taken,
        created_at=conv.created_at,
    )
