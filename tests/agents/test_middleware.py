# -*- coding: utf-8 -*-
# Copyright (c) 2025. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root for details.

import pytest
from starlette.requests import Request
from starlette.responses import Response

from app.agents.middleware import OAUTH_TOKEN_CTX, OAuthTokenMiddleware


class MinimalASGIApp:
    def __init__(self, response):
        self.response = response

    async def __call__(self, scope, receive, send):
        await self.response(scope, receive, send)


def build_request(headers=None):
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [
            (k.lower().encode(), v.encode()) for k, v in (headers or {}).items()
        ],
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_oauth_token_middleware_sets_token():
    token = "Bearer test-token"
    headers = {"authorization": token}
    request = build_request(headers)
    response = Response("ok")
    app = MinimalASGIApp(response)
    middleware = OAuthTokenMiddleware(app=app)

    async def call_next(req):
        return response

    # Reset context before test
    OAUTH_TOKEN_CTX.set(None)
    await middleware.dispatch(request, call_next)
    assert OAUTH_TOKEN_CTX.get() == token


@pytest.mark.asyncio
async def test_oauth_token_middleware_no_auth():
    request = build_request()
    response = Response("ok")
    app = MinimalASGIApp(response)
    middleware = OAuthTokenMiddleware(app=app)

    async def call_next(req):
        return response

    # Reset context before test
    OAUTH_TOKEN_CTX.set(None)
    await middleware.dispatch(request, call_next)
    assert OAUTH_TOKEN_CTX.get() is None
