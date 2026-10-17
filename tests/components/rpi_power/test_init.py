"""Tests for rpi_power integration."""

from homeassistant.components.rpi_power.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, patch


async def test_entry_setup_unload(hass: HomeAssistant) -> None:
    """Test integration setup and unload."""

    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)
    with patch("homeassistant.components.rpi_power.new_under_voltage", get=True):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_config_entry_error(hass: HomeAssistant) -> None:
    """Test config entry error."""
    with patch(
        "homeassistant.components.rpi_power.new_under_voltage", return_value=None
    ):
        config_entry = MockConfigEntry(domain=DOMAIN)
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
