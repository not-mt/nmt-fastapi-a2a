# -*- coding: utf-8 -*-
# Copyright (c) 2025. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root for details.

"""FastAPI web frontend for streaming chat with A2A agents via htmx and WebSockets."""

import logging
from uuid import uuid4

import httpx
from a2a.client import A2ACardResolver, A2AClient
from a2a.types import (
    Message,
    MessageSendParams,
    Part,
    Role,
    SendStreamingMessageRequest,
    TextPart,
)
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.settings import get_app_settings
from app.utils import configure_logging

settings = get_app_settings()

configure_logging(settings)
logger = logging.getLogger(__name__)

app = FastAPI()
templates = Jinja2Templates(directory="src/app/web/templates")
# Mount static directory for htmx (if needed)
# app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """
    Renders the chat template with an empty list of messages.

    Args:
        request: The incoming HTTP request object.

    Returns:
        HTMLResponse: The rendered HTML response for the chat page.
    """
    return templates.TemplateResponse(request=request, name="chat.html")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    Handles a WebSocket connection for streaming agent responses.

    Accepts incoming WebSocket connections, receives JSON-formatted form data
    containing user input and an optional OAuth token, forwards the user input to an
    agent service via HTTP, and streams agent responses back to the client as rendered
    HTML fragments.

    Args:
        websocket: The WebSocket connection instance.

    Returns:
        None: No data is returned directly; communication is handled via the WebSocket.
    """
    await websocket.accept()
    try:
        while True:
            # htmx sends form data as JSON
            data = await websocket.receive_json()
            user_input = data.get("user_input")
            oauth_token = data.get("oauth_token")
            # Ignore previous messages for appending, only send new ones

            headers = {}
            if oauth_token:
                headers["Authorization"] = f"Bearer {oauth_token}"

            async with httpx.AsyncClient(
                base_url=settings.a2a.director_url,
                headers=headers,
            ) as httpx_client:
                resolver = A2ACardResolver(
                    httpx_client=httpx_client,
                    base_url=settings.a2a.director_url,
                )
                agent_card = await resolver.get_agent_card()
                client = A2AClient(httpx_client=httpx_client, agent_card=agent_card)
                msg = Message(
                    role=Role.user,
                    parts=[Part(root=TextPart(text=user_input))],
                    message_id=uuid4().hex,
                )
                streaming_request = SendStreamingMessageRequest(
                    id=str(uuid4()), params=MessageSendParams(message=msg)
                )
                try:
                    stream_response = client.send_message_streaming(streaming_request)
                    # send each chunk as a rendered HTML fragment
                    async for chunk in stream_response:
                        chunk_dict = chunk.model_dump(mode="json", exclude_none=True)
                        result = chunk_dict.get("result")
                        content = ""
                        if result and result.get("lastChunk"):
                            artifact = result.get("artifact")
                            if artifact:
                                parts = artifact.get("parts", [])
                                for part in parts:
                                    if part.get("kind") == "text" and part.get("text"):
                                        content = part["text"]
                                        break
                            if not content:
                                content = str(chunk_dict)
                            # only send the new agent message
                            new_msgs = [("agent", content)]
                            html = templates.get_template("messages.html").render(
                                {"messages": new_msgs}
                            )
                            await websocket.send_text(html)
                except Exception as e:
                    html = f'<div class="msg agent">Error contacting agent: {e}</div>'
                    await websocket.send_text(html)
    except WebSocketDisconnect:
        pass
