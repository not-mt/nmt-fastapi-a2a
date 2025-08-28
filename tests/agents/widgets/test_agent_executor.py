# -*- coding: utf-8 -*-
# Copyright (c) 2025. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root for details.

"""Tests for the widgets agent executor behavior."""

from typing import Any, cast

import pytest
from a2a.types import Message, Part, TextPart
from a2a.utils import new_task

from app.agents.widgets.agent_executor import MCPAgentExecutor


class DummyContext:
    def __init__(self, message=None, user_input="q"):
        self.message = message
        self._user_input = user_input
        self.current_task: Any = None

    def get_user_input(self):
        return self._user_input


class DummyEventQueue:
    def __init__(self):
        self.events = []

    async def enqueue_event(self, event):
        self.events.append(event)


class DummyAgent:
    def __init__(self, items):
        self._items = items

    async def stream(self, query, sessionId):
        for it in self._items:
            yield it


def test_widgets_executor_init(monkeypatch):
    """
    Instantiating MCPAgentExecutor should create the agent attribute.
    """

    class DummyWidgetAgent:
        instantiated = False

        def __init__(self, settings):
            DummyWidgetAgent.instantiated = True

    monkeypatch.setattr(
        "app.agents.widgets.agent_executor.WidgetsMCPAgent",
        DummyWidgetAgent,
    )

    from app.agents.widgets.agent_executor import MCPAgentExecutor
    from app.settings import AppSettings

    exec = MCPAgentExecutor(AppSettings())
    assert getattr(exec, "agent", None) is not None
    assert DummyWidgetAgent.instantiated


@pytest.mark.asyncio
async def test_execute_progress_and_completion(monkeypatch):
    executor = MCPAgentExecutor.__new__(MCPAgentExecutor)
    executor.agent = cast(
        Any,
        DummyAgent(
            [
                {
                    "is_task_complete": False,
                    "require_user_input": False,
                    "content": "working1",
                },
                {
                    "is_task_complete": True,
                    "require_user_input": False,
                    "content": "final",
                },
            ]
        ),
    )

    msg = Message(role="user", parts=[Part(root=TextPart(text="hi"))], message_id="m1")  # type: ignore[arg-type]
    ctx = DummyContext(message=msg)
    eq = DummyEventQueue()

    await executor.execute(cast(Any, ctx), cast(Any, eq))

    types = [type(e) for e in eq.events]
    assert any("TaskStatusUpdateEvent" in str(t) for t in types)
    assert any("TaskArtifactUpdateEvent" in str(t) for t in types)


@pytest.mark.asyncio
async def test_execute_input_required(monkeypatch):
    executor = MCPAgentExecutor.__new__(MCPAgentExecutor)
    executor.agent = cast(
        Any,
        DummyAgent(
            [
                {
                    "is_task_complete": False,
                    "require_user_input": True,
                    "content": "please input",
                },
            ]
        ),
    )
    ctx = DummyContext(
        message=Message(
            role="user", parts=[Part(root=TextPart(text="hi"))], message_id="m2"  # type: ignore[arg-type]
        )
    )
    eq = DummyEventQueue()
    await executor.execute(cast(Any, ctx), cast(Any, eq))
    assert any("TaskStatusUpdateEvent" in str(type(e)) for e in eq.events)


@pytest.mark.asyncio
async def test_execute_with_existing_task(monkeypatch):
    executor = MCPAgentExecutor.__new__(MCPAgentExecutor)
    executor.agent = cast(
        Any,
        DummyAgent(
            [
                {
                    "is_task_complete": False,
                    "require_user_input": False,
                    "content": "working",
                },
                {
                    "is_task_complete": True,
                    "require_user_input": False,
                    "content": "done",
                },
            ]
        ),
    )
    msg = Message(role="user", parts=[Part(root=TextPart(text="hi"))], message_id="mx")  # type: ignore[arg-type]
    task = new_task(msg)
    ctx = DummyContext(message=msg)
    ctx.current_task = task
    eq = DummyEventQueue()
    await executor.execute(cast(Any, ctx), cast(Any, eq))
    assert any("TaskArtifactUpdateEvent" in str(type(e)) for e in eq.events)


@pytest.mark.asyncio
async def test_cancel_raises():
    executor = MCPAgentExecutor.__new__(MCPAgentExecutor)
    # directly await the coroutine inside the async test and assert it raises
    with pytest.raises(Exception):
        await executor.cancel(cast(Any, None), cast(Any, None))
