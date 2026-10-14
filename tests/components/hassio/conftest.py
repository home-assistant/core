"""Fixtures for Hass.io."""

from collections.abc import AsyncGenerator, Generator
from dataclasses import replace
import os
import re
from unittest.mock import AsyncMock, Mock, patch

from aiohasupervisor.models import AddonsStats, AddonState, InstalledAddonComplete
from aiohttp.test_utils import TestClient
import pytest

from homeassistant.components.hassio.handler import HassIO
from homeassistant.components.http.config import _DEFAULT_CONFIG as HTTP_DEFAULT_CONFIG
from homeassistant.components.http.const import CONF_SERVER_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import SUPERVISOR_TOKEN

from tests.typing import ClientSessionGenerator, WebSocketGenerator


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
async def hassio_handler(hass: HomeAssistant) -> AsyncGenerator[HassIO]:
    """Create mock hassio handler."""
    with patch.dict(os.environ, {"SUPERVISOR_TOKEN": SUPERVISOR_TOKEN}):
        yield HassIO(hass.loop, async_get_clientsession(hass), "127.0.0.1")


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
