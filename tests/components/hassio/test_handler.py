"""The tests for the hassio component."""

import aiohttp
import pytest

from homeassistant.components.hassio.handler import HassioAPIError


async def test_api_ping(hassio_handler, aioclient_mock):
    """Test setup with API ping."""
    aioclient_mock.get("http://127.0.0.1/supervisor/ping", json={"result": "ok"})

    assert await hassio_handler.is_connected()
    assert aioclient_mock.call_count == 1


async def test_api_ping_error(hassio_handler, aioclient_mock):
    """Test setup with API ping error."""
    aioclient_mock.get("http://127.0.0.1/supervisor/ping", json={"result": "error"})

    assert not (await hassio_handler.is_connected())
    assert aioclient_mock.call_count == 1


async def test_api_ping_exeption(hassio_handler, aioclient_mock):
    """Test setup with API ping exception."""
    aioclient_mock.get("http://127.0.0.1/supervisor/ping", exc=aiohttp.ClientError())

    assert not (await hassio_handler.is_connected())
    assert aioclient_mock.call_count == 1


async def test_api_info(hassio_handler, aioclient_mock):
    """Test setup with API generic info."""
    aioclient_mock.get(
        "http://127.0.0.1/info",
        json={
            "result": "ok",
            "data": {"supervisor": "222", "homeassistant": "0.110.0", "hassos": None},
        },
    )

    data = await hassio_handler.get_info()
    assert aioclient_mock.call_count == 1
    assert data["hassos"] is None
    assert data["homeassistant"] == "0.110.0"
    assert data["supervisor"] == "222"


async def test_api_info_error(hassio_handler, aioclient_mock):
    """Test setup with API Home Assistant info error."""
    aioclient_mock.get(
        "http://127.0.0.1/info", json={"result": "error", "message": None}
    )

    with pytest.raises(HassioAPIError):
        await hassio_handler.get_info()

    assert aioclient_mock.call_count == 1


async def test_api_host_info(hassio_handler, aioclient_mock):
    """Test setup with API Host info."""
    aioclient_mock.get(
        "http://127.0.0.1/host/info",
        json={
            "result": "ok",
            "data": {
                "chassis": "vm",
                "operating_system": "Debian GNU/Linux 10 (buster)",
                "kernel": "4.19.0-6-amd64",
            },
        },
    )

    data = await hassio_handler.get_host_info()
    assert aioclient_mock.call_count == 1
    assert data["chassis"] == "vm"
    assert data["kernel"] == "4.19.0-6-amd64"
    assert data["operating_system"] == "Debian GNU/Linux 10 (buster)"


async def test_api_supervisor_info(hassio_handler, aioclient_mock):
    """Test setup with API Supervisor info."""
    aioclient_mock.get(
        "http://127.0.0.1/supervisor/info",
        json={
            "result": "ok",
            "data": {"supported": True, "version": "2020.11.1", "channel": "stable"},
        },
    )

    data = await hassio_handler.get_supervisor_info()
    assert aioclient_mock.call_count == 1
    assert data["supported"]
    assert data["version"] == "2020.11.1"
    assert data["channel"] == "stable"


async def test_api_os_info(hassio_handler, aioclient_mock):
    """Test setup with API OS info."""
    aioclient_mock.get(
        "http://127.0.0.1/os/info",
        json={
            "result": "ok",
            "data": {"board": "odroid-n2", "version": "2020.11.1"},
        },
    )

    data = await hassio_handler.get_os_info()
    assert aioclient_mock.call_count == 1
    assert data["board"] == "odroid-n2"
    assert data["version"] == "2020.11.1"


async def test_api_host_info_error(hassio_handler, aioclient_mock):
    """Test setup with API Home Assistant info error."""
    aioclient_mock.get(
        "http://127.0.0.1/host/info", json={"result": "error", "message": None}
    )

    with pytest.raises(HassioAPIError):
        await hassio_handler.get_host_info()

    assert aioclient_mock.call_count == 1


async def test_api_core_info(hassio_handler, aioclient_mock):
    """Test setup with API Home Assistant Core info."""
    aioclient_mock.get(
        "http://127.0.0.1/core/info",
        json={"result": "ok", "data": {"version_latest": "1.0.0"}},
    )

    data = await hassio_handler.get_core_info()
    assert aioclient_mock.call_count == 1
    assert data["version_latest"] == "1.0.0"


async def test_api_core_info_error(hassio_handler, aioclient_mock):
    """Test setup with API Home Assistant Core info error."""
    aioclient_mock.get(
        "http://127.0.0.1/core/info", json={"result": "error", "message": None}
    )

    with pytest.raises(HassioAPIError):
        await hassio_handler.get_core_info()

    assert aioclient_mock.call_count == 1


async def test_api_homeassistant_stop(hassio_handler, aioclient_mock):
    """Test setup with API Home Assistant stop."""
    aioclient_mock.post("http://127.0.0.1/homeassistant/stop", json={"result": "ok"})

    assert await hassio_handler.stop_homeassistant()
    assert aioclient_mock.call_count == 1


async def test_api_homeassistant_restart(hassio_handler, aioclient_mock):
    """Test setup with API Home Assistant restart."""
    aioclient_mock.post("http://127.0.0.1/homeassistant/restart", json={"result": "ok"})

    assert await hassio_handler.restart_homeassistant()
    assert aioclient_mock.call_count == 1


async def test_api_addon_info(hassio_handler, aioclient_mock):
    """Test setup with API Add-on info."""
    aioclient_mock.get(
        "http://127.0.0.1/addons/test/info",
        json={"result": "ok", "data": {"name": "bla"}},
    )

    data = await hassio_handler.get_addon_info("test")
    assert data["name"] == "bla"
    assert aioclient_mock.call_count == 1


async def test_api_discovery_message(hassio_handler, aioclient_mock):
    """Test setup with API discovery message."""
    aioclient_mock.get(
        "http://127.0.0.1/discovery/test",
        json={"result": "ok", "data": {"service": "mqtt"}},
    )

    data = await hassio_handler.get_discovery_message("test")
    assert data["service"] == "mqtt"
    assert aioclient_mock.call_count == 1


async def test_api_retrieve_discovery(hassio_handler, aioclient_mock):
    """Test setup with API discovery message."""
    aioclient_mock.get(
        "http://127.0.0.1/discovery",
        json={"result": "ok", "data": {"discovery": [{"service": "mqtt"}]}},
    )

    data = await hassio_handler.retrieve_discovery_messages()
    assert data["discovery"][-1]["service"] == "mqtt"
    assert aioclient_mock.call_count == 1


async def test_api_ingress_panels(hassio_handler, aioclient_mock):
    """Test setup with API Ingress panels."""
    aioclient_mock.get(
        "http://127.0.0.1/ingress/panels",
        json={
            "result": "ok",
            "data": {
                "panels": {
                    "slug": {
                        "enable": True,
                        "title": "Test",
                        "icon": "mdi:test",
                        "admin": False,
                    }
                }
            },
        },
    )

    data = await hassio_handler.get_ingress_panels()
    assert aioclient_mock.call_count == 1
    assert data["panels"]
    assert "slug" in data["panels"]
