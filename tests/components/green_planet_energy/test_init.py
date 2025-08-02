"""Test the Green Planet Energy integration setup."""

from unittest.mock import patch

from homeassistant.components.green_planet_energy.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(hass: HomeAssistant, mock_api) -> None:
    """Test setting up config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        unique_id="green_planet_energy",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.green_planet_energy.coordinator.async_get_clientsession",
        return_value=mock_api.return_value,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert DOMAIN in hass.data
    assert config_entry.entry_id in hass.data[DOMAIN]


async def test_unload_entry(hass: HomeAssistant, mock_api) -> None:
    """Test unloading config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        unique_id="green_planet_energy",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.green_planet_energy.coordinator.async_get_clientsession",
        return_value=mock_api.return_value,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.state is ConfigEntryState.LOADED

        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.state is ConfigEntryState.NOT_LOADED
        assert config_entry.entry_id not in hass.data[DOMAIN]
