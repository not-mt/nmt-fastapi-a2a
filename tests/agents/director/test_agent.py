# -*- coding: utf-8 -*-
# Copyright (c) 2025. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root for details.

"""Unit tests for the DirectorAgent selection and streaming logic."""

import instructor
import pytest

from app.agents import middleware
from app.agents.director.agent import AgentSelectionResult, DirectorAgent
from app.settings import (
    Agent2AgentSettings,
    AgentSettings,
    AppSettings,
    DirectorSettings,
    LLMProviderSettings,
)


class DummyA2AClient:
    def __init__(self, stream_chunks):
        self.stream_chunks = stream_chunks

    def send_message_streaming(self, *args, **kwargs):
        async def gen():
            for chunk in self.stream_chunks:
                yield chunk

        return gen()


class DummyChunk:
    def __init__(self, lastChunk=True, text=None):
        self.lastChunk = lastChunk
        self.text = text

    def model_dump(self, mode=None, exclude_none=None):
        out = {"result": {"lastChunk": self.lastChunk}}
        if self.text is not None:
            out["artifact"] = {"parts": [{"kind": "text", "text": self.text}]}  # type: ignore
        return out


class DummySettings(AppSettings):
    def __init__(self):
        super().__init__(
            a2a=Agent2AgentSettings(
                director_url="http://director",
                director=DirectorSettings(
                    host="localhost", port=10010, agents={"widgets": "http://widgets"}
                ),
                agents={
                    "widgets": AgentSettings(
                        host="localhost", port=10020, mcp_url="http://widgets/mcp/"
                    )
                },
                llm_provider=LLMProviderSettings(
                    name="openai/gpt-4", base_url="http://llm"
                ),
            )
        )


@pytest.fixture
def director_agent(monkeypatch):
    class DummyInstructorClient:
        class chat:
            class completions:
                @staticmethod
                def create(response_model, messages, temperature):
                    return AgentSelectionResult(
                        agent_id="WidgetsAgent", reasoning="widget"
                    )

    monkeypatch.setattr(
        instructor, "from_provider", lambda *args, **kwargs: DummyInstructorClient()
    )
    settings = DummySettings()
    agent = DirectorAgent(settings)
    return agent


def test_select_agent_widgets(monkeypatch, director_agent):
    # Patch instructor client to always return WidgetsAgent
    result = director_agent._select_agent("What is widget 1?")
    assert result.agent_id == "WidgetsAgent"
    assert result.reasoning == "widget"


def test_select_agent_unknown(monkeypatch, director_agent):
    # Patch instructor client to always return UNKNOWN
    director_agent.client.chat.completions.create = staticmethod(
        lambda response_model, messages, temperature: AgentSelectionResult(
            agent_id="UNKNOWN", reasoning="unknown"
        )
    )
    result = director_agent._select_agent("What is foo?")
    assert result.agent_id == "UNKNOWN"
    assert result.reasoning == "unknown"


@pytest.mark.asyncio
async def test_stream_success(monkeypatch, director_agent):
    # Patch _select_agent to return WidgetsAgent
    monkeypatch.setattr(
        director_agent,
        "_select_agent",
        lambda q: AgentSelectionResult(agent_id="WidgetsAgent", reasoning="widget"),
    )
    # Patch a2a_clients to use DummyA2AClient
    chunk = DummyChunk(lastChunk=True, text="Widget response")
    director_agent.a2a_clients["widgets"] = DummyA2AClient([chunk])
    # Set OAUTH_TOKEN_CTX to None before running test
    middleware.OAUTH_TOKEN_CTX.set(None)
    results = []
    async for item in director_agent.stream("What is widget 1?", "session1"):
        results.append(item)
    assert any("Processing request" in r["content"] for r in results)
    assert any("Widget response" in r["content"] for r in results)


@pytest.mark.asyncio
async def test_stream_error(monkeypatch, director_agent):
    monkeypatch.setattr(
        director_agent,
        "_select_agent",
        lambda q: AgentSelectionResult(agent_id="WidgetsAgent", reasoning="widget"),
    )

    class ErrorA2AClient:
        def send_message_streaming(self, *args, **kwargs):
            raise Exception("A2A error")

    director_agent.a2a_clients["widgets"] = ErrorA2AClient()
    middleware.OAUTH_TOKEN_CTX.set(None)
    results = []
    async for item in director_agent.stream("What is widget 1?", "session1"):
        results.append(item)
    assert any("Error processing request" in r["content"] for r in results)


@pytest.mark.asyncio
async def test_stream_not_initialized(monkeypatch, director_agent):
    director_agent.initialized = False
    results = []
    async for item in director_agent.stream("foo", "session1"):
        results.append(item)
    assert any("Agent initialization failed" in r["content"] for r in results)


def test_invoke_raises(director_agent):
    with pytest.raises(NotImplementedError):
        director_agent.invoke("foo", "session1")


