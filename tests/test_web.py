# -*- coding: utf-8 -*-
# Copyright (c) 2025. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root for details.

"""Tests for web websocket and HTTP endpoints."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient

from app.web import app, websocket_endpoint


@pytest.mark.asyncio
async def test_websocket_endpoint_disconnect_branch(monkeypatch):
    websocket = AsyncMock()
    websocket.accept = AsyncMock()
    websocket.receive_json = AsyncMock(side_effect=WebSocketDisconnect)
    websocket.send_text = AsyncMock()

    monkeypatch.setattr("app.web.settings", MagicMock())
    monkeypatch.setattr("app.web.templates", MagicMock())

    # Should not raise, just pass on disconnect
    await websocket_endpoint(websocket)
    websocket.accept.assert_called_once()


@pytest.mark.asyncio
async def test_websocket_endpoint_streaming_exception_in_loop(monkeypatch):
    websocket = AsyncMock()
    websocket.receive_json = AsyncMock(
        side_effect=[
            {"user_input": "Hello", "oauth_token": None},
            asyncio.CancelledError,
        ]
    )
    websocket.accept = AsyncMock()
    websocket.send_text = AsyncMock()

    monkeypatch.setattr("app.web.settings", MagicMock())
    monkeypatch.setattr("app.web.templates", MagicMock())
    mock_client_cm = MagicMock()
    mock_client_cm.__aenter__.return_value = MagicMock()
    monkeypatch.setattr("app.web.httpx.AsyncClient", lambda **kwargs: mock_client_cm)
    mock_resolver = AsyncMock()
    mock_resolver.get_agent_card = AsyncMock(return_value="agent_card")
    monkeypatch.setattr("app.web.A2ACardResolver", lambda **kwargs: mock_resolver)

    async def broken_streaming(_):
        raise Exception("Stream error in loop")
        yield  # unreachable

    mock_client = MagicMock()
    mock_client.send_message_streaming = broken_streaming
    monkeypatch.setattr("app.web.A2AClient", lambda **kwargs: mock_client)

    mock_template = MagicMock()
    mock_template.render.return_value = "<div>Agent response</div>"
    mock_templates = MagicMock()
    mock_templates.get_template.return_value = mock_template
    monkeypatch.setattr("app.web.templates", mock_templates)

    with pytest.raises(asyncio.CancelledError):
        await websocket_endpoint(websocket)
    websocket.send_text.assert_any_call(
        '<div class="msg agent">Error contacting agent: Stream error in loop</div>'
    )


@pytest.mark.asyncio
async def test_websocket_endpoint_no_result(monkeypatch):
    websocket = AsyncMock()
    websocket.receive_json = AsyncMock(
        side_effect=[
            {"user_input": "Hello", "oauth_token": None},
            asyncio.CancelledError,
        ]
    )
    websocket.accept = AsyncMock()
    websocket.send_text = AsyncMock()

    monkeypatch.setattr("app.web.settings", MagicMock())
    monkeypatch.setattr("app.web.templates", MagicMock())
    mock_client_cm = MagicMock()
    mock_client_cm.__aenter__.return_value = MagicMock()
    monkeypatch.setattr("app.web.httpx.AsyncClient", lambda **kwargs: mock_client_cm)
    mock_resolver = AsyncMock()
    mock_resolver.get_agent_card = AsyncMock(return_value="agent_card")
    monkeypatch.setattr("app.web.A2ACardResolver", lambda **kwargs: mock_resolver)

    mock_stream_chunk = MagicMock()
    mock_stream_chunk.model_dump.return_value = {}

    async def mock_streaming(_):
        yield mock_stream_chunk

    mock_client = MagicMock()
    mock_client.send_message_streaming = mock_streaming
    monkeypatch.setattr("app.web.A2AClient", lambda **kwargs: mock_client)

    mock_template = MagicMock()
    mock_template.render.return_value = "<div>Edge case</div>"
    mock_templates = MagicMock()
    mock_templates.get_template.return_value = mock_template
    monkeypatch.setattr("app.web.templates", mock_templates)

    with pytest.raises(asyncio.CancelledError):
        await websocket_endpoint(websocket)
    # Should not send any text since result is missing
    websocket.send_text.assert_not_called()


def test_index_route_renders_chat(monkeypatch):
    # Patch the template rendering to return a valid HTML string
    from app.web import templates

    mock_template = MagicMock()
    mock_template.render.return_value = "<html><body>Chat</body></html>"
    monkeypatch.setattr(
        templates, "get_template", MagicMock(return_value=mock_template)
    )
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "Chat" in response.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "chunk_dict,result,artifact,expected_content,should_send",
    [
        ({"result": None}, None, None, "{'result': None}", False),
        ({}, None, None, "{}", False),
        (
            {"result": {"lastChunk": True}},
            {"lastChunk": True},
            None,
            "{'result': {'lastChunk': True}}",
            True,
        ),
        (
            {"result": {"lastChunk": True, "artifact": {"parts": []}}},
            {"lastChunk": True, "artifact": {"parts": []}},
            {"parts": []},
            "{'result': {'lastChunk': True, 'artifact': {'parts': []}}}",
            True,
        ),
    ],
)
async def test_websocket_endpoint_edge_cases(
    monkeypatch, chunk_dict, result, artifact, expected_content, should_send
):
    websocket = AsyncMock()
    websocket.receive_json = AsyncMock(
        side_effect=[
            {"user_input": "Hello", "oauth_token": None},
            asyncio.CancelledError,
        ]
    )
    websocket.accept = AsyncMock()
    websocket.send_text = AsyncMock()
    monkeypatch.setattr("app.web.settings", MagicMock())
    monkeypatch.setattr("app.web.templates", MagicMock())
    mock_client_cm = MagicMock()
    mock_client_cm.__aenter__.return_value = MagicMock()
    monkeypatch.setattr("app.web.httpx.AsyncClient", lambda **kwargs: mock_client_cm)

    mock_resolver = AsyncMock()
    mock_resolver.get_agent_card = AsyncMock(return_value="agent_card")
    monkeypatch.setattr("app.web.A2ACardResolver", lambda **kwargs: mock_resolver)

    mock_stream_chunk = MagicMock()
    mock_stream_chunk.model_dump.return_value = {
        "result": {
            "lastChunk": True,
            "artifact": {"parts": [{"kind": "text", "text": "Agent response"}]},
        }
    }

    async def mock_streaming(_):
        yield mock_stream_chunk

    mock_client = MagicMock()
    mock_client.send_message_streaming = mock_streaming
    monkeypatch.setattr("app.web.A2AClient", lambda **kwargs: mock_client)

    mock_template = MagicMock()
    mock_template.render.return_value = "<div>Agent response</div>"
    mock_templates = MagicMock()
    mock_templates.get_template.return_value = mock_template
    monkeypatch.setattr("app.web.templates", mock_templates)

    with pytest.raises(asyncio.CancelledError):
        await websocket_endpoint(websocket)


@pytest.mark.asyncio
async def test_websocket_endpoint_error(monkeypatch):
    websocket = AsyncMock()
    websocket.receive_json = AsyncMock(
        side_effect=[
            {"user_input": "Hello", "oauth_token": None},
            asyncio.CancelledError,
        ]
    )
    websocket.accept = AsyncMock()
    websocket.send_text = AsyncMock()

    monkeypatch.setattr("app.web.settings", MagicMock())
    monkeypatch.setattr("app.web.templates", MagicMock())
    mock_client_cm = MagicMock()
    mock_client_cm.__aenter__.return_value = MagicMock()
    monkeypatch.setattr("app.web.httpx.AsyncClient", lambda **kwargs: mock_client_cm)
    mock_resolver = AsyncMock()
    mock_resolver.get_agent_card = AsyncMock(return_value="agent_card")
    monkeypatch.setattr("app.web.A2ACardResolver", lambda **kwargs: mock_resolver)

    # Simulate error in send_message_streaming
    def raise_exc(_):
        raise Exception("Agent error")

    mock_client = MagicMock()
    mock_client.send_message_streaming = raise_exc
    monkeypatch.setattr("app.web.A2AClient", lambda **kwargs: mock_client)

    mock_template = MagicMock()
    mock_template.render.return_value = "<div>Agent response</div>"
    mock_templates = MagicMock()
    mock_templates.get_template.return_value = mock_template
    monkeypatch.setattr("app.web.templates", mock_templates)

    with pytest.raises(asyncio.CancelledError):
        await websocket_endpoint(websocket)

    websocket.send_text.assert_any_call(
        '<div class="msg agent">Error contacting agent: Agent error</div>'
    )


@pytest.mark.asyncio
async def test_websocket_endpoint_disconnect(monkeypatch):
    websocket = AsyncMock()
    websocket.accept = AsyncMock()
    websocket.receive_json = AsyncMock(side_effect=WebSocketDisconnect)
    websocket.send_text = AsyncMock()

    monkeypatch.setattr("app.web.settings", MagicMock())
    monkeypatch.setattr("app.web.templates", MagicMock())

    # Should not raise, just pass on disconnect
    await websocket_endpoint(websocket)
    websocket.accept.assert_called_once()


@pytest.mark.asyncio
async def test_websocket_endpoint_artifact_no_text(monkeypatch):
    websocket = AsyncMock()
    websocket.receive_json = AsyncMock(
        side_effect=[
            {"user_input": "Hello", "oauth_token": None},
            asyncio.CancelledError,
        ]
    )
    websocket.accept = AsyncMock()
    websocket.send_text = AsyncMock()
    monkeypatch.setattr("app.web.settings", MagicMock())
    monkeypatch.setattr("app.web.templates", MagicMock())
    mock_client_cm = MagicMock()
    mock_client_cm.__aenter__.return_value = MagicMock()
    monkeypatch.setattr("app.web.httpx.AsyncClient", lambda **kwargs: mock_client_cm)
    mock_resolver = AsyncMock()
    mock_resolver.get_agent_card = AsyncMock(return_value="agent_card")
    monkeypatch.setattr("app.web.A2ACardResolver", lambda **kwargs: mock_resolver)

    # Chunk with artifact, but no text part
    mock_stream_chunk = MagicMock()
    chunk_dict = {
        "result": {
            "lastChunk": True,
            "artifact": {
                "parts": [
                    {"kind": "image", "url": "some_url"},
                    {"kind": "text"},  # No 'text' key
                ]
            },
        }
    }
    mock_stream_chunk.model_dump.return_value = chunk_dict

    async def mock_streaming(_):
        yield mock_stream_chunk

    mock_client = MagicMock()
    mock_client.send_message_streaming = mock_streaming
    monkeypatch.setattr("app.web.A2AClient", lambda **kwargs: mock_client)

    mock_template = MagicMock()
    mock_template.render.return_value = "<div>Fallback</div>"
    mock_templates = MagicMock()
    mock_templates.get_template.return_value = mock_template
    monkeypatch.setattr("app.web.templates", mock_templates)

    with pytest.raises(asyncio.CancelledError):
        await websocket_endpoint(websocket)
    # Should send fallback content (str(chunk_dict))
    websocket.send_text.assert_any_call("<div>Fallback</div>")


@pytest.mark.asyncio
async def test_websocket_endpoint_no_oauth_token(monkeypatch):
    websocket = AsyncMock()
    websocket.receive_json = AsyncMock(
        side_effect=[{"user_input": "Hello"}, asyncio.CancelledError]
    )
    websocket.accept = AsyncMock()
    websocket.send_text = AsyncMock()
    monkeypatch.setattr("app.web.settings", MagicMock())
    monkeypatch.setattr("app.web.templates", MagicMock())
    mock_client_cm = MagicMock()
    mock_client_cm.__aenter__.return_value = MagicMock()
    monkeypatch.setattr("app.web.httpx.AsyncClient", lambda **kwargs: mock_client_cm)
    mock_resolver = AsyncMock()
    mock_resolver.get_agent_card = AsyncMock(return_value="agent_card")
    monkeypatch.setattr("app.web.A2ACardResolver", lambda **kwargs: mock_resolver)

    # Chunk with lastChunk True, but no artifact
    mock_stream_chunk = MagicMock()
    chunk_dict = {
        "result": {
            "lastChunk": True
            # No artifact key
        }
    }
    mock_stream_chunk.model_dump.return_value = chunk_dict

    async def mock_streaming(_):
        yield mock_stream_chunk

    mock_client = MagicMock()
    mock_client.send_message_streaming = mock_streaming
    monkeypatch.setattr("app.web.A2AClient", lambda **kwargs: mock_client)

    mock_template = MagicMock()
    mock_template.render.return_value = "<div>Fallback no artifact</div>"
    mock_templates = MagicMock()
    mock_templates.get_template.return_value = mock_template
    monkeypatch.setattr("app.web.templates", mock_templates)

    with pytest.raises(asyncio.CancelledError):
        await websocket_endpoint(websocket)
    # Should send fallback content (str(chunk_dict))
    websocket.send_text.assert_any_call("<div>Fallback no artifact</div>")


@pytest.mark.asyncio
async def test_websocket_endpoint_minimal_headers(monkeypatch):
    websocket = AsyncMock()
    # Only user_input, no oauth_token key at all
    websocket.receive_json = AsyncMock(
        side_effect=[{"user_input": "Minimal"}, asyncio.CancelledError]
    )
    websocket.accept = AsyncMock()
    websocket.send_text = AsyncMock()
    monkeypatch.setattr("app.web.settings", MagicMock())
    monkeypatch.setattr("app.web.templates", MagicMock())
    mock_client_cm = MagicMock()
    mock_client_cm.__aenter__.return_value = MagicMock()
    monkeypatch.setattr("app.web.httpx.AsyncClient", lambda **kwargs: mock_client_cm)
    mock_resolver = AsyncMock()
    mock_resolver.get_agent_card = AsyncMock(return_value="agent_card")
    monkeypatch.setattr("app.web.A2ACardResolver", lambda **kwargs: mock_resolver)

    # Chunk with lastChunk True, but no artifact
    mock_stream_chunk = MagicMock()
    chunk_dict = {"result": {"lastChunk": True}}
    mock_stream_chunk.model_dump.return_value = chunk_dict

    async def mock_streaming(_):
        yield mock_stream_chunk

    mock_client = MagicMock()
    mock_client.send_message_streaming = mock_streaming
    monkeypatch.setattr("app.web.A2AClient", lambda **kwargs: mock_client)

    mock_template = MagicMock()
    mock_template.render.return_value = "<div>Minimal fallback</div>"
    mock_templates = MagicMock()
    mock_templates.get_template.return_value = mock_template
    monkeypatch.setattr("app.web.templates", mock_templates)

    with pytest.raises(asyncio.CancelledError):
        await websocket_endpoint(websocket)
    websocket.send_text.assert_any_call("<div>Minimal fallback</div>")


@pytest.mark.asyncio
async def test_websocket_endpoint_with_oauth_token(monkeypatch):
    websocket = AsyncMock()
    # Provide a non-empty oauth_token
    websocket.receive_json = AsyncMock(
        side_effect=[
            {"user_input": "Hello", "oauth_token": "testtoken"},
            asyncio.CancelledError,
        ]
    )
    websocket.accept = AsyncMock()
    websocket.send_text = AsyncMock()
    monkeypatch.setattr("app.web.settings", MagicMock())
    monkeypatch.setattr("app.web.templates", MagicMock())
    mock_client_cm = MagicMock()
    mock_client_cm.__aenter__.return_value = MagicMock()
    monkeypatch.setattr("app.web.httpx.AsyncClient", lambda **kwargs: mock_client_cm)
    mock_resolver = AsyncMock()
    mock_resolver.get_agent_card = AsyncMock(return_value="agent_card")
    monkeypatch.setattr("app.web.A2ACardResolver", lambda **kwargs: mock_resolver)

    # Chunk with lastChunk True, but no artifact
    mock_stream_chunk = MagicMock()
    chunk_dict = {"result": {"lastChunk": True}}
    mock_stream_chunk.model_dump.return_value = chunk_dict

    async def mock_streaming(_):
        yield mock_stream_chunk

    mock_client = MagicMock()
    mock_client.send_message_streaming = mock_streaming
    monkeypatch.setattr("app.web.A2AClient", lambda **kwargs: mock_client)

    mock_template = MagicMock()
    mock_template.render.return_value = "<div>OAuth fallback</div>"
    mock_templates = MagicMock()
    mock_templates.get_template.return_value = mock_template
    monkeypatch.setattr("app.web.templates", mock_templates)

    with pytest.raises(asyncio.CancelledError):
        await websocket_endpoint(websocket)
    websocket.send_text.assert_any_call("<div>OAuth fallback</div>")
