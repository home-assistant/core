"""The tests for the hassio component."""

from collections.abc import Awaitable, Callable
import os
from pathlib import Path
from typing import Any, Literal
from unittest.mock import patch

from aiohasupervisor import SupervisorClient
from aiohasupervisor.models import SupervisorOptions
from aiohttp import DummyCookieJar, UnixConnector, hdrs, web
import pytest
from yarl import URL

from homeassistant.components.hassio.const import ENV_SUPERVISOR_SOCKET
from homeassistant.components.hassio.handler import (
    KEY_SUPERVISOR_CONNECTION,
    HassIO,
    HassioAPIError,
    SupervisorConnection,
    get_passthrough_supervisor_client,
    get_supervisor_client,
    get_supervisor_connection,
)
from homeassistant.const import EVENT_HOMEASSISTANT_CLOSE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import SUPERVISOR_TOKEN


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
        SupervisorConnection(
            async_get_clientsession(hass), URL(f"http://{server.host}:{server.port}")
        )
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
    hass.data[KEY_SUPERVISOR_CONNECTION] = SupervisorConnection(
        async_get_clientsession(hass), URL(f"http://{server.host}:{server.port}")
    )

    await client_call(get_supervisor_client(hass))
    assert received_request is not None

    assert received_request.method == method
    assert received_request.path == path
    assert received_request.headers.get("X-Hass-Source") == "core/aiohasupervisor"


@pytest.mark.parametrize(
    ("client_call", "source"),
    [
        pytest.param(
            lambda hass: get_passthrough_supervisor_client(hass).send_command(
                "/supervisor/ping", "get"
            ),
            "core.handler",
            id="handler",
        ),
        pytest.param(
            lambda hass: get_supervisor_client(hass).supervisor.ping(),
            "core/aiohasupervisor",
            id="supervisor_client",
        ),
    ],
)
@pytest.mark.usefixtures("hassio_unix_socket_env")
async def test_unix_socket(
    hass: HomeAssistant,
    supervisor_unix_socket: tuple[Path, list[web.Request]],
    client_call: Callable[[HomeAssistant], Awaitable[Any]],
    source: str,
) -> None:
    """Test requests over the Supervisor Unix socket carry no token."""
    path, requests = supervisor_unix_socket
    session = get_supervisor_connection(hass).session

    # Supervisor still issues a token to Core, it must not be sent on the socket
    with patch.dict(os.environ, {"SUPERVISOR_TOKEN": SUPERVISOR_TOKEN}):
        await client_call(hass)

    assert isinstance(session.connector, UnixConnector)
    assert session.connector.path == str(path)
    # Every app is "localhost" over the socket, cookies must not be shared
    assert isinstance(session.cookie_jar, DummyCookieJar)
    assert len(requests) == 1
    assert requests[0].path == "/supervisor/ping"
    assert requests[0].host == "localhost"
    assert hdrs.AUTHORIZATION not in requests[0].headers
    assert requests[0].headers["X-Hass-Source"] == source


async def test_unix_socket_session_closed(hass: HomeAssistant) -> None:
    """Test the Supervisor Unix socket session is closed with Home Assistant."""
    with patch.dict(
        os.environ, {ENV_SUPERVISOR_SOCKET: "/run/supervisor/api/supervisor.sock"}
    ):
        session = get_supervisor_connection(hass).session
    assert not session.closed

    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()

    assert session.closed


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
        SupervisorConnection(
            async_get_clientsession(hass), URL(f"http://{server.host}:{server.port}")
        )
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
        SupervisorConnection(
            async_get_clientsession(hass), URL(f"http://{server.host}:{server.port}")
        )
    )

    with pytest.raises(HassioAPIError, match="^401: Unauthorized$"):
        await hassio_handler.send_command("/ingress/validate_session")

    assert "Client error" not in caplog.text


@pytest.mark.usefixtures("hassio_stubs")
async def test_send_command_invalid_command(hass: HomeAssistant) -> None:
    """Test send command fails when command is invalid."""
    hassio = get_passthrough_supervisor_client(hass)
    with pytest.raises(HassioAPIError):
        # absolute path
        await hassio.send_command("/test/../bad")
    with pytest.raises(HassioAPIError):
        # relative path
        await hassio.send_command("test/../bad")
    with pytest.raises(HassioAPIError):
        # relative path with percent encoding
        await hassio.send_command("test/%2E%2E/bad")
