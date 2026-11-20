"""Fixtures for Hass.io."""

from collections.abc import AsyncGenerator, Generator
from dataclasses import replace
import os
from pathlib import Path
import re
import shutil
import tempfile
from unittest.mock import AsyncMock, Mock, patch

from aiohasupervisor.models import AddonsStats, AddonState, InstalledAddonComplete
from aiohttp import web
from aiohttp.test_utils import TestClient
import pytest
from pytest_homeassistant.typing import ClientSessionGenerator, WebSocketGenerator
import pytest_socket

from homeassistant.components.hassio.const import ENV_SUPERVISOR_SOCKET
from homeassistant.components.http.config import _DEFAULT_CONFIG as HTTP_DEFAULT_CONFIG
from homeassistant.components.http.const import CONF_SERVER_PORT
from homeassistant.core import HomeAssistant


@pytest.fixture(autouse=True)
def disable_security_filter() -> Generator[None]:
    """Disable the security filter to ensure the integration is secure."""
    with patch(
        "homeassistant.components.http.security_filter.FILTERS",
        re.compile("not-matching-anything"),
    ):
        yield


@pytest.fixture(autouse=True)
def http_supervisor_default_port() -> Generator[None]:
    """Reflect the port-80 HTTP default that Core sees under Supervisor.

    _DEFAULT_CONFIG is frozen at import (port 8123, since SUPERVISOR is not set
    then in the test process). Under MOCK_ENVIRON the runtime default is 80, so
    the store would treat the default as a pending change and schedule an
    auto-revert restart - a state that cannot occur in a real Supervisor
    process. Patch the default to port 80 to reproduce production.
    """
    default_80 = {**HTTP_DEFAULT_CONFIG, CONF_SERVER_PORT: 80}
    with (
        patch("homeassistant.components.http.config._DEFAULT_CONFIG", default_80),
        patch("homeassistant.components.http.server._DEFAULT_CONFIG", default_80),
    ):
        yield


