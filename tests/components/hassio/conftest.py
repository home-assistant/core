"""Fixtures for Hass.io."""

from collections.abc import Generator
from dataclasses import replace
import os
import re
from unittest.mock import AsyncMock, Mock, patch

from aiohasupervisor.models import AddonsStats, AddonState, InstalledAddonComplete
from aiohttp.test_utils import TestClient
import pytest

from homeassistant.components.hassio.const import DATA_CONFIG_STORE
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
) -> TestClient:
    """Return an authenticated HTTP client."""
    hassio_user_id = hass.data[DATA_CONFIG_STORE].data.hassio_user
    hassio_user = await hass.auth.async_get_user(hassio_user_id)
    assert hassio_user
    assert hassio_user.refresh_tokens
    refresh_token = next(iter(hassio_user.refresh_tokens.values()))
    access_token = hass.auth.async_create_access_token(refresh_token)
    return await aiohttp_client(
        hass.http.app,
        headers={"Authorization": f"Bearer {access_token}"},
    )


@pytest.fixture
async def hassio_handler(
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
) -> None:
    """Mock all setup requests."""
    include_addons = hasattr(request, "param") and request.param.get(
        "include_addons", False
    )

    aioclient_mock.post("http://127.0.0.1/homeassistant/options", json={"result": "ok"})
    aioclient_mock.post("http://127.0.0.1/supervisor/options", json={"result": "ok"})
    aioclient_mock.get(
        "http://127.0.0.1/ingress/panels", json={"result": "ok", "data": {"panels": {}}}
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

    aioclient_mock.get(
        "http://127.0.0.1/jobs/info",
        json={"result": "ok", "data": {"ignore_conditions": [], "jobs": []}},
    )
