"""Test for Roborock init."""
from unittest.mock import patch

from roborock.exceptions import RoborockException

from homeassistant.components.roborock.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.setup import async_setup_component

from .mock_data import HOME_DATA, NETWORK_INFO, PROP

from tests.common import MockConfigEntry


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
        assert mock_disconnect.call_count == 2
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


async def test_config_entry_not_ready_home_data(
    hass: HomeAssistant, mock_roborock_entry: MockConfigEntry
) -> None:
    """Test that when we fail to get home data, entry retries."""
    with patch(
        "homeassistant.components.roborock.RoborockApiClient.get_home_data",
        side_effect=RoborockException(),
    ), patch(
        "homeassistant.components.roborock.RoborockDataUpdateCoordinator._async_update_data",
        side_effect=UpdateFailed(),
    ):
        await async_setup_component(hass, DOMAIN, {})
        assert mock_roborock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_get_networking_fails_once(
    hass: HomeAssistant, mock_roborock_entry: MockConfigEntry
) -> None:
    """Test that if networking fails for only one device, we setup the other."""
    with patch(
        "homeassistant.components.roborock.RoborockApiClient.get_home_data",
        return_value=HOME_DATA,
    ), patch(
        "homeassistant.components.roborock.RoborockMqttClient.get_networking",
        return_value=NETWORK_INFO,
    ), patch(
        "homeassistant.components.roborock.coordinator.RoborockLocalClient.get_prop",
        return_value=PROP,
    ), patch(
        "homeassistant.components.roborock.coordinator.RoborockLocalClient.send_message"
    ), patch(
        "homeassistant.components.roborock.RoborockMqttClient.get_networking",
        side_effect=[RoborockException(), NETWORK_INFO],
    ), patch(
        "homeassistant.components.roborock.RoborockMqttClient._wait_response"
    ), patch(
        "homeassistant.components.roborock.coordinator.RoborockLocalClient._wait_response"
    ):
        await async_setup_component(hass, DOMAIN, {})
        assert mock_roborock_entry.state is ConfigEntryState.LOADED


async def test_get_networking_fails_twice(
    hass: HomeAssistant, mock_roborock_entry: MockConfigEntry
) -> None:
    """Test that if networking fails for both devices, we failed to setup."""
    with patch(
        "homeassistant.components.roborock.RoborockApiClient.get_home_data",
        return_value=HOME_DATA,
    ), patch(
        "homeassistant.components.roborock.RoborockMqttClient.get_networking",
        return_value=NETWORK_INFO,
    ), patch(
        "homeassistant.components.roborock.coordinator.RoborockLocalClient.get_prop",
        return_value=PROP,
    ), patch(
        "homeassistant.components.roborock.coordinator.RoborockLocalClient.send_message"
    ), patch(
        "homeassistant.components.roborock.RoborockMqttClient.get_networking",
        side_effect=[RoborockException(), None],
    ):
        await async_setup_component(hass, DOMAIN, {})
        assert mock_roborock_entry.state is ConfigEntryState.SETUP_RETRY