@pytest.fixture
async def hassio_client(
    hassio_stubs: None, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> TestClient:
    """Return a Hass.io HTTP client."""
    return await hass_client()


@pytest.fixture
async def supervisor_unix_socket() -> AsyncGenerator[tuple[Path, list[web.Request]]]:
    """Serve a mock Supervisor API on a Unix socket and record requests to it."""
    # The default allow list blocks connecting to Unix sockets, reset per test
    pytest_socket.socket_allow_hosts(["127.0.0.1"], allow_unix_socket=True)
    requests: list[web.Request] = []

    async def handler(request: web.Request) -> web.Response:
        requests.append(request)
        return web.json_response({"result": "ok", "data": {}})

    app = web.Application()
    app.router.add_route("*", "/{path:.*}", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    # Not tmp_path, it can exceed the sun_path limit (104 bytes on macOS)
    socket_dir = tempfile.mkdtemp(dir="/tmp")
    path = Path(socket_dir, "supervisor.sock")
    await web.UnixSite(runner, str(path)).start()
    yield path, requests
    await runner.cleanup()
    shutil.rmtree(socket_dir)


@pytest.fixture
def hassio_unix_socket_env(
    supervisor_unix_socket: tuple[Path, list[web.Request]],
) -> Generator[None]:
    """Point the hassio integration at the mock Supervisor Unix socket."""
    with patch.dict(
        os.environ, {ENV_SUPERVISOR_SOCKET: str(supervisor_unix_socket[0])}
    ):
        yield


@pytest.fixture
async def hassio_unix_socket_client(
    hassio_unix_socket_env: None,
    hassio_stubs: None,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> TestClient:
    """Return a Hass.io HTTP client with Supervisor reached over a Unix socket."""
    return await hass_client()


@pytest.fixture
async def hassio_noauth_client(
    hassio_stubs: None, hass: HomeAssistant, aiohttp_client: ClientSessionGenerator
) -> TestClient:
    """Return a Hass.io HTTP client without auth."""
    return await aiohttp_client(hass.http.app)


@pytest.fixture
async def hassio_client_supervisor(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    hassio_stubs: None,
) -> AsyncGenerator[TestClient]:
    """Return an authenticated HTTP client."""
    with (
        patch(
            "homeassistant.components.hassio.auth.is_supervisor_unix_socket_request",
            return_value=True,
        ),
        patch(
            "homeassistant.components.http.auth.is_supervisor_unix_socket_request",
            return_value=True,
        ),
        patch(
            "homeassistant.components.http.ban.is_supervisor_unix_socket_request",
            return_value=True,
        ),
    ):
        yield await aiohttp_client(hass.http.app)


@pytest.fixture
def hass_supervisor_ws_client(
    hass_ws_client: WebSocketGenerator,
    hass: HomeAssistant,
) -> WebSocketGenerator:
    """Return a websocket client authenticated as the Supervisor user."""

    async def create_client() -> WebSocketGenerator:
        with (
            patch(
                "homeassistant.components.http.auth.is_supervisor_unix_socket_request",
                return_value=True,
            ),
            patch(
                "homeassistant.components.http.ban.is_supervisor_unix_socket_request",
                return_value=True,
            ),
            patch(
                "homeassistant.components.websocket_api.http.is_supervisor_unix_socket_request",
                return_value=True,
            ),
        ):
            return await hass_ws_client(hass, supervisor_unix_socket=True)

    return create_client


@pytest.fixture
def all_setup_requests(
    request: pytest.FixtureRequest,
    addon_installed: AsyncMock,
    store_info: AsyncMock,
    addon_changelog: AsyncMock,
    addon_stats: AsyncMock,
    jobs_info: AsyncMock,
    host_info: AsyncMock,
    supervisor_root_info: AsyncMock,
    homeassistant_info: AsyncMock,
    supervisor_info: AsyncMock,
    addons_list: AsyncMock,
    network_info: AsyncMock,
    os_info: AsyncMock,
    homeassistant_stats: AsyncMock,
    supervisor_stats: AsyncMock,
    ingress_panels: AsyncMock,
) -> None:
    """Mock all setup requests."""
    include_addons = hasattr(request, "param") and request.param.get(
        "include_addons", False
    )

    if include_addons:
        addons_list.return_value[0] = replace(
            addons_list.return_value[0],
            version="1.0.0",
            version_latest="1.0.0",
            update_available=False,
        )
        addons_list.return_value[1] = replace(
            addons_list.return_value[1],
            version="1.0.0",
            version_latest="1.0.0",
            state=AddonState.STARTED,
        )
    else:
        addons_list.return_value = []

    addon_installed.return_value.update_available = False
    addon_installed.return_value.version = "1.0.0"
    addon_installed.return_value.version_latest = "1.0.0"
    addon_installed.return_value.repository = "core"
    addon_installed.return_value.state = AddonState.STARTED
    addon_installed.return_value.icon = False

    def mock_addon_info(slug: str):
        addon = Mock(
            spec=InstalledAddonComplete,
            to_dict=addon_installed.return_value.to_dict,
            **addon_installed.return_value.to_dict(),
        )
        if slug == "test":
            addon.name = "test"
            addon.slug = "test"
            addon.url = "https://github.com/home-assistant/addons/test"
            addon.auto_update = True
        else:
            addon.name = "test2"
            addon.slug = "test2"
            addon.url = "https://github.com"
            addon.auto_update = False

        return addon

    addon_installed.side_effect = mock_addon_info

    async def mock_addon_stats(addon: str) -> AddonsStats:
        """Mock addon stats for test and test2."""
        if addon == "test2":
            return AddonsStats(
                cpu_percent=0.8,
                memory_usage=51941376,
                memory_limit=3977146368,
                memory_percent=1.31,
                network_rx=31338284,
                network_tx=15692900,
                blk_read=740077568,
                blk_write=6004736,
            )
        return AddonsStats(
            cpu_percent=0.99,
            memory_usage=182611968,
            memory_limit=3977146368,
            memory_percent=4.59,
            network_rx=362570232,
            network_tx=82374138,
            blk_read=46010945536,
            blk_write=15051526144,
        )

    addon_stats.side_effect = mock_addon_stats
