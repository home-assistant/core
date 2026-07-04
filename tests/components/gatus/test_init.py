"""Tests for the Gatus integration setup and unload lifecycle."""

from unittest.mock import AsyncMock

from homeassistant.components.gatus.const import DOMAIN
from homeassistant.components.gatus.coordinator import GatusDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_and_unload_entry(
    hass: HomeAssistant, mock_gatus_client: AsyncMock
) -> None:
    """Test standard successful setup and unload cycle of the integration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_URL: "http://gatus.example.com:8080"}
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data is not None
    assert isinstance(config_entry.runtime_data, GatusDataUpdateCoordinator)

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
