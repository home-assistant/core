"""Test cors for the HTTP component."""
import asyncio
from unittest.mock import patch

from aiohttp import web
from aiohttp.hdrs import (
    ACCESS_CONTROL_ALLOW_ORIGIN,
    ACCESS_CONTROL_ALLOW_HEADERS,
    ACCESS_CONTROL_REQUEST_HEADERS,
    ACCESS_CONTROL_REQUEST_METHOD,
    ORIGIN
)
import pytest

from homeassistant.const import HTTP_HEADER_HA_AUTH
from homeassistant.setup import async_setup_component
from homeassistant.components.http.cors import setup_cors


TRUSTED_ORIGIN = 'https://home-assistant.io'


@asyncio.coroutine
def test_cors_middleware_not_loaded_by_default(hass):
    """Test accessing to server from banned IP when feature is off."""
    with patch('homeassistant.components.http.setup_cors') as mock_setup:
        yield from async_setup_component(hass, 'http', {
            'http': {}
        })

    assert len(mock_setup.mock_calls) == 0


@asyncio.coroutine
def test_cors_middleware_loaded_from_config(hass):
    """Test accessing to server from banned IP when feature is off."""
    with patch('homeassistant.components.http.setup_cors') as mock_setup:
        yield from async_setup_component(hass, 'http', {
            'http': {
                'cors_allowed_origins': ['http://home-assistant.io']
            }
        })

    assert len(mock_setup.mock_calls) == 1


@asyncio.coroutine
def mock_handler(request):
    """Return if request was authenticated."""
    return web.Response(status=200)


@pytest.fixture
def client(loop, test_client):
    """Fixture to setup a web.Application."""
    app = web.Application()
    app.router.add_get('/', mock_handler)
    setup_cors(app, [TRUSTED_ORIGIN])
    return loop.run_until_complete(test_client(app))


@asyncio.coroutine
def test_cors_requests(client):
    """Test cross origin requests."""
    req = yield from client.get('/', headers={
        ORIGIN: TRUSTED_ORIGIN
    })
    assert req.status == 200
    assert req.headers[ACCESS_CONTROL_ALLOW_ORIGIN] == \
        TRUSTED_ORIGIN

    # With password in URL
    req = yield from client.get('/', params={
        'api_password': 'some-pass'
    }, headers={
        ORIGIN: TRUSTED_ORIGIN
    })
    assert req.status == 200
    assert req.headers[ACCESS_CONTROL_ALLOW_ORIGIN] == \
        TRUSTED_ORIGIN

    # With password in headers
    req = yield from client.get('/', headers={
        HTTP_HEADER_HA_AUTH: 'some-pass',
        ORIGIN: TRUSTED_ORIGIN
    })
    assert req.status == 200
    assert req.headers[ACCESS_CONTROL_ALLOW_ORIGIN] == \
        TRUSTED_ORIGIN


@asyncio.coroutine
def test_cors_preflight_allowed(client):
    """Test cross origin resource sharing preflight (OPTIONS) request."""
    req = yield from client.options('/', headers={
        ORIGIN: TRUSTED_ORIGIN,
        ACCESS_CONTROL_REQUEST_METHOD: 'GET',
        ACCESS_CONTROL_REQUEST_HEADERS: 'x-ha-access'
    })

    assert req.status == 200
    assert req.headers[ACCESS_CONTROL_ALLOW_ORIGIN] == TRUSTED_ORIGIN
    assert req.headers[ACCESS_CONTROL_ALLOW_HEADERS] == \
        HTTP_HEADER_HA_AUTH.upper()
