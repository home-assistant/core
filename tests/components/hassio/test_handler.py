"""The tests for the hassio component."""

import aiohttp
import pytest

from homeassistant.components.hassio.handler import HassioAPIError


async def test_api_ping(hassio_handler, aioclient_mock):
    """Test setup with API ping."""
    aioclient_mock.get(
        "http://127.0.0.1/supervisor/ping", json={'result': 'ok'})

    assert (await hassio_handler.is_connected())
    assert aioclient_mock.call_count == 1


async def test_api_ping_error(hassio_handler, aioclient_mock):
    """Test setup with API ping error."""
    aioclient_mock.get(
        "http://127.0.0.1/supervisor/ping", json={'result': 'error'})

    assert not (await hassio_handler.is_connected())
    assert aioclient_mock.call_count == 1


async def test_api_ping_exeption(hassio_handler, aioclient_mock):
    """Test setup with API ping exception."""
    aioclient_mock.get(
        "http://127.0.0.1/supervisor/ping", exc=aiohttp.ClientError())

    assert not (await hassio_handler.is_connected())
    assert aioclient_mock.call_count == 1


async def test_api_homeassistant_info(hassio_handler, aioclient_mock):
    """Test setup with API homeassistant info."""
    aioclient_mock.get(
        "http://127.0.0.1/homeassistant/info", json={
            'result': 'ok', 'data': {'last_version': '10.0'}})

    data = await hassio_handler.get_homeassistant_info()
    assert aioclient_mock.call_count == 1
    assert data['last_version'] == "10.0"


async def test_api_homeassistant_info_error(hassio_handler, aioclient_mock):
    """Test setup with API homeassistant info error."""
    aioclient_mock.get(
        "http://127.0.0.1/homeassistant/info", json={
            'result': 'error', 'message': None})

    with pytest.raises(HassioAPIError):
        await hassio_handler.get_homeassistant_info()

    assert aioclient_mock.call_count == 1


async def test_api_homeassistant_stop(hassio_handler, aioclient_mock):
    """Test setup with API HomeAssistant stop."""
    aioclient_mock.post(
        "http://127.0.0.1/homeassistant/stop", json={'result': 'ok'})

    assert (await hassio_handler.stop_homeassistant())
    assert aioclient_mock.call_count == 1


async def test_api_homeassistant_restart(hassio_handler, aioclient_mock):
    """Test setup with API HomeAssistant restart."""
    aioclient_mock.post(
        "http://127.0.0.1/homeassistant/restart", json={'result': 'ok'})

    assert (await hassio_handler.restart_homeassistant())
    assert aioclient_mock.call_count == 1


async def test_api_homeassistant_config(hassio_handler, aioclient_mock):
    """Test setup with API HomeAssistant config."""
    aioclient_mock.post(
        "http://127.0.0.1/homeassistant/check", json={
            'result': 'ok', 'data': {'test': 'bla'}})

    data = await hassio_handler.check_homeassistant_config()
    assert data['data']['test'] == 'bla'
    assert aioclient_mock.call_count == 1


async def test_api_addon_info(hassio_handler, aioclient_mock):
    """Test setup with API Add-on info."""
    aioclient_mock.get(
        "http://127.0.0.1/addons/test/info", json={
            'result': 'ok', 'data': {'name': 'bla'}})

    data = await hassio_handler.get_addon_info("test")
    assert data['name'] == 'bla'
    assert aioclient_mock.call_count == 1


async def test_api_discovery_message(hassio_handler, aioclient_mock):
    """Test setup with API discovery message."""
    aioclient_mock.get(
        "http://127.0.0.1/discovery/test", json={
            'result': 'ok', 'data': {"service": "mqtt"}})

    data = await hassio_handler.get_discovery_message("test")
    assert data['service'] == "mqtt"
    assert aioclient_mock.call_count == 1


async def test_api_retrieve_discovery(hassio_handler, aioclient_mock):
    """Test setup with API discovery message."""
    aioclient_mock.get(
        "http://127.0.0.1/discovery", json={
            'result': 'ok', 'data': {'discovery': [{"service": "mqtt"}]}})

    data = await hassio_handler.retrieve_discovery_messages()
    assert data['discovery'][-1]['service'] == "mqtt"
    assert aioclient_mock.call_count == 1
