"""Tests for the WATERCryst integration setup."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.watercryst.const import DOMAIN
from homeassistant.components.watercryst.coordinator import WatercrystUpdateCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant


@pytest.mark.usefixtures("mock_api_client")
async def test_setup_and_unload(hass: HomeAssistant) -> None:
    """Test standard setup and unloading of the config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="WATERCryst",
        unique_id="2026123456789123",
        entry_id="6D9GB5RKL9691HH3RT895JNH56",
        data={CONF_API_KEY: "<api-key>"},
    )

    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.watercryst._PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert type(config_entry.runtime_data) is WatercrystUpdateCoordinator

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
