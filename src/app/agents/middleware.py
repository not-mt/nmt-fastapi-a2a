# -*- coding: utf-8 -*-
# Copyright (c) 2025. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root for details.

"""Middleware for handling OAuth tokens in agent-to-agent communication."""

import contextvars

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

OAUTH_TOKEN_CTX: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "oauth_token", default=None
)


class OAuthTokenMiddleware(BaseHTTPMiddleware):
    """
    Middleware to extract and inject OAuth tokens into request context.
    """

    async def dispatch(self, request: Request, call_next):
        """
        Intercepts requests to manage OAuth token context.
        """
        token = request.headers.get("authorization")
        if token:
            OAUTH_TOKEN_CTX.set(token)
        response = await call_next(request)
        return response