@pytest.mark.asyncio
async def test_stream_unknown_agent(monkeypatch, director_agent):
    # Patch _select_agent to return UNKNOWN
    monkeypatch.setattr(
        director_agent,
        "_select_agent",
        lambda q: AgentSelectionResult(agent_id="UNKNOWN", reasoning="unknown"),
    )
    middleware.OAUTH_TOKEN_CTX.set(None)
    results = []
    async for item in director_agent.stream("What is foo?", "session1"):
        results.append(item)
    assert any("Unknown agent_id" in r["content"] for r in results)


@pytest.mark.asyncio
async def test_stream_agent_selection_exception(monkeypatch, director_agent):
    # Patch _select_agent to raise exception
    def raise_exc(q):
        raise RuntimeError("agent selection failed")

    monkeypatch.setattr(director_agent, "_select_agent", raise_exc)
    middleware.OAUTH_TOKEN_CTX.set(None)
    results = []
    async for item in director_agent.stream("fail", "session1"):
        results.append(item)
    assert any("Error processing request" in r["content"] for r in results)


@pytest.mark.asyncio
async def test_stream_outer_exception(monkeypatch, director_agent):
    # Patch _select_agent to return WidgetsAgent
    monkeypatch.setattr(
        director_agent,
        "_select_agent",
        lambda q: AgentSelectionResult(agent_id="WidgetsAgent", reasoning="widget"),
    )

    # Patch a2a_clients to raise exception in send_message_streaming
    class ErrorA2AClient:
        def send_message_streaming(self, *args, **kwargs):
            raise Exception("stream outer error")

    director_agent.a2a_clients["widgets"] = ErrorA2AClient()
    middleware.OAUTH_TOKEN_CTX.set(None)
    results = []
    async for item in director_agent.stream("What is widget 1?", "session1"):
        results.append(item)
    assert any("Error processing request" in r["content"] for r in results)


@pytest.mark.asyncio
async def test_stream_with_token_headers(monkeypatch, director_agent):
    # Ensure headers are forwarded when token present
    monkeypatch.setattr(
        director_agent,
        "_select_agent",
        lambda q: AgentSelectionResult(agent_id="WidgetsAgent", reasoning="widget"),
    )
    recorded = {}

    class RecordingA2AClient:
        def send_message_streaming(self, streaming_request, http_kwargs=None):
            recorded["http_kwargs"] = http_kwargs

            async def gen():
                chunk = DummyChunk(lastChunk=True, text="ok")
                yield chunk

            return gen()

    director_agent.a2a_clients["widgets"] = RecordingA2AClient()
    middleware.OAUTH_TOKEN_CTX.set("Bearer abc123")
    results = []
    async for item in director_agent.stream("q", "s1"):
        results.append(item)
    assert recorded.get("http_kwargs") and recorded["http_kwargs"].get("headers") == {
        "Authorization": "Bearer abc123"
    }


@pytest.mark.asyncio
async def test_stream_artifact_without_text(monkeypatch, director_agent):
    # artifact parts exist but contain no text -> content becomes str(chunk_dict)
    monkeypatch.setattr(
        director_agent,
        "_select_agent",
        lambda q: AgentSelectionResult(agent_id="WidgetsAgent", reasoning="widget"),
    )

    class NoTextChunk:
        def model_dump(self, mode=None, exclude_none=None):
            return {
                "result": {"lastChunk": True},
                "artifact": {"parts": [{"kind": "image", "url": "x"}]},
            }

    director_agent.a2a_clients["widgets"] = DummyA2AClient([NoTextChunk()])
    middleware.OAUTH_TOKEN_CTX.set(None)
    results = []
    async for item in director_agent.stream("q", "s1"):
        results.append(item)
    # final content should include a stringified chunk dict (contains 'lastChunk')
    assert any("lastChunk" in r["content"] for r in results)


@pytest.mark.asyncio
async def test_stream_nested_artifact_with_text(monkeypatch, director_agent):
    # artifact nested under result with a text part -> content should be set to that text
    monkeypatch.setattr(
        director_agent,
        "_select_agent",
        lambda q: AgentSelectionResult(agent_id="WidgetsAgent", reasoning="widget"),
    )

    class NestedArtifactChunk:
        def model_dump(self, mode=None, exclude_none=None):
            return {
                "result": {
                    "lastChunk": True,
                    "artifact": {"parts": [{"kind": "text", "text": "nested text"}]},
                }
            }

    director_agent.a2a_clients["widgets"] = DummyA2AClient([NestedArtifactChunk()])
    middleware.OAUTH_TOKEN_CTX.set(None)
    results = []
    async for item in director_agent.stream("q", "s1"):
        results.append(item)
    assert any("nested text" in r["content"] for r in results)


