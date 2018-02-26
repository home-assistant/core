"""The tests for the hassio component."""
import asyncio

import aiohttp


@asyncio.coroutine
def test_api_ping(hassio_handler, aioclient_mock):
    """Test setup with API ping."""
    aioclient_mock.get(
        "http://127.0.0.1/supervisor/ping", json={'result': 'ok'})

    assert (yield from hassio_handler.is_connected())
    assert aioclient_mock.call_count == 1


@asyncio.coroutine
def test_api_ping_error(hassio_handler, aioclient_mock):
    """Test setup with API ping error."""
    aioclient_mock.get(
        "http://127.0.0.1/supervisor/ping", json={'result': 'error'})

    assert not (yield from hassio_handler.is_connected())
    assert aioclient_mock.call_count == 1


@asyncio.coroutine
def test_api_ping_exeption(hassio_handler, aioclient_mock):
    """Test setup with API ping exception."""
    aioclient_mock.get(
        "http://127.0.0.1/supervisor/ping", exc=aiohttp.ClientError())

    assert not (yield from hassio_handler.is_connected())
    assert aioclient_mock.call_count == 1


@asyncio.coroutine
def test_api_homeassistant_info(hassio_handler, aioclient_mock):
    """Test setup with API homeassistant info."""
    aioclient_mock.get(
        "http://127.0.0.1/homeassistant/info", json={
            'result': 'ok', 'data': {'last_version': '10.0'}})

    data = yield from hassio_handler.get_homeassistant_info()
    assert aioclient_mock.call_count == 1
    assert data['last_version'] == "10.0"


@asyncio.coroutine
def test_api_homeassistant_info_error(hassio_handler, aioclient_mock):
    """Test setup with API homeassistant info error."""
    aioclient_mock.get(
        "http://127.0.0.1/homeassistant/info", json={
            'result': 'error', 'message': None})

    data = yield from hassio_handler.get_homeassistant_info()
    assert aioclient_mock.call_count == 1
    assert data is None


@asyncio.coroutine
def test_api_homeassistant_stop(hassio_handler, aioclient_mock):
    """Test setup with API HomeAssistant stop."""
    aioclient_mock.post(
        "http://127.0.0.1/homeassistant/stop", json={'result': 'ok'})

    assert (yield from hassio_handler.stop_homeassistant())
    assert aioclient_mock.call_count == 1


@asyncio.coroutine
def test_api_homeassistant_restart(hassio_handler, aioclient_mock):
    """Test setup with API HomeAssistant restart."""
    aioclient_mock.post(
        "http://127.0.0.1/homeassistant/restart", json={'result': 'ok'})

    assert (yield from hassio_handler.restart_homeassistant())
    assert aioclient_mock.call_count == 1


@asyncio.coroutine
def test_api_homeassistant_config(hassio_handler, aioclient_mock):
    """Test setup with API HomeAssistant restart."""
    aioclient_mock.post(
        "http://127.0.0.1/homeassistant/check", json={
            'result': 'ok', 'data': {'test': 'bla'}})

    data = yield from hassio_handler.check_homeassistant_config()
    assert data['data']['test'] == 'bla'
    assert aioclient_mock.call_count == 1
