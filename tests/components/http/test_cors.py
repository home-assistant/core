"""Test cors for the HTTP component."""

from asyncio import AbstractEventLoop
from http import HTTPStatus
from pathlib import Path
from unittest.mock import patch

from aiohttp import web
from aiohttp.hdrs import (
    ACCESS_CONTROL_ALLOW_HEADERS,
    ACCESS_CONTROL_ALLOW_ORIGIN,
    ACCESS_CONTROL_REQUEST_HEADERS,
    ACCESS_CONTROL_REQUEST_METHOD,
    AUTHORIZATION,
    ORIGIN,
)
from aiohttp.test_utils import TestClient
import pytest

from homeassistant.components.http.cors import setup_cors
from homeassistant.components.http.view import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers.http import KEY_ALLOW_CONFIGURED_CORS
from homeassistant.setup import async_setup_component

from . import HTTP_HEADER_HA_AUTH

from tests.typing import ClientSessionGenerator

TRUSTED_ORIGIN = "https://home-assistant.io"


async def test_cors_middleware_loaded_by_default(hass: HomeAssistant) -> None:
    """Test accessing to server from banned IP when feature is off."""
    with patch("homeassistant.components.http.setup_cors") as mock_setup:
        await async_setup_component(hass, "http", {"http": {}})

    assert len(mock_setup.mock_calls) == 1


async def test_cors_middleware_loaded_from_config(hass: HomeAssistant) -> None:
    """Test accessing to server from banned IP when feature is off."""
    with patch("homeassistant.components.http.setup_cors") as mock_setup:
        await async_setup_component(
            hass,
            "http",
            {"http": {"cors_allowed_origins": ["http://home-assistant.io"]}},
        )

    assert len(mock_setup.mock_calls) == 1


async def mock_handler(request):
    """Return if request was authenticated."""
    return web.Response()


@pytest.fixture
def client(
    event_loop: AbstractEventLoop, aiohttp_client: ClientSessionGenerator
) -> TestClient:
    """Fixture to set up a web.Application."""
    app = web.Application()
    setup_cors(app, [TRUSTED_ORIGIN])
    app[KEY_ALLOW_CONFIGURED_CORS](app.router.add_get("/", mock_handler))
    return event_loop.run_until_complete(aiohttp_client(app))


async def test_cors_requests(client) -> None:
    """Test cross origin requests."""
    req = await client.get("/", headers={ORIGIN: TRUSTED_ORIGIN})
    assert req.status == HTTPStatus.OK
    assert req.headers[ACCESS_CONTROL_ALLOW_ORIGIN] == TRUSTED_ORIGIN

    # With password in URL
    req = await client.get(
        "/", params={"api_password": "some-pass"}, headers={ORIGIN: TRUSTED_ORIGIN}
    )
    assert req.status == HTTPStatus.OK
    assert req.headers[ACCESS_CONTROL_ALLOW_ORIGIN] == TRUSTED_ORIGIN

    # With password in headers
    req = await client.get(
        "/", headers={HTTP_HEADER_HA_AUTH: "some-pass", ORIGIN: TRUSTED_ORIGIN}
    )
    assert req.status == HTTPStatus.OK
    assert req.headers[ACCESS_CONTROL_ALLOW_ORIGIN] == TRUSTED_ORIGIN

    # With auth token in headers
    req = await client.get(
        "/", headers={AUTHORIZATION: "Bearer some-token", ORIGIN: TRUSTED_ORIGIN}
    )
    assert req.status == HTTPStatus.OK
    assert req.headers[ACCESS_CONTROL_ALLOW_ORIGIN] == TRUSTED_ORIGIN


async def test_cors_preflight_allowed(client) -> None:
    """Test cross origin resource sharing preflight (OPTIONS) request."""
    req = await client.options(
        "/",
        headers={
            ORIGIN: TRUSTED_ORIGIN,
            ACCESS_CONTROL_REQUEST_METHOD: "GET",
            ACCESS_CONTROL_REQUEST_HEADERS: "x-requested-with",
        },
    )

    assert req.status == HTTPStatus.OK
    assert req.headers[ACCESS_CONTROL_ALLOW_ORIGIN] == TRUSTED_ORIGIN
    assert req.headers[ACCESS_CONTROL_ALLOW_HEADERS] == "X-REQUESTED-WITH"


async def test_cors_middleware_with_cors_allowed_view(hass: HomeAssistant) -> None:
    """Test that we can configure cors and have a cors_allowed view."""

    class MyView(HomeAssistantView):
        """Test view that allows CORS."""

        requires_auth = False
        cors_allowed = True

        def __init__(self, url, name) -> None:
            """Initialize test view."""
            self.url = url
            self.name = name

        async def get(self, request):
            """Test response."""
            return "test"

    assert await async_setup_component(
        hass, "http", {"http": {"cors_allowed_origins": ["http://home-assistant.io"]}}
    )

    hass.http.register_view(MyView("/api/test", "api:test"))
    hass.http.register_view(MyView("/api/test", "api:test2"))
    hass.http.register_view(MyView("/api/test2", "api:test"))

    hass.http.app._on_startup.freeze()
    await hass.http.app.startup()


async def test_cors_works_with_frontend(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test CORS works with the frontend."""
    assert await async_setup_component(
        hass,
        "frontend",
        {"http": {"cors_allowed_origins": ["http://home-assistant.io"]}},
    )
    client = await hass_client()
    resp = await client.get("/")
    assert resp.status == HTTPStatus.OK


async def test_cors_on_static_files(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test that we enable CORS for static files."""
    assert await async_setup_component(
        hass, "frontend", {"http": {"cors_allowed_origins": ["http://www.example.com"]}}
    )
    hass.http.register_static_path("/something", str(Path(__file__).parent))

    client = await hass_client()
    resp = await client.options(
        "/something/__init__.py",
        headers={
            "origin": "http://www.example.com",
            ACCESS_CONTROL_REQUEST_METHOD: "GET",
        },
    )
    assert resp.status == HTTPStatus.OK
    assert resp.headers[ACCESS_CONTROL_ALLOW_ORIGIN] == "http://www.example.com"
