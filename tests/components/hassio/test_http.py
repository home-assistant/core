"""The tests for the hassio component."""
import asyncio
from unittest.mock import patch, Mock, MagicMock

import pytest

from homeassistant.const import HTTP_HEADER_HA_AUTH
from homeassistant.setup import async_setup_component

from tests.common import mock_coro
from .test_init import hassio_env

API_PASSWORD = 'pass1234'


@pytest.fixture
def hassio_client(hassio_env, hass, test_client):
    """Create mock hassio http client."""
    with patch('homeassistant.components.hassio.HassIO.update_hass_api',
               Mock(return_value=mock_coro({"result": "ok"}))), \
            patch('homeassistant.components.hassio.HassIO.'
                  'get_homeassistant_info',
                  Mock(return_value=mock_coro(None))):
        hass.loop.run_until_complete(async_setup_component(hass, 'hassio', {
            'http': {
                'api_password': API_PASSWORD
            }
        }))
    yield hass.loop.run_until_complete(test_client(hass.http.app))


@asyncio.coroutine
def test_forward_request(hassio_client):
    """Test fetching normal path."""
    response = MagicMock()
    response.read.return_value = mock_coro('data')

    with patch('homeassistant.components.hassio.HassIOView._command_proxy',
               Mock(return_value=mock_coro(response))), \
            patch('homeassistant.components.hassio.http'
                  '._create_response') as mresp:
        mresp.return_value = 'response'
        resp = yield from hassio_client.post('/api/hassio/beer', headers={
                HTTP_HEADER_HA_AUTH: API_PASSWORD
            })

    # Check we got right response
    assert resp.status == 200
    body = yield from resp.text()
    assert body == 'response'

    # Check we forwarded command
    assert len(mresp.mock_calls) == 1
    assert mresp.mock_calls[0][1] == (response, 'data')


@asyncio.coroutine
def test_auth_required_forward_request(hassio_client):
    """Test auth required for normal request."""
    resp = yield from hassio_client.post('/api/hassio/beer')

    # Check we got right response
    assert resp.status == 401


@asyncio.coroutine
@pytest.mark.parametrize(
    'build_type', [
        'es5/index.html', 'es5/hassio-app.html', 'latest/index.html',
        'latest/hassio-app.html'
    ])
def test_forward_request_no_auth_for_panel(hassio_client, build_type):
    """Test no auth needed for ."""
    response = MagicMock()
    response.read.return_value = mock_coro('data')

    with patch('homeassistant.components.hassio.HassIOView._command_proxy',
               Mock(return_value=mock_coro(response))), \
            patch('homeassistant.components.hassio.http.'
                  '_create_response') as mresp:
        mresp.return_value = 'response'
        resp = yield from hassio_client.get(
            '/api/hassio/app-{}'.format(build_type))

    # Check we got right response
    assert resp.status == 200
    body = yield from resp.text()
    assert body == 'response'

    # Check we forwarded command
    assert len(mresp.mock_calls) == 1
    assert mresp.mock_calls[0][1] == (response, 'data')


@asyncio.coroutine
def test_forward_request_no_auth_for_logo(hassio_client):
    """Test no auth needed for ."""
    response = MagicMock()
    response.read.return_value = mock_coro('data')

    with patch('homeassistant.components.hassio.HassIOView._command_proxy',
               Mock(return_value=mock_coro(response))), \
            patch('homeassistant.components.hassio.http.'
                  '_create_response') as mresp:
        mresp.return_value = 'response'
        resp = yield from hassio_client.get('/api/hassio/addons/bl_b392/logo')

    # Check we got right response
    assert resp.status == 200
    body = yield from resp.text()
    assert body == 'response'

    # Check we forwarded command
    assert len(mresp.mock_calls) == 1
    assert mresp.mock_calls[0][1] == (response, 'data')


@asyncio.coroutine
def test_forward_log_request(hassio_client):
    """Test fetching normal log path."""
    response = MagicMock()
    response.read.return_value = mock_coro('data')

    with patch('homeassistant.components.hassio.HassIOView._command_proxy',
               Mock(return_value=mock_coro(response))), \
            patch('homeassistant.components.hassio.http.'
                  '_create_response_log') as mresp:
        mresp.return_value = 'response'
        resp = yield from hassio_client.get('/api/hassio/beer/logs', headers={
                HTTP_HEADER_HA_AUTH: API_PASSWORD
            })

    # Check we got right response
    assert resp.status == 200
    body = yield from resp.text()
    assert body == 'response'

    # Check we forwarded command
    assert len(mresp.mock_calls) == 1
    assert mresp.mock_calls[0][1] == (response, 'data')


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
