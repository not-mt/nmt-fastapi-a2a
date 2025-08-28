# -*- coding: utf-8 -*-
# Copyright (c) 2025. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root for details.

"""Unit tests for the Widgets MCP agent implementation."""

from types import SimpleNamespace

import httpx
import instructor
import pytest

from app.agents.middleware import OAUTH_TOKEN_CTX
from app.agents.widgets.agent import WidgetsMCPAgent
from app.settings import (
    Agent2AgentSettings,
    AgentSettings,
    AppSettings,
    DirectorSettings,
    LLMProviderSettings,
)


class DummyInstructorClient:
    class chat:
        class completions:
            @staticmethod
            def create(*args, **kwargs):
                # Not used by widgets tests, but keep shape
                return SimpleNamespace()


class DummySession:
    def __init__(self, call_tool_result=None, list_tools_result=None, to_raise=None):
        self._call_result = call_tool_result
        self._list_tools = list_tools_result or SimpleNamespace(tools=[])
        self._to_raise = to_raise

    async def initialize(self):
        if self._to_raise:
            raise self._to_raise

    async def list_tools(self):
        return self._list_tools

    async def call_tool(self, name, arguments):
        # If we were given an ExceptionGroup, return it so the outer
        # `except* httpx.ConnectError` in the agent can match it. For
        # other Exceptions, raise them to simulate immediate error.
        if isinstance(self._call_result, ExceptionGroup):
            return self._call_result
        if isinstance(self._call_result, Exception):
            raise self._call_result
        return self._call_result


class DummyStreamableCtx:
    def __init__(self, session, recorder=None, raise_on_enter=None):
        self._session = session
        self._recorder = recorder
        self._raise_on_enter = raise_on_enter

    async def __aenter__(self):
        if self._raise_on_enter:
            raise self._raise_on_enter
        # return (read_stream, write_stream, get_session_id)
        return (None, None, lambda: "sid")

    async def __aexit__(self, exc_type, exc, tb):
        return False


class DummyClientSessionCtx:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.fixture
def widgets_agent(monkeypatch):
    # Build a minimal, real AppSettings instance for tests so linters and
    # type-checkers can verify the correct shapes instead of using SimpleNamespace.
    settings = AppSettings(
        a2a=Agent2AgentSettings(
            director_url="http://localhost",
            director=DirectorSettings(
                host="localhost", port=10010, agents={"widgets": "http://mcp"}
            ),
            agents={
                "widgets": AgentSettings(
                    host="localhost", port=10020, mcp_url="http://mcp"
                )
            },
            llm_provider=LLMProviderSettings(name="prov", base_url="http://llm"),
        )
    )

    monkeypatch.setattr(
        instructor, "from_provider", lambda *a, **k: DummyInstructorClient()
    )
    # Use very small stand-ins for response types used in agent code; these are
    # bound to names the agent references during runtime but do not need to be
    # full implementations for unit tests.
    from types import SimpleNamespace as _SN

    monkeypatch.setattr("app.agents.widgets.agent.CallToolResult", _SN)
    monkeypatch.setattr("app.agents.widgets.agent.TextContent", _SN)
    return WidgetsMCPAgent(settings)


@pytest.mark.asyncio
async def test_stream_not_initialized(widgets_agent):
    widgets_agent.initialized = False
    results = [r async for r in widgets_agent.stream("q", "s1")]
    assert any("Agent initialization failed" in r["content"] for r in results)


@pytest.mark.asyncio
async def test_stream_success(monkeypatch, widgets_agent):
    # Build a successful CallToolResult-like object (SimpleNamespace)
    call_res = SimpleNamespace(isError=False, content=[SimpleNamespace(text="hello")])

    # patch ClientSession context manager to return a DummySession
    session = DummySession(call_tool_result=call_res)
    monkeypatch.setattr(
        "app.agents.widgets.agent.streamablehttp_client",
        lambda url, headers=None: DummyStreamableCtx(session),
    )
    monkeypatch.setattr(
        "app.agents.widgets.agent.ClientSession",
        lambda read, write: DummyClientSessionCtx(session),
    )

    # ensure tool selection returns a usable tool name and args
    monkeypatch.setattr(
        widgets_agent,
        "_select_tool",
        lambda tools, q: SimpleNamespace(tool_name="tool", args={}),
    )

    OAUTH_TOKEN_CTX.set(None)
    results = [r async for r in widgets_agent.stream("q", "s1")]
    assert any("Processing request" in r["content"] for r in results)
    assert any("hello" in r["content"] for r in results)


