"""The tests for the hassio component."""
import asyncio
from unittest.mock import patch

import pytest

from homeassistant.const import HTTP_HEADER_HA_AUTH

from . import API_PASSWORD


@asyncio.coroutine
def test_forward_request(hassio_client, aioclient_mock):
    """Test fetching normal path."""
    aioclient_mock.post("http://127.0.0.1/beer", text="response")

    resp = yield from hassio_client.post('/api/hassio/beer', headers={
        HTTP_HEADER_HA_AUTH: API_PASSWORD
    })

    # Check we got right response
    assert resp.status == 200
    body = yield from resp.text()
    assert body == 'response'

    # Check we forwarded command
    assert len(aioclient_mock.mock_calls) == 1


@asyncio.coroutine
@pytest.mark.parametrize(
    'build_type', [
        'supervisor/info', 'homeassistant/update', 'host/info'
    ])
def test_auth_required_forward_request(hassio_noauth_client, build_type):
    """Test auth required for normal request."""
    resp = yield from hassio_noauth_client.post(
        "/api/hassio/{}".format(build_type))

    # Check we got right response
    assert resp.status == 401


@asyncio.coroutine
@pytest.mark.parametrize(
    'build_type', [
        'app/index.html', 'app/hassio-app.html', 'app/index.html',
        'app/hassio-app.html', 'app/some-chunk.js', 'app/app.js',
    ])
def test_forward_request_no_auth_for_panel(
        hassio_client, build_type, aioclient_mock):
    """Test no auth needed for ."""
    aioclient_mock.get(
        "http://127.0.0.1/{}".format(build_type), text="response")

    resp = yield from hassio_client.get('/api/hassio/{}'.format(build_type))

    # Check we got right response
    assert resp.status == 200
    body = yield from resp.text()
    assert body == 'response'

    # Check we forwarded command
    assert len(aioclient_mock.mock_calls) == 1


@asyncio.coroutine
def test_forward_request_no_auth_for_logo(hassio_client, aioclient_mock):
    """Test no auth needed for ."""
    aioclient_mock.get(
        "http://127.0.0.1/addons/bl_b392/logo", text="response")

    resp = yield from hassio_client.get('/api/hassio/addons/bl_b392/logo')

    # Check we got right response
    assert resp.status == 200
    body = yield from resp.text()
    assert body == 'response'

    # Check we forwarded command
    assert len(aioclient_mock.mock_calls) == 1


@asyncio.coroutine
def test_forward_log_request(hassio_client, aioclient_mock):
    """Test fetching normal log path doesn't remove ANSI color escape codes."""
    aioclient_mock.get(
        "http://127.0.0.1/beer/logs", text="\033[32mresponse\033[0m")

    resp = yield from hassio_client.get('/api/hassio/beer/logs', headers={
        HTTP_HEADER_HA_AUTH: API_PASSWORD
    })

    # Check we got right response
    assert resp.status == 200
    body = yield from resp.text()
    assert body == '\033[32mresponse\033[0m'

    # Check we forwarded command
    assert len(aioclient_mock.mock_calls) == 1


@asyncio.coroutine
def test_bad_gateway_when_cannot_find_supervisor(hassio_client):
    """Test we get a bad gateway error if we can't find supervisor."""
    with patch('homeassistant.components.hassio.http.async_timeout.timeout',
               side_effect=asyncio.TimeoutError):
        resp = yield from hassio_client.get(
            '/api/hassio/addons/test/info', headers={
                HTTP_HEADER_HA_AUTH: API_PASSWORD
            })
    assert resp.status == 502


async def test_forwarding_user_info(hassio_client, hass_admin_user,
                                    aioclient_mock):
    """Test that we forward user info correctly."""
    aioclient_mock.get('http://127.0.0.1/hello')

    resp = await hassio_client.get('/api/hassio/hello')

    # Check we got right response
    assert resp.status == 200

    assert len(aioclient_mock.mock_calls) == 1

    req_headers = aioclient_mock.mock_calls[0][-1]
    req_headers['X-HASS-USER-ID'] == hass_admin_user.id
    req_headers['X-HASS-IS-ADMIN'] == '1'
