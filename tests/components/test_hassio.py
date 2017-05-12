"""The tests for the hassio component."""
import asyncio
import os
from unittest.mock import patch, Mock, MagicMock

import pytest

from homeassistant.setup import async_setup_component

from tests.common import mock_coro, mock_http_component_app


@pytest.fixture
def hassio_env():
    """Fixture to inject hassio env."""
    with patch.dict(os.environ, {'HASSIO': "127.0.0.1"}), \
            patch('homeassistant.components.hassio.HassIO.is_connected',
                  Mock(return_value=mock_coro(True))):
        yield


@pytest.fixture
def hassio_client(hassio_env, hass, test_client):
    """Create mock hassio http client."""
    app = mock_http_component_app(hass)
    hass.loop.run_until_complete(async_setup_component(hass, 'hassio', {}))
    hass.http.views['api:hassio'].register(app.router)
    yield hass.loop.run_until_complete(test_client(app))


@asyncio.coroutine
def test_fail_setup_without_environ_var(hass):
    """Fail setup if no environ variable set."""
    with patch.dict(os.environ, {}, clear=True):
        result = yield from async_setup_component(hass, 'hassio', {})
        assert not result


@asyncio.coroutine
def test_fail_setup_cannot_connect(hass):
    """Fail setup if cannot connect."""
    with patch.dict(os.environ, {'HASSIO': "127.0.0.1"}), \
            patch('homeassistant.components.hassio.HassIO.is_connected',
                  Mock(return_value=mock_coro(False))):
        result = yield from async_setup_component(hass, 'hassio', {})
        assert not result


@asyncio.coroutine
def test_forward_request(hassio_client):
    """Test fetching normal path."""
    response = MagicMock()
    response.read.return_value = mock_coro('data')

    with patch('homeassistant.components.hassio.HassIO.command_proxy',
               Mock(return_value=mock_coro(response))), \
            patch('homeassistant.components.hassio._create_response') as mresp:
        mresp.return_value = 'response'
        resp = yield from hassio_client.post('/api/hassio/beer')

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

    with patch('homeassistant.components.hassio.HassIO.command_proxy',
               Mock(return_value=mock_coro(response))), \
            patch('homeassistant.components.hassio.'
                  '_create_response_log') as mresp:
        mresp.return_value = 'response'
        resp = yield from hassio_client.get('/api/hassio/beer/logs')

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
    with patch('homeassistant.components.hassio.async_timeout.timeout',
               side_effect=asyncio.TimeoutError):
        resp = yield from hassio_client.get('/api/hassio/addons/test/info')
    assert resp.status == 502