@pytest.mark.asyncio
async def test_stream_tool_error(monkeypatch, widgets_agent):
    call_res = SimpleNamespace(isError=True, content=[SimpleNamespace(text="failed")])
    session = DummySession(call_tool_result=call_res)
    monkeypatch.setattr(
        "app.agents.widgets.agent.streamablehttp_client",
        lambda url, headers=None: DummyStreamableCtx(session),
    )
    monkeypatch.setattr(
        "app.agents.widgets.agent.ClientSession",
        lambda read, write: DummyClientSessionCtx(session),
    )
    monkeypatch.setattr(
        widgets_agent,
        "_select_tool",
        lambda tools, q: SimpleNamespace(tool_name="tool", args={}),
    )
    OAUTH_TOKEN_CTX.set(None)
    results = [r async for r in widgets_agent.stream("q", "s1")]
    assert any("Tool call failed" in r["content"] for r in results)


@pytest.mark.asyncio
async def test_stream_connect_error(monkeypatch, widgets_agent):
    # simulate call_tool raising an ExceptionGroup containing ConnectError
    eg = ExceptionGroup("eg", [httpx.ConnectError("conn")])
    session = DummySession(call_tool_result=None)
    # raise the ExceptionGroup on entering the streamable client so the
    # outer `except* httpx.ConnectError` handler in the agent can catch it.
    monkeypatch.setattr(
        "app.agents.widgets.agent.streamablehttp_client",
        lambda url, headers=None: DummyStreamableCtx(session, raise_on_enter=eg),
    )
    monkeypatch.setattr(
        "app.agents.widgets.agent.ClientSession",
        lambda read, write: DummyClientSessionCtx(session),
    )
    # selection not reached, but keep safe stub
    monkeypatch.setattr(
        widgets_agent,
        "_select_tool",
        lambda tools, q: SimpleNamespace(tool_name="tool", args={}),
    )
    OAUTH_TOKEN_CTX.set(None)
    results = [r async for r in widgets_agent.stream("q", "s1")]
    assert any("Error connecting to MCP server" in r["content"] for r in results)


@pytest.mark.asyncio
async def test_stream_generic_exception(monkeypatch, widgets_agent):
    eg = ExceptionGroup("eg", [Exception("boom")])
    session = DummySession(call_tool_result=eg)
    monkeypatch.setattr(
        "app.agents.widgets.agent.streamablehttp_client",
        lambda url, headers=None: DummyStreamableCtx(session),
    )
    monkeypatch.setattr(
        "app.agents.widgets.agent.ClientSession",
        lambda read, write: DummyClientSessionCtx(session),
    )
    monkeypatch.setattr(
        widgets_agent,
        "_select_tool",
        lambda tools, q: SimpleNamespace(tool_name="tool", args={}),
    )
    OAUTH_TOKEN_CTX.set(None)
    results = [r async for r in widgets_agent.stream("q", "s1")]
    assert any("Error processing request" in r["content"] for r in results)


@pytest.mark.asyncio
async def test_headers_forwarded(monkeypatch, widgets_agent):
    recorded = {}

    def fake_streamable(url, headers=None):
        recorded["headers"] = headers
        return DummyStreamableCtx(
            DummySession(
                call_tool_result=SimpleNamespace(
                    isError=False, content=[SimpleNamespace(text="ok")]
                )
            )
        )

    monkeypatch.setattr(
        "app.agents.widgets.agent.streamablehttp_client", fake_streamable
    )
    monkeypatch.setattr(
        "app.agents.widgets.agent.ClientSession",
        lambda read, write: DummyClientSessionCtx(
            DummySession(
                call_tool_result=SimpleNamespace(
                    isError=False, content=[SimpleNamespace(text="ok")]
                )
            )
        ),
    )

    # ensure selection returns a tool to call
    monkeypatch.setattr(
        widgets_agent,
        "_select_tool",
        lambda q: SimpleNamespace(tool_name="tool", args={}),
    )

    OAUTH_TOKEN_CTX.set("Bearer tok123")
    [r async for r in widgets_agent.stream("q", "s1")]
    assert recorded.get("headers") == {"Authorization": "Bearer tok123"}


