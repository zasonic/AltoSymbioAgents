"""tests/test_routes_web.py — HTTP-level tests for /api/web routes.

Exercises the real router + BearerAuthMiddleware + request/await wiring via
FastAPI's TestClient. The API object behind the route records the calls and
returns real-shaped envelopes (the WebAPI logic itself is covered end-to-end in
test_web_to_rag_integration.py); here we assert auth, body parsing, and that
async delegators are awaited and surfaced verbatim.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import web as web_routes
from server import BearerAuthMiddleware

TOKEN = "test-token-web"


def _auth():
    return {"Authorization": f"Bearer {TOKEN}"}


class _Api:
    """Stand-in for the API facade exposing the three web methods."""
    def __init__(self):
        self.calls = []

    def web_status(self):
        return {"available": True, "stealth_available": False, "enabled": True}

    async def web_fetch(self, url, use_stealth=False):
        self.calls.append(("fetch", url, use_stealth))
        return {"url": url, "title": "T", "markdown": "# T", "status": 200,
                "engine": "http", "truncated": False}

    async def web_fetch_to_rag(self, url, source="", use_stealth=False):
        self.calls.append(("to_rag", url, source, use_stealth))
        if "blocked" in url:
            return {"error": "blocked by scan", "reason": "blocked"}
        return {"chunks_added": 3, "url": url, "title": "T", "truncated": False}


@pytest.fixture
def app():
    api = _Api()
    a = FastAPI()
    a.add_middleware(BearerAuthMiddleware, expected_token=TOKEN)
    a.include_router(web_routes.router, prefix="/api/web")
    a.state.container = SimpleNamespace(api=api)
    a.state._api = api  # handle for assertions
    return a


def test_status_requires_auth(app):
    client = TestClient(app)
    assert client.get("/api/web/status").status_code == 401


def test_status_ok_with_auth(app):
    client = TestClient(app)
    resp = client.get("/api/web/status", headers=_auth())
    assert resp.status_code == 200
    assert resp.json() == {"available": True, "stealth_available": False, "enabled": True}


def test_fetch_awaits_and_returns_body(app):
    client = TestClient(app)
    resp = client.post("/api/web/fetch", json={"url": "https://example.com"}, headers=_auth())
    assert resp.status_code == 200
    body = resp.json()
    assert body["url"] == "https://example.com"
    assert body["status"] == 200
    assert app.state._api.calls[0] == ("fetch", "https://example.com", False)


def test_fetch_to_rag_returns_chunks(app):
    client = TestClient(app)
    resp = client.post(
        "/api/web/fetch_to_rag",
        json={"url": "https://example.com/doc", "source": "src"},
        headers=_auth(),
    )
    assert resp.status_code == 200
    assert resp.json()["chunks_added"] == 3
    assert app.state._api.calls[0] == ("to_rag", "https://example.com/doc", "src", False)


def test_fetch_to_rag_blocked_envelope(app):
    client = TestClient(app)
    resp = client.post(
        "/api/web/fetch_to_rag", json={"url": "https://blocked.example/x"}, headers=_auth()
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["reason"] == "blocked"
    assert "error" in body
