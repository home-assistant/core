"""The tests for the hassio component."""

from __future__ import annotations

from typing import Any, Literal

from aiohttp import hdrs, web
import pytest

from homeassistant.components.hassio.handler import HassIO, HassioAPIError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession


@pytest.mark.parametrize(
    ("api_call", "method", "payload"),
    [
        ("/ingress/panels", "GET", None),
        ("/supervisor/options", "POST", {"diagnostics": True}),
        ("/supervisor/update", "POST", None),
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

    await hassio_handler.send_command(api_call, method, payload)
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