def test_render_tools_prompt_and_select(monkeypatch):
    # create a minimal agent without touching network clients
    settings = AppSettings(
        a2a=Agent2AgentSettings(
            director_url="http://localhost",
            director=DirectorSettings(
                host="localhost", port=10010, agents={"widgets": "http://mcp"}
            ),
            agents={
                "widgets": AgentSettings(
                    host="localhost", port=10020, mcp_url="http://mcp"
                )
            },
            llm_provider=LLMProviderSettings(name="prov", base_url="http://llm"),
        )
    )
    monkeypatch.setattr(
        instructor, "from_provider", lambda *a, **k: DummyInstructorClient()
    )
    agent = WidgetsMCPAgent(settings)

    # test render with a fake tool
    # A lightweight tool-like object for rendering tests. The call below passes
    # this object into `_render_tools_prompt` which expects objects shaped like
    # the MCP `Tool` model; silence the type checker for that call.
    class _ToolLike:
        def __init__(self, name, description, inputSchema):
            self.name = name
            self.description = description
            self.inputSchema = inputSchema

    tool = _ToolLike(name="t1", description="desc", inputSchema="{}")
    rendered = agent._render_tools_prompt([tool], "what?")  # type: ignore[arg-type]
    assert "t1" in rendered and "what?" in rendered

    # test _select_tool: monkeypatch the client's create to return a ToolCall model
    from app.agents.widgets.agent import ToolCall

    tc = ToolCall(tool_name="chosen", args={})

    class FakeClient:
        class chat:
            class completions:
                @staticmethod
                def create(*args, **kwargs):
                    return tc

    monkeypatch.setattr(instructor, "from_provider", lambda *a, **k: FakeClient())
    agent.client = instructor.from_provider("x")
    sel = agent._select_tool([], "q")
    assert sel.tool_name == "chosen"


def test_discover_mcp_tools_error(monkeypatch):
    # Ensure _discover_mcp_tools returns [] when session.list_tools raises
    settings = AppSettings(
        a2a=Agent2AgentSettings(
            director_url="http://localhost",
            director=DirectorSettings(
                host="localhost", port=10010, agents={"widgets": "http://mcp"}
            ),
            agents={
                "widgets": AgentSettings(
                    host="localhost", port=10020, mcp_url="http://mcp"
                )
            },
            llm_provider=LLMProviderSettings(name="prov", base_url="http://llm"),
        )
    )
    monkeypatch.setattr(
        instructor, "from_provider", lambda *a, **k: DummyInstructorClient()
    )
    agent = WidgetsMCPAgent(settings)

    class BadSession:
        async def list_tools(self):
            raise RuntimeError("boom")

    # call discovery — this passes a test stub where the production API expects
    # a ClientSession; silence the type-checker about the arg type only for this call.
    import asyncio

    got = asyncio.get_event_loop().run_until_complete(
        agent._discover_mcp_tools(BadSession())  # type: ignore[arg-type]
    )
    assert got == []


@pytest.mark.asyncio
async def test_stream_call_tool_raises(monkeypatch, widgets_agent):
    """
    When session.call_tool raises a normal Exception, the inner except
    branch should execute (logging) and subsequent assertion will fail —
    ensure the generator raises (AssertionError) so the code branch is covered.
    """
    session = DummySession(call_tool_result=RuntimeError("boom"))
    monkeypatch.setattr(
        "app.agents.widgets.agent.streamablehttp_client",
        lambda url, headers=None: DummyStreamableCtx(session),
    )
    monkeypatch.setattr(
        "app.agents.widgets.agent.ClientSession",
        lambda read, write: DummyClientSessionCtx(session),
    )
    monkeypatch.setattr(
        widgets_agent,
        "_select_tool",
        lambda tools, q: SimpleNamespace(tool_name="tool", args={}),
    )
    OAUTH_TOKEN_CTX.set(None)

    # collect results and assert an error-like message is present
    results = [r async for r in widgets_agent.stream("q", "s1")]
    assert any("Error" in r["content"] for r in results)


def test_invoke_raises_not_implemented(widgets_agent):
    with pytest.raises(NotImplementedError):
        widgets_agent.invoke("q", "s1")
