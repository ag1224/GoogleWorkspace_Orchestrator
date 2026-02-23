#!/usr/bin/env python3
"""Automated demo runner — executes 5 queries and prints formatted output.

Usage:
    # First start the server:
    uv run uvicorn app.main:app --reload

    # Then in another terminal:
    uv run python scripts/run_demo.py
"""

import asyncio
import json
import sys
import time

import httpx

BASE_URL = "http://localhost:8000"
USER_ID = "00000000-0000-0000-0000-000000000001"

DEMO_QUERIES = [
    {
        "label": "DEMO 1: Single-Service Query (Calendar)",
        "query": "What's on my calendar next week?",
        "description": "Simple calendar search — single agent, single step.",
    },
    {
        "label": "DEMO 2: Multi-Service Orchestration (Gmail + Calendar)",
        "query": "Cancel my Turkish Airlines flight",
        "description": "Cross-service: search Gmail for booking → find calendar event → draft cancellation email.\n"
                       "         Shows DAG execution: parallel search, then sequential draft.",
    },
    {
        "label": "DEMO 3: Three-Service Orchestration (Calendar + Gmail + Drive)",
        "query": "Prepare for tomorrow's client meeting with Acme Corp",
        "description": "All 3 services queried in parallel: find event, search emails, pull Drive docs.\n"
                       "         Results synthesized into a meeting preparation summary.",
    },
    {
        "label": "DEMO 4: Ambiguity Handling",
        "query": "Move the meeting with John",
        "description": "Ambiguous query — classifier detects low confidence, returns clarification request.\n"
                       "         Shows graceful handling of unclear intent.",
    },
    {
        "label": "DEMO 5: Conversation Context",
        "query": "That email about the proposal",
        "description": "Pronoun resolution using conversation context from previous queries.\n"
                       "         Demonstrates context window tracking via Redis.",
    },
]


def print_separator():
    print("\n" + "=" * 72)


def print_header(label: str, description: str):
    print_separator()
    print(f"  {label}")
    print(f"  {'-' * len(label)}")
    print(f"  Context: {description}")
    print_separator()


def print_response(query: str, data: dict, elapsed: float):
    print(f"\n  Query:    \"{query}\"")
    print(f"  Latency:  {elapsed:.2f}s")
    print()

    if "response" in data:
        print("  Response:")
        for line in data["response"].split("\n"):
            print(f"    {line}")
        print()

    if data.get("actions_taken"):
        print("  Actions Taken:")
        for action in data["actions_taken"]:
            status_icon = "✓" if action["status"] == "success" else "✗" if action["status"] == "failed" else "?"
            detail = f" — {action.get('detail', '')}" if action.get("detail") else ""
            print(f"    {status_icon} [{action['service']}] {action['action']}{detail}")
        print()


async def check_health():
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{BASE_URL}/health", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False


async def run_query(client: httpx.AsyncClient, query: str, conversation_id: str | None = None) -> tuple[dict, float]:
    body = {"query": query}
    if conversation_id:
        body["conversation_id"] = conversation_id

    start = time.time()
    resp = await client.post(
        f"{BASE_URL}/api/v1/query",
        json=body,
        headers={"X-User-Id": USER_ID, "Content-Type": "application/json"},
        timeout=30.0,
    )
    elapsed = time.time() - start

    if resp.status_code != 200:
        return {"error": resp.text, "status_code": resp.status_code}, elapsed

    return resp.json(), elapsed


async def main():
    print("\n" + "╔" + "═" * 70 + "╗")
    print("║" + "  Google Workspace Orchestrator — Live Demo".center(70) + "║")
    print("╚" + "═" * 70 + "╝")

    # Health check
    healthy = await check_health()
    if not healthy:
        print("\n  ERROR: Server not running at", BASE_URL)
        print("  Start it with: uv run uvicorn app.main:app --reload")
        sys.exit(1)
    print(f"\n  Server healthy at {BASE_URL}")

    conversation_id = None

    async with httpx.AsyncClient() as client:
        for i, demo in enumerate(DEMO_QUERIES):
            print_header(demo["label"], demo["description"])

            input("  Press Enter to run this query...")

            data, elapsed = await run_query(client, demo["query"], conversation_id)

            if "error" in data:
                print(f"\n  ERROR ({data.get('status_code', '?')}): {data['error'][:200]}")
            else:
                print_response(demo["query"], data, elapsed)
                conversation_id = data.get("conversation_id")

    print_separator()
    print("  Demo complete!")
    print_separator()


if __name__ == "__main__":
    asyncio.run(main())
