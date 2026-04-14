"""Test Supervisor diagnostics."""

from dataclasses import replace
import os
from unittest.mock import AsyncMock, Mock, patch

from aiohasupervisor.models import AddonState, InstalledAddonComplete
import pytest

from homeassistant.components.hassio import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

MOCK_ENVIRON = {"SUPERVISOR": "127.0.0.1", "SUPERVISOR_TOKEN": "abcdefgh"}


@pytest.fixture(autouse=True)
def mock_all(
    addon_installed: AsyncMock,
    store_info: AsyncMock,
    addon_stats: AsyncMock,
    addon_changelog: AsyncMock,
    resolution_info: AsyncMock,
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
    homeassistant_info.return_value = replace(
        homeassistant_info.return_value,
        version="1.0.0dev221",
        version_latest="1.0.0dev222",
        update_available=True,
    )
    os_info.return_value = replace(
        os_info.return_value,
        version="1.0.0dev2221",
        version_latest="1.0.0dev2222",
        update_available=True,
    )
    supervisor_info.return_value = replace(
        supervisor_info.return_value,
        version_latest="1.0.1dev222",
        update_available=True,
    )

    def mock_addon_info(slug: str):
        addon = Mock(
            spec=InstalledAddonComplete,
            to_dict=addon_installed.return_value.to_dict,
            **addon_installed.return_value.to_dict(),
        )
        if slug == "test":
            addon.name = "test"
            addon.slug = "test"
            addon.version = "2.0.0"
            addon.version_latest = "2.0.1"
            addon.update_available = True
            addon.state = AddonState.STARTED
            addon.url = "https://github.com/home-assistant/addons/test"
            addon.auto_update = True
        else:
            addon.name = "test2"
            addon.slug = "test2"
            addon.version = "3.1.0"
            addon.version_latest = "3.1.0"
            addon.update_available = False
            addon.state = AddonState.STOPPED
            addon.url = "https://github.com"
            addon.auto_update = False

        return addon

    addon_installed.side_effect = mock_addon_info


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test diagnostic information."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    config_entry.add_to_hass(hass)

    with patch.dict(os.environ, MOCK_ENVIRON):
        result = await async_setup_component(
            hass,
            "hassio",
            {"http": {"server_port": 9999, "server_host": "127.0.0.1"}, "hassio": {}},
        )
        assert result
        await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )

    assert "addons" in diagnostics["coordinator_data"]
    assert "core" in diagnostics["coordinator_data"]
    assert "supervisor" in diagnostics["coordinator_data"]
    assert "os" in diagnostics["coordinator_data"]
    assert "host" in diagnostics["coordinator_data"]

    assert len(diagnostics["devices"]) == 6
