"""The tests for the hassio component."""

from collections.abc import Awaitable, Callable
from typing import Any, Literal

from aiohasupervisor import SupervisorClient
from aiohasupervisor.models import SupervisorOptions
from aiohttp import hdrs, web
import pytest

from homeassistant.components.hassio.const import DATA_COMPONENT
from homeassistant.components.hassio.handler import (
    HassIO,
    HassioAPIError,
    get_supervisor_client,
)
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


@pytest.mark.parametrize(
    ("client_call", "method", "path"),
    [
        pytest.param(
            lambda client: client.supervisor.ping(),
            "GET",
            "/supervisor/ping",
            id="supervisor_ping",
        ),
        pytest.param(
            lambda client: client.supervisor.set_options(
                SupervisorOptions(diagnostics=True)
            ),
            "POST",
            "/supervisor/options",
            id="supervisor_options",
        ),
        pytest.param(
            lambda client: client.store.reload(),
            "POST",
            "/store/reload",
            id="store_reload",
        ),
    ],
)
@pytest.mark.usefixtures("socket_enabled")
async def test_supervisor_client_source_header(
    aiohttp_raw_server,  # 'aiohttp_raw_server' must be before 'hass'!
    hass: HomeAssistant,
    client_call: Callable[[SupervisorClient], Awaitable[None]],
    method: Literal["GET", "POST"],
    path: str,
) -> None:
    """Test the supervisor client identifies itself with X-Hass-Source."""
    received_request = None

    async def mock_handler(request):
        """Return OK."""
        nonlocal received_request
        received_request = request
        return web.json_response({"result": "ok", "data": {}})

    server = await aiohttp_raw_server(mock_handler)
    hass.data[DATA_COMPONENT] = HassIO(
        hass.loop,
        async_get_clientsession(hass),
        f"{server.host}:{server.port}",
    )

    await client_call(get_supervisor_client(hass))
    assert received_request is not None

    assert received_request.method == method
    assert received_request.path == path
    assert received_request.headers.get("X-Hass-Source") == "core/aiohasupervisor"


@pytest.mark.usefixtures("socket_enabled")
async def test_api_range_header(
    aiohttp_raw_server,  # 'aiohttp_raw_server' must be before 'hass'!
    hass: HomeAssistant,
) -> None:
    """Test the range header is sent."""
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

    await hassio_handler.send_command(
        "/core/logs",
        "GET",
        range_header="entries=:-1:2",
    )

    assert received_request is not None
    assert received_request.headers[hdrs.RANGE] == "entries=:-1:2"


@pytest.mark.usefixtures("socket_enabled")
async def test_send_command_text_error(
    aiohttp_raw_server,  # 'aiohttp_raw_server' must be before 'hass'!
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a plain text error response raises with the response text."""

    async def mock_handler(request: web.BaseRequest) -> web.Response:
        """Return a plain text error like aiohttp's HTTP exceptions."""
        return web.Response(status=401, text="401: Unauthorized")

    server = await aiohttp_raw_server(mock_handler)
    hassio_handler = HassIO(
        hass.loop,
        async_get_clientsession(hass),
        f"{server.host}:{server.port}",
    )

    with pytest.raises(HassioAPIError, match="^401: Unauthorized$"):
        await hassio_handler.send_command("/ingress/validate_session")

    assert "Client error" not in caplog.text


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
