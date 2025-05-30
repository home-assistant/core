"""Fixtures for Hass.io."""

from collections.abc import Generator
import os
import re
from unittest.mock import AsyncMock, patch

from aiohasupervisor.models import AddonsStats, AddonState
from aiohttp.test_utils import TestClient
import pytest

from homeassistant.auth.models import RefreshToken
from homeassistant.components.hassio.handler import HassIO
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import SUPERVISOR_TOKEN

from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
def disable_security_filter() -> Generator[None]:
    """Disable the security filter to ensure the integration is secure."""
    with patch(
        "homeassistant.components.http.security_filter.FILTERS",
        re.compile("not-matching-anything"),
    ):
        yield


@pytest.fixture
async def hassio_client(
    hassio_stubs: RefreshToken, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> TestClient:
    """Return a Hass.io HTTP client."""
    return await hass_client()


@pytest.fixture
async def hassio_noauth_client(
    hassio_stubs: RefreshToken,
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
) -> TestClient:
    """Return a Hass.io HTTP client without auth."""
    return await aiohttp_client(hass.http.app)


@pytest.fixture
async def hassio_client_supervisor(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    hassio_stubs: RefreshToken,
) -> TestClient:
    """Return an authenticated HTTP client."""
    access_token = hass.auth.async_create_access_token(hassio_stubs)
    return await aiohttp_client(
        hass.http.app,
        headers={"Authorization": f"Bearer {access_token}"},
    )


@pytest.fixture
def hassio_handler(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> Generator[HassIO]:
    """Create mock hassio handler."""
    with patch.dict(os.environ, {"SUPERVISOR_TOKEN": SUPERVISOR_TOKEN}):
        yield HassIO(hass.loop, async_get_clientsession(hass), "127.0.0.1")


@pytest.fixture
def all_setup_requests(
    aioclient_mock: AiohttpClientMocker,
    request: pytest.FixtureRequest,
    addon_installed: AsyncMock,
    store_info: AsyncMock,
    addon_changelog: AsyncMock,
    addon_stats: AsyncMock,
) -> None:
    """Mock all setup requests."""
    include_addons = hasattr(request, "param") and request.param.get(
        "include_addons", False
    )

    aioclient_mock.post("http://127.0.0.1/homeassistant/options", json={"result": "ok"})
    aioclient_mock.post("http://127.0.0.1/supervisor/options", json={"result": "ok"})
    aioclient_mock.get(
        "http://127.0.0.1/info",
        json={
            "result": "ok",
            "data": {
                "supervisor": "222",
                "homeassistant": "0.110.0",
                "hassos": "1.2.3",
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/host/info",
        json={
            "result": "ok",
            "data": {
                "result": "ok",
                "data": {
                    "chassis": "vm",
                    "operating_system": "Debian GNU/Linux 10 (buster)",
                    "kernel": "4.19.0-6-amd64",
                },
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/core/info",
        json={"result": "ok", "data": {"version_latest": "1.0.0", "version": "1.0.0"}},
    )
    aioclient_mock.get(
        "http://127.0.0.1/os/info",
        json={
            "result": "ok",
            "data": {
                "version_latest": "1.0.0",
                "version": "1.0.0",
                "update_available": False,
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/supervisor/info",
        json={
            "result": "ok",
            "data": {
                "result": "ok",
                "version": "1.0.0",
                "version_latest": "1.0.0",
                "auto_update": True,
                "addons": [
                    {
                        "name": "test",
                        "slug": "test",
                        "update_available": False,
                        "version": "1.0.0",
                        "version_latest": "1.0.0",
                        "repository": "core",
                        "state": "started",
                        "icon": False,
                    },
                    {
                        "name": "test2",
                        "slug": "test2",
                        "update_available": False,
                        "version": "1.0.0",
                        "version_latest": "1.0.0",
                        "repository": "core",
                        "state": "started",
                        "icon": False,
                    },
                ]
                if include_addons
                else [],
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/ingress/panels", json={"result": "ok", "data": {"panels": {}}}
    )

    addon_installed.return_value.update_available = False
    addon_installed.return_value.version = "1.0.0"
    addon_installed.return_value.version_latest = "1.0.0"
    addon_installed.return_value.repository = "core"
    addon_installed.return_value.state = AddonState.STARTED
    addon_installed.return_value.icon = False

    def mock_addon_info(slug: str):
        if slug == "test":
            addon_installed.return_value.name = "test"
            addon_installed.return_value.slug = "test"
            addon_installed.return_value.url = (
                "https://github.com/home-assistant/addons/test"
            )
            addon_installed.return_value.auto_update = True
        else:
            addon_installed.return_value.name = "test2"
            addon_installed.return_value.slug = "test2"
            addon_installed.return_value.url = "https://github.com"
            addon_installed.return_value.auto_update = False

        return addon_installed.return_value

    addon_installed.side_effect = mock_addon_info

    aioclient_mock.get(
        "http://127.0.0.1/core/stats",
        json={
            "result": "ok",
            "data": {
                "cpu_percent": 0.99,
                "memory_usage": 182611968,
                "memory_limit": 3977146368,
                "memory_percent": 4.59,
                "network_rx": 362570232,
                "network_tx": 82374138,
                "blk_read": 46010945536,
                "blk_write": 15051526144,
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/supervisor/stats",
        json={
            "result": "ok",
            "data": {
                "cpu_percent": 0.99,
                "memory_usage": 182611968,
                "memory_limit": 3977146368,
                "memory_percent": 4.59,
                "network_rx": 362570232,
                "network_tx": 82374138,
                "blk_read": 46010945536,
                "blk_write": 15051526144,
            },
        },
    )

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
    aioclient_mock.get(
        "http://127.0.0.1/network/info",
        json={
            "result": "ok",
            "data": {
                "host_internet": True,
                "supervisor_internet": True,
            },
        },
    )
