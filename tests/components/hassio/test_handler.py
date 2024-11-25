"""The tests for the hassio component."""

from __future__ import annotations

from typing import Any, Literal

from aiohttp import hdrs, web
import pytest

from homeassistant.components.hassio import handler
from homeassistant.components.hassio.handler import HassIO, HassioAPIError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_api_info(
    hassio_handler: HassIO, aioclient_mock: AiohttpClientMocker
) -> None:
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


async def test_api_info_error(
    hassio_handler: HassIO, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with API Home Assistant info error."""
    aioclient_mock.get(
        "http://127.0.0.1/info", json={"result": "error", "message": None}
    )

    with pytest.raises(HassioAPIError):
        await hassio_handler.get_info()

    assert aioclient_mock.call_count == 1


async def test_api_host_info(
    hassio_handler: HassIO, aioclient_mock: AiohttpClientMocker
) -> None:
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


async def test_api_supervisor_info(
    hassio_handler: HassIO, aioclient_mock: AiohttpClientMocker
) -> None:
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


async def test_api_os_info(
    hassio_handler: HassIO, aioclient_mock: AiohttpClientMocker
) -> None:
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


async def test_api_host_info_error(
    hassio_handler: HassIO, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with API Home Assistant info error."""
    aioclient_mock.get(
        "http://127.0.0.1/host/info", json={"result": "error", "message": None}
    )

    with pytest.raises(HassioAPIError):
        await hassio_handler.get_host_info()

    assert aioclient_mock.call_count == 1


async def test_api_core_info(
    hassio_handler: HassIO, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with API Home Assistant Core info."""
    aioclient_mock.get(
        "http://127.0.0.1/core/info",
        json={"result": "ok", "data": {"version_latest": "1.0.0"}},
    )

    data = await hassio_handler.get_core_info()
    assert aioclient_mock.call_count == 1
    assert data["version_latest"] == "1.0.0"


async def test_api_core_info_error(
    hassio_handler: HassIO, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with API Home Assistant Core info error."""
    aioclient_mock.get(
        "http://127.0.0.1/core/info", json={"result": "error", "message": None}
    )

    with pytest.raises(HassioAPIError):
        await hassio_handler.get_core_info()

    assert aioclient_mock.call_count == 1


async def test_api_core_stats(
    hassio_handler: HassIO, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with API Add-on stats."""
    aioclient_mock.get(
        "http://127.0.0.1/core/stats",
        json={"result": "ok", "data": {"memory_percent": 0.01}},
    )

    data = await hassio_handler.get_core_stats()
    assert data["memory_percent"] == 0.01
    assert aioclient_mock.call_count == 1


async def test_api_supervisor_stats(
    hassio_handler: HassIO, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with API Add-on stats."""
    aioclient_mock.get(
        "http://127.0.0.1/supervisor/stats",
        json={"result": "ok", "data": {"memory_percent": 0.01}},
    )

    data = await hassio_handler.get_supervisor_stats()
    assert data["memory_percent"] == 0.01
    assert aioclient_mock.call_count == 1


async def test_api_ingress_panels(
    hassio_handler: HassIO, aioclient_mock: AiohttpClientMocker
) -> None:
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


@pytest.mark.parametrize(
    ("api_call", "method", "payload"),
    [
        ("get_network_info", "GET", None),
        ("update_diagnostics", "POST", True),
    ],
)
@pytest.mark.usefixtures("socket_enabled")
async def test_api_headers(
    aiohttp_raw_server,  # 'aiohttp_raw_server' must be before 'hass'!
    hass: HomeAssistant,
    api_call: str,
    method: Literal["GET", "POST"],
    payload: Any,
) -> None:
    """Test headers are forwarded correctly."""
    received_request = None

    async def mock_handler(request):
        """Return OK."""
        nonlocal received_request
        received_request = request
        return web.json_response({"result": "ok", "data": None})

    server = await aiohttp_raw_server(mock_handler)
    hassio_handler = HassIO(
        hass.loop,
        async_get_clientsession(hass),
        f"{server.host}:{server.port}",
    )

    api_func = getattr(hassio_handler, api_call)
    if payload:
        await api_func(payload)
    else:
        await api_func()
    assert received_request is not None

    assert received_request.method == method
    assert received_request.headers.get("X-Hass-Source") == "core.handler"

    if method == "GET":
        assert hdrs.CONTENT_TYPE not in received_request.headers
        return

    assert hdrs.CONTENT_TYPE in received_request.headers
    if payload:
        assert received_request.headers[hdrs.CONTENT_TYPE] == "application/json"
    else:
        assert received_request.headers[hdrs.CONTENT_TYPE] == "application/octet-stream"


@pytest.mark.usefixtures("hassio_stubs")
async def test_api_get_green_settings(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with API ping."""
    aioclient_mock.get(
        "http://127.0.0.1/os/boards/green",
        json={
            "result": "ok",
            "data": {
                "activity_led": True,
                "power_led": True,
                "system_health_led": True,
            },
        },
    )

    assert await handler.async_get_green_settings(hass) == {
        "activity_led": True,
        "power_led": True,
        "system_health_led": True,
    }
    assert aioclient_mock.call_count == 1


@pytest.mark.usefixtures("hassio_stubs")
async def test_api_set_green_settings(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with API ping."""
    aioclient_mock.post(
        "http://127.0.0.1/os/boards/green",
        json={"result": "ok", "data": {}},
    )

    assert (
        await handler.async_set_green_settings(
            hass, {"activity_led": True, "power_led": True, "system_health_led": True}
        )
        == {}
    )
    assert aioclient_mock.call_count == 1


@pytest.mark.usefixtures("hassio_stubs")
async def test_api_get_yellow_settings(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with API ping."""
    aioclient_mock.get(
        "http://127.0.0.1/os/boards/yellow",
        json={
            "result": "ok",
            "data": {"disk_led": True, "heartbeat_led": True, "power_led": True},
        },
    )

    assert await handler.async_get_yellow_settings(hass) == {
        "disk_led": True,
        "heartbeat_led": True,
        "power_led": True,
    }
    assert aioclient_mock.call_count == 1


@pytest.mark.usefixtures("hassio_stubs")
async def test_api_set_yellow_settings(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with API ping."""
    aioclient_mock.post(
        "http://127.0.0.1/os/boards/yellow",
        json={"result": "ok", "data": {}},
    )

    assert (
        await handler.async_set_yellow_settings(
            hass, {"disk_led": True, "heartbeat_led": True, "power_led": True}
        )
        == {}
    )
    assert aioclient_mock.call_count == 1


@pytest.mark.usefixtures("hassio_stubs")
async def test_api_reboot_host(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with API ping."""
    aioclient_mock.post(
        "http://127.0.0.1/host/reboot",
        json={"result": "ok", "data": {}},
    )

    assert await handler.async_reboot_host(hass) == {}
    assert aioclient_mock.call_count == 1


@pytest.mark.usefixtures("hassio_stubs")
async def test_send_command_invalid_command(hass: HomeAssistant) -> None:
    """Test send command fails when command is invalid."""
    hassio: HassIO = hass.data["hassio"]
    with pytest.raises(HassioAPIError):
        # absolute path
        await hassio.send_command("/test/../bad")
    with pytest.raises(HassioAPIError):
        # relative path
        await hassio.send_command("test/../bad")
    with pytest.raises(HassioAPIError):
        # relative path with percent encoding
        await hassio.send_command("test/%2E%2E/bad")
