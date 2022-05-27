"""Test the Fronius integration."""
from unittest.mock import patch

from pyfronius import FroniusError

from homeassistant.components.fronius.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState

from . import mock_responses, setup_fronius_integration


async def test_unload_config_entry(hass, aioclient_mock):
    """Test that configuration entry supports unloading."""
    mock_responses(aioclient_mock)
    await setup_fronius_integration(hass)

    fronius_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(fronius_entries) == 1

    test_entry = fronius_entries[0]
    assert test_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(test_entry.entry_id)
    await hass.async_block_till_done()

    assert test_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_logger_error(hass, aioclient_mock):
    """Test setup when logger reports an error."""
    # gen24 dataset will raise FroniusError when logger is called
    mock_responses(aioclient_mock, fixture_set="gen24")
    config_entry = await setup_fronius_integration(hass, is_logger=True)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_inverter_error(hass, aioclient_mock):
    """Test setup when inverter_info reports an error."""
    mock_responses(aioclient_mock)
    with patch(
        "pyfronius.Fronius.inverter_info",
        side_effect=FroniusError,
    ):
        config_entry = await setup_fronius_integration(hass)
        assert config_entry.state is ConfigEntryState.SETUP_RETRY
