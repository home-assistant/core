"""Test for Roborock init."""
from unittest.mock import patch

from roborock.exceptions import RoborockTimeout

from homeassistant.components.roborock.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.roborock.mock_data import HOME_DATA, NETWORK_INFO


async def test_unload_entry(
    hass: HomeAssistant, bypass_api_fixture, setup_entry: MockConfigEntry
) -> None:
    """Test unloading roboorck integration."""
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert setup_entry.state is ConfigEntryState.LOADED
    with patch(
        "homeassistant.components.roborock.coordinator.RoborockLocalClient.async_disconnect"
    ) as mock_disconnect:
        assert await hass.config_entries.async_unload(setup_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_disconnect.call_count == 1
        assert setup_entry.state is ConfigEntryState.NOT_LOADED
        assert not hass.data.get(DOMAIN)


async def test_config_entry_not_ready(
    hass: HomeAssistant, mock_roborock_entry: MockConfigEntry
) -> None:
    """Test that when coordinator update fails, entry retries."""
    with patch(
        "homeassistant.components.roborock.RoborockApiClient.get_home_data",
    ), patch(
        "homeassistant.components.roborock.RoborockDataUpdateCoordinator._async_update_data",
        side_effect=UpdateFailed(),
    ):
        await async_setup_component(hass, DOMAIN, {})
        assert mock_roborock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_continue_setup_mqtt_disconnect_fail(
    hass: HomeAssistant, mock_roborock_entry: MockConfigEntry
):
    """Test that if disconnect fails, we still continue setting up."""
    with patch(
        "homeassistant.components.roborock.RoborockApiClient.get_home_data",
        return_value=HOME_DATA,
    ), patch(
        "homeassistant.components.roborock.RoborockMqttClient.get_networking",
        return_value=NETWORK_INFO,
    ), patch(
        "homeassistant.components.roborock.RoborockMqttClient.async_disconnect",
        side_effect=RoborockTimeout(),
    ), patch(
        "homeassistant.components.roborock.RoborockDataUpdateCoordinator.async_config_entry_first_refresh"
    ):
        await async_setup_component(hass, DOMAIN, {})
    assert mock_roborock_entry.state is ConfigEntryState.LOADED
