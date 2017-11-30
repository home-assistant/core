"""The tests for the hassio component."""
import asyncio
import os
from unittest.mock import patch, Mock, MagicMock

import pytest

from homeassistant.const import HTTP_HEADER_HA_AUTH
from homeassistant.setup import async_setup_component

from tests.common import mock_coro

API_PASSWORD = 'pass1234'


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
    with patch('homeassistant.components.hassio.HassIO.update_hass_api',
               Mock(return_value=mock_coro(True))):
        hass.loop.run_until_complete(async_setup_component(hass, 'hassio', {
            'http': {
                'api_password': API_PASSWORD
            }
        }))
    yield hass.loop.run_until_complete(test_client(hass.http.app))


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
def test_setup_api_ping(hass, aioclient_mock):
    """Test setup with API ping."""
    aioclient_mock.get(
        "http://127.0.0.1/supervisor/ping", json={'result': 'ok'})

    with patch.dict(os.environ, {'HASSIO': "127.0.0.1"}):
        result = yield from async_setup_component(hass, 'hassio', {})
        assert result

    assert aioclient_mock.call_count == 1


@asyncio.coroutine
def test_setup_api_push_api_data(hass, aioclient_mock):
    """Test setup with API push."""
    aioclient_mock.get(
        "http://127.0.0.1/supervisor/ping", json={'result': 'ok'})
    aioclient_mock.post(
        "http://127.0.0.1/homeassistant/options", json={'result': 'ok'})

    with patch.dict(os.environ, {'HASSIO': "127.0.0.1"}):
        result = yield from async_setup_component(hass, 'hassio', {
            'http': {
                'api_password': "123456",
                'server_port': 9999
            },
            'hassio': {}
        })
        assert result

    assert aioclient_mock.call_count == 2
    assert not aioclient_mock.mock_calls[-1][2]['ssl']
    assert aioclient_mock.mock_calls[-1][2]['password'] == "123456"
    assert aioclient_mock.mock_calls[-1][2]['port'] == 9999


@asyncio.coroutine
def test_setup_api_push_api_data_default(hass, aioclient_mock):
    """Test setup with API push default data."""
    aioclient_mock.get(
        "http://127.0.0.1/supervisor/ping", json={'result': 'ok'})
    aioclient_mock.post(
        "http://127.0.0.1/homeassistant/options", json={'result': 'ok'})

    with patch.dict(os.environ, {'HASSIO': "127.0.0.1"}):
        result = yield from async_setup_component(hass, 'hassio', {
            'http': {},
            'hassio': {}
        })
        assert result

    assert aioclient_mock.call_count == 2
    assert not aioclient_mock.mock_calls[-1][2]['ssl']
    assert aioclient_mock.mock_calls[-1][2]['password'] is None
    assert aioclient_mock.mock_calls[-1][2]['port'] == 8123


@asyncio.coroutine
def test_setup_core_push_timezone(hass, aioclient_mock):
    """Test setup with API push default data."""
    aioclient_mock.get(
        "http://127.0.0.1/supervisor/ping", json={'result': 'ok'})
    aioclient_mock.post(
        "http://127.0.0.1/supervisor/options", json={'result': 'ok'})

    with patch.dict(os.environ, {'HASSIO': "127.0.0.1"}):
        result = yield from async_setup_component(hass, 'hassio', {
            'hassio': {},
            'homeassistant': {
                'time_zone': 'testzone',
            },
        })
        assert result

    assert aioclient_mock.call_count == 2
    assert aioclient_mock.mock_calls[-1][2]['timezone'] == "testzone"


@asyncio.coroutine
def test_setup_hassio_no_additional_data(hass, aioclient_mock):
    """Test setup with API push default data."""
    aioclient_mock.get(
        "http://127.0.0.1/supervisor/ping", json={'result': 'ok'})

    with patch.dict(os.environ, {'HASSIO': "127.0.0.1"}):
        result = yield from async_setup_component(hass, 'hassio', {
            'hassio': {},
        })
        assert result

    assert aioclient_mock.call_count == 1