@pytest.mark.asyncio
async def test_stream_multiple_parts(monkeypatch, director_agent):
    # first part non-text, second part text -> ensures loop continues then breaks on second
    monkeypatch.setattr(
        director_agent,
        "_select_agent",
        lambda q: AgentSelectionResult(agent_id="WidgetsAgent", reasoning="widget"),
    )

    class MultiPartChunk:
        def model_dump(self, mode=None, exclude_none=None):
            return {
                "result": {
                    "lastChunk": True,
                    "artifact": {
                        "parts": [
                            {"kind": "image", "url": "x"},
                            {"kind": "text", "text": "second"},
                        ]
                    },
                }
            }

    director_agent.a2a_clients["widgets"] = DummyA2AClient([MultiPartChunk()])
    middleware.OAUTH_TOKEN_CTX.set(None)
    results = []
    async for item in director_agent.stream("q", "s1"):
        results.append(item)
    assert any("second" in r["content"] for r in results)


@pytest.mark.asyncio
async def test_stream_text_part_missing_text_key(monkeypatch, director_agent):
    # part kind is text but 'text' key missing -> should fallback to stringified chunk
    monkeypatch.setattr(
        director_agent,
        "_select_agent",
        lambda q: AgentSelectionResult(agent_id="WidgetsAgent", reasoning="widget"),
    )

    class MissingTextKeyChunk:
        def model_dump(self, mode=None, exclude_none=None):
            return {
                "result": {"lastChunk": True, "artifact": {"parts": [{"kind": "text"}]}}
            }

    director_agent.a2a_clients["widgets"] = DummyA2AClient([MissingTextKeyChunk()])
    middleware.OAUTH_TOKEN_CTX.set(None)
    results = []
    async for item in director_agent.stream("q", "s1"):
        results.append(item)
    assert any("lastChunk" in r["content"] for r in results)


@pytest.mark.asyncio
async def test_stream_lastchunk_no_artifact(monkeypatch, director_agent):
    # lastChunk True but no artifact -> content becomes str(chunk_dict)
    monkeypatch.setattr(
        director_agent,
        "_select_agent",
        lambda q: AgentSelectionResult(agent_id="WidgetsAgent", reasoning="widget"),
    )

    class ChunkNoArtifact:
        def model_dump(self, mode=None, exclude_none=None):
            return {"result": {"lastChunk": True}}

    director_agent.a2a_clients["widgets"] = DummyA2AClient([ChunkNoArtifact()])
    middleware.OAUTH_TOKEN_CTX.set(None)
    results = []
    async for item in director_agent.stream("q", "s1"):
        results.append(item)
    # final content should include stringified chunk dict
    assert any("lastChunk" in r["content"] for r in results)


@pytest.mark.asyncio
async def test_stream_lastchunk_false(monkeypatch, director_agent):
    # lastChunk False -> inner block skipped, final content empty
    monkeypatch.setattr(
        director_agent,
        "_select_agent",
        lambda q: AgentSelectionResult(agent_id="WidgetsAgent", reasoning="widget"),
    )

    class ChunkNotLast:
        def model_dump(self, mode=None, exclude_none=None):
            return {"result": {"lastChunk": False}}

    director_agent.a2a_clients["widgets"] = DummyA2AClient([ChunkNotLast()])
    middleware.OAUTH_TOKEN_CTX.set(None)
    results = []
    async for item in director_agent.stream("q", "s1"):
        results.append(item)
    # final message should end with an empty content field
    assert any("Agent WidgetsAgent response: " in r["content"] for r in results)


@pytest.mark.asyncio
async def test_stream_artifact_empty_parts(monkeypatch, director_agent):
    # artifact exists but parts is empty -> fallback to stringified chunk
    monkeypatch.setattr(
        director_agent,
        "_select_agent",
        lambda q: AgentSelectionResult(agent_id="WidgetsAgent", reasoning="widget"),
    )

    class EmptyPartsChunk:
        def model_dump(self, mode=None, exclude_none=None):
            return {"result": {"lastChunk": True}, "artifact": {}}

    director_agent.a2a_clients["widgets"] = DummyA2AClient([EmptyPartsChunk()])
    middleware.OAUTH_TOKEN_CTX.set(None)
    results = []
    async for item in director_agent.stream("q", "s1"):
        results.append(item)
    assert any("lastChunk" in r["content"] for r in results)


@pytest.mark.asyncio
async def test_stream_text_part_empty_text(monkeypatch, director_agent):
    # part kind is text but text is empty -> should fallback to stringified chunk
    monkeypatch.setattr(
        director_agent,
        "_select_agent",
        lambda q: AgentSelectionResult(agent_id="WidgetsAgent", reasoning="widget"),
    )

    class EmptyTextChunk:
        def model_dump(self, mode=None, exclude_none=None):
            return {
                "result": {"lastChunk": True},
                "artifact": {"parts": [{"kind": "text", "text": ""}]},
            }

    director_agent.a2a_clients["widgets"] = DummyA2AClient([EmptyTextChunk()])
    middleware.OAUTH_TOKEN_CTX.set(None)
    results = []
    async for item in director_agent.stream("q", "s1"):
        results.append(item)
    assert any("lastChunk" in r["content"] for r in results)
