"""The tests for the hassio component."""
import asyncio
import os
from unittest.mock import patch

from homeassistant.setup import async_setup_component


@asyncio.coroutine
def test_setup_api_ping(hass, aioclient_mock):
    """Test setup with API ping."""
    aioclient_mock.get(
        "http://127.0.0.1/supervisor/ping", json={'result': 'ok'})
    aioclient_mock.get(
        "http://127.0.0.1/homeassistant/info", json={
            'result': 'ok', 'data': {'last_version': '10.0'}})

    with patch.dict(os.environ, {'HASSIO': "127.0.0.1"}):
        result = yield from async_setup_component(hass, 'hassio', {})
        assert result

    assert aioclient_mock.call_count == 2
    assert hass.components.hassio.get_homeassistant_version() == "10.0"
    assert hass.components.hassio.is_hassio()


@asyncio.coroutine
def test_setup_api_push_api_data(hass, aioclient_mock):
    """Test setup with API push."""
    aioclient_mock.get(
        "http://127.0.0.1/supervisor/ping", json={'result': 'ok'})
    aioclient_mock.get(
        "http://127.0.0.1/homeassistant/info", json={
            'result': 'ok', 'data': {'last_version': '10.0'}})
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

    assert aioclient_mock.call_count == 3
    assert not aioclient_mock.mock_calls[1][2]['ssl']
    assert aioclient_mock.mock_calls[1][2]['password'] == "123456"
    assert aioclient_mock.mock_calls[1][2]['port'] == 9999
    assert aioclient_mock.mock_calls[1][2]['watchdog']


@asyncio.coroutine
def test_setup_api_push_api_data_server_host(hass, aioclient_mock):
    """Test setup with API push with active server host."""
    aioclient_mock.get(
        "http://127.0.0.1/supervisor/ping", json={'result': 'ok'})
    aioclient_mock.get(
        "http://127.0.0.1/homeassistant/info", json={
            'result': 'ok', 'data': {'last_version': '10.0'}})
    aioclient_mock.post(
        "http://127.0.0.1/homeassistant/options", json={'result': 'ok'})

    with patch.dict(os.environ, {'HASSIO': "127.0.0.1"}):
        result = yield from async_setup_component(hass, 'hassio', {
            'http': {
                'api_password': "123456",
                'server_port': 9999,
                'server_host': "127.0.0.1"
            },
            'hassio': {}
        })
        assert result

    assert aioclient_mock.call_count == 3
    assert not aioclient_mock.mock_calls[1][2]['ssl']
    assert aioclient_mock.mock_calls[1][2]['password'] == "123456"
    assert aioclient_mock.mock_calls[1][2]['port'] == 9999
    assert not aioclient_mock.mock_calls[1][2]['watchdog']


@asyncio.coroutine
def test_setup_api_push_api_data_default(hass, aioclient_mock):
    """Test setup with API push default data."""
    aioclient_mock.get(
        "http://127.0.0.1/supervisor/ping", json={'result': 'ok'})
    aioclient_mock.get(
        "http://127.0.0.1/homeassistant/info", json={
            'result': 'ok', 'data': {'last_version': '10.0'}})
    aioclient_mock.post(
        "http://127.0.0.1/homeassistant/options", json={'result': 'ok'})

    with patch.dict(os.environ, {'HASSIO': "127.0.0.1"}):
        result = yield from async_setup_component(hass, 'hassio', {
            'http': {},
            'hassio': {}
        })
        assert result

    assert aioclient_mock.call_count == 3
    assert not aioclient_mock.mock_calls[1][2]['ssl']
    assert aioclient_mock.mock_calls[1][2]['password'] is None
    assert aioclient_mock.mock_calls[1][2]['port'] == 8123


@asyncio.coroutine
def test_setup_core_push_timezone(hass, aioclient_mock):
    """Test setup with API push default data."""
    aioclient_mock.get(
        "http://127.0.0.1/supervisor/ping", json={'result': 'ok'})
    aioclient_mock.get(
        "http://127.0.0.1/homeassistant/info", json={
            'result': 'ok', 'data': {'last_version': '10.0'}})
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

    assert aioclient_mock.call_count == 3
    assert aioclient_mock.mock_calls[1][2]['timezone'] == "testzone"


@asyncio.coroutine
def test_setup_hassio_no_additional_data(hass, aioclient_mock):
    """Test setup with API push default data."""
    aioclient_mock.get(
        "http://127.0.0.1/supervisor/ping", json={'result': 'ok'})
    aioclient_mock.get(
        "http://127.0.0.1/homeassistant/info", json={
            'result': 'ok', 'data': {'last_version': '10.0'}})
    aioclient_mock.get(
        "http://127.0.0.1/homeassistant/info", json={'result': 'ok'})

    with patch.dict(os.environ, {'HASSIO': "127.0.0.1"}), \
            patch.dict(os.environ, {'HASSIO_TOKEN': "123456"}):
        result = yield from async_setup_component(hass, 'hassio', {
            'hassio': {},
        })
        assert result

    assert aioclient_mock.call_count == 2
    assert aioclient_mock.mock_calls[-1][3]['X-HASSIO-KEY'] == "123456"
