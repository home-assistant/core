"""Test the Teslemetry init."""

from tesla_fleet_api.exceptions import TeslaFleetError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_load_unload(hass: HomeAssistant, config_entry_mock) -> None:
    """Test load and unload."""

    config_entry_mock.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry_mock.entry_id)
    await hass.async_block_till_done()

    assert config_entry_mock.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(config_entry_mock.entry_id)
    await hass.async_block_till_done()
    assert config_entry_mock.state is ConfigEntryState.NOT_LOADED


async def test_failure(hass: HomeAssistant, teslemetry_mock, config_entry_mock) -> None:
    """Test init with an error."""

    teslemetry_mock.products.side_effect = TeslaFleetError
    config_entry_mock.add_to_hass(hass)
    assert config_entry_mock.state is ConfigEntryState.SETUP_ERROR
