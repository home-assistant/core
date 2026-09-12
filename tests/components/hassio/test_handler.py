"""The tests for the hassio component."""

from typing import Any, Literal

from aiohttp import hdrs, web
from aiohttp.pytest_plugin import AiohttpRawServer
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
    aiohttp_raw_server: AiohttpRawServer,  # 'aiohttp_raw_server' must be before 'hass'!
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


@pytest.mark.usefixtures("socket_enabled")
async def test_send_command_text_response(
    aiohttp_raw_server: AiohttpRawServer,  # 'aiohttp_raw_server' must be before 'hass'!
    hass: HomeAssistant,
) -> None:
    """Test send command returns plain text when response is text/plain."""
    log_data = "2026-09-09 10:00:00 WARNING (MainThread) [test] sample log\n"

    async def mock_handler(request: web.Request) -> web.Response:
        """Return plain text logs."""
        return web.Response(text=log_data, content_type="text/plain")

    server = await aiohttp_raw_server(mock_handler)
    hassio_handler = HassIO(
        hass.loop,
        async_get_clientsession(hass),
        f"{server.host}:{server.port}",
    )

    result = await hassio_handler.send_command("/core/logs", method="GET")
    assert result == log_data


@pytest.mark.usefixtures("socket_enabled")
async def test_send_command_non_json_error(
    aiohttp_raw_server: AiohttpRawServer,  # 'aiohttp_raw_server' must be before 'hass'!
    hass: HomeAssistant,
) -> None:
    """Test send command raises HassioAPIError with body text when error response is not JSON."""

    async def mock_handler(request: web.Request) -> web.Response:
        """Return 502 Bad Gateway text."""
        return web.Response(
            text="502 Bad Gateway", status=502, content_type="text/plain"
        )

    server = await aiohttp_raw_server(mock_handler)
    hassio_handler = HassIO(
        hass.loop,
        async_get_clientsession(hass),
        f"{server.host}:{server.port}",
    )

    with pytest.raises(HassioAPIError, match="502 Bad Gateway"):
        await hassio_handler.send_command("/core/logs", method="GET")


@pytest.mark.usefixtures("socket_enabled")
async def test_send_command_non_dict_json_error(
    aiohttp_raw_server: AiohttpRawServer,  # 'aiohttp_raw_server' must be before 'hass'!
    hass: HomeAssistant,
) -> None:
    """Test non-dict JSON error payload raises HassioAPIError, not AttributeError."""

    async def mock_handler(request: web.Request) -> web.Response:
        """Return 400 with a JSON list body."""
        return web.json_response(["error"], status=400)

    server = await aiohttp_raw_server(mock_handler)
    hassio_handler = HassIO(
        hass.loop,
        async_get_clientsession(hass),
        f"{server.host}:{server.port}",
    )

    with pytest.raises(HassioAPIError):
        await hassio_handler.send_command("/core/logs", method="GET")


@pytest.mark.usefixtures("socket_enabled")
async def test_send_command_octet_stream_fallback(
    aiohttp_raw_server: AiohttpRawServer,  # 'aiohttp_raw_server' must be before 'hass'!
    hass: HomeAssistant,
) -> None:
    """Test send command falls back to text on unexpected mimetype (#116470)."""
    log_data = "2026-09-09 10:00:00 WARNING (MainThread) [test] octet-stream log\n"

    async def mock_handler(request: web.Request) -> web.Response:
        """Return text body with a fallback mimetype."""
        return web.Response(text=log_data, content_type="application/octet-stream")

    server = await aiohttp_raw_server(mock_handler)
    hassio_handler = HassIO(
        hass.loop,
        async_get_clientsession(hass),
        f"{server.host}:{server.port}",
    )

    result = await hassio_handler.send_command("/core/logs", method="GET")
    assert result == log_data


@pytest.mark.usefixtures("socket_enabled")
async def test_send_command_invalid_json_fallback(
    aiohttp_raw_server: AiohttpRawServer,  # 'aiohttp_raw_server' must be before 'hass'!
    hass: HomeAssistant,
) -> None:
    """Test send command falls back to text on JSON mimetype with invalid body."""
    raw_body = "not valid json"

    async def mock_handler(request: web.Request) -> web.Response:
        """Return invalid JSON body with JSON mimetype."""
        return web.Response(text=raw_body, content_type="application/json")

    server = await aiohttp_raw_server(mock_handler)
    hassio_handler = HassIO(
        hass.loop,
        async_get_clientsession(hass),
        f"{server.host}:{server.port}",
    )

    result = await hassio_handler.send_command("/core/logs", method="GET")
    assert result == raw_body