@asyncio.coroutine
def test_service_register(hassio_env, hass):
    """Check if service will be settup."""
    assert (yield from async_setup_component(hass, 'hassio', {}))
    assert hass.services.has_service('hassio', 'addon_start')
    assert hass.services.has_service('hassio', 'addon_stop')
    assert hass.services.has_service('hassio', 'addon_restart')
    assert hass.services.has_service('hassio', 'addon_stdin')
    assert hass.services.has_service('hassio', 'host_shutdown')
    assert hass.services.has_service('hassio', 'host_reboot')


@asyncio.coroutine
def test_service_calls(hassio_env, hass, aioclient_mock):
    """Call service and check the API calls behind that."""
    assert (yield from async_setup_component(hass, 'hassio', {}))

    aioclient_mock.post(
        "http://127.0.0.1/addons/test/start", json={'result': 'ok'})
    aioclient_mock.post(
        "http://127.0.0.1/addons/test/stop", json={'result': 'ok'})
    aioclient_mock.post(
        "http://127.0.0.1/addons/test/restart", json={'result': 'ok'})
    aioclient_mock.post(
        "http://127.0.0.1/addons/test/stdin", json={'result': 'ok'})
    aioclient_mock.post(
        "http://127.0.0.1/host/shutdown", json={'result': 'ok'})
    aioclient_mock.post(
        "http://127.0.0.1/host/reboot", json={'result': 'ok'})

    yield from hass.services.async_call(
        'hassio', 'addon_start', {'addon': 'test'})
    yield from hass.services.async_call(
        'hassio', 'addon_stop', {'addon': 'test'})
    yield from hass.services.async_call(
        'hassio', 'addon_restart', {'addon': 'test'})
    yield from hass.services.async_call(
        'hassio', 'addon_stdin', {'addon': 'test', 'input': 'test'})
    yield from hass.async_block_till_done()

    assert aioclient_mock.call_count == 4
    assert aioclient_mock.mock_calls[-1][2] == 'test'

    yield from hass.services.async_call('hassio', 'host_shutdown', {})
    yield from hass.services.async_call('hassio', 'host_reboot', {})
    yield from hass.async_block_till_done()

    assert aioclient_mock.call_count == 6


@asyncio.coroutine
def test_forward_request(hassio_client):
    """Test fetching normal path."""
    response = MagicMock()
    response.read.return_value = mock_coro('data')

    with patch('homeassistant.components.hassio.HassIO.command_proxy',
               Mock(return_value=mock_coro(response))), \
            patch('homeassistant.components.hassio._create_response') as mresp:
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
@pytest.mark.parametrize('build_type', ['es5', 'latest'])
def test_forward_request_no_auth_for_panel(hassio_client, build_type):
    """Test no auth needed for ."""
    response = MagicMock()
    response.read.return_value = mock_coro('data')

    with patch('homeassistant.components.hassio.HassIO.command_proxy',
               Mock(return_value=mock_coro(response))), \
            patch('homeassistant.components.hassio._create_response') as mresp:
        mresp.return_value = 'response'
        resp = yield from hassio_client.get(
            '/api/hassio/panel_{}'.format(build_type))

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

    with patch('homeassistant.components.hassio.HassIO.command_proxy',
               Mock(return_value=mock_coro(response))), \
            patch('homeassistant.components.hassio._create_response') as mresp:
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

    with patch('homeassistant.components.hassio.HassIO.command_proxy',
               Mock(return_value=mock_coro(response))), \
            patch('homeassistant.components.hassio.'
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
    with patch('homeassistant.components.hassio.async_timeout.timeout',
               side_effect=asyncio.TimeoutError):
        resp = yield from hassio_client.get(
            '/api/hassio/addons/test/info', headers={
                HTTP_HEADER_HA_AUTH: API_PASSWORD
            })
    assert resp.status == 502
