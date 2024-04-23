"""Test for Roborock init."""

from unittest.mock import patch

from roborock import RoborockException, RoborockInvalidCredentials

from homeassistant.components.roborock.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_unload_entry(
    hass: HomeAssistant, bypass_api_fixture, setup_entry: MockConfigEntry
) -> None:
    """Test unloading roboorck integration."""
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert setup_entry.state is ConfigEntryState.LOADED
    with patch(
        "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.async_release"
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
    with (
        patch(
            "homeassistant.components.roborock.RoborockApiClient.get_home_data",
        ),
        patch(
            "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.get_prop",
            side_effect=RoborockException(),
        ),
    ):
        await async_setup_component(hass, DOMAIN, {})
        assert mock_roborock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_entry_not_ready_home_data(
    hass: HomeAssistant, mock_roborock_entry: MockConfigEntry
) -> None:
    """Test that when we fail to get home data, entry retries."""
    with (
        patch(
            "homeassistant.components.roborock.RoborockApiClient.get_home_data",
            side_effect=RoborockException(),
        ),
        patch(
            "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.get_prop",
            side_effect=RoborockException(),
        ),
    ):
        await async_setup_component(hass, DOMAIN, {})
        assert mock_roborock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_get_networking_fails(
    hass: HomeAssistant, mock_roborock_entry: MockConfigEntry, bypass_api_fixture
) -> None:
    """Test that when networking fails, we attempt to retry."""
    with patch(
        "homeassistant.components.roborock.RoborockMqttClientV1.get_networking",
        side_effect=RoborockException(),
    ):
        await async_setup_component(hass, DOMAIN, {})
        assert mock_roborock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_get_networking_fails_none(
    hass: HomeAssistant, mock_roborock_entry: MockConfigEntry, bypass_api_fixture
) -> None:
    """Test that when networking returns None, we attempt to retry."""
    with patch(
        "homeassistant.components.roborock.RoborockMqttClientV1.get_networking",
        return_value=None,
    ):
        await async_setup_component(hass, DOMAIN, {})
        assert mock_roborock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_cloud_client_fails_props(
    hass: HomeAssistant, mock_roborock_entry: MockConfigEntry, bypass_api_fixture
) -> None:
    """Test that if networking succeeds, but we can't communicate with the vacuum, we can't get props, fail."""
    with (
        patch(
            "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.ping",
            side_effect=RoborockException(),
        ),
        patch(
            "homeassistant.components.roborock.coordinator.RoborockMqttClientV1.get_prop",
            side_effect=RoborockException(),
        ),
    ):
        await async_setup_component(hass, DOMAIN, {})
        assert mock_roborock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_local_client_fails_props(
    hass: HomeAssistant, mock_roborock_entry: MockConfigEntry, bypass_api_fixture
) -> None:
    """Test that if networking succeeds, but we can't communicate locally with the vacuum, we can't get props, fail."""
    with patch(
        "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.get_prop",
        side_effect=RoborockException(),
    ):
        await async_setup_component(hass, DOMAIN, {})
        assert mock_roborock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_fails_maps_continue(
    hass: HomeAssistant, mock_roborock_entry: MockConfigEntry, bypass_api_fixture
) -> None:
    """Test that if we fail to get the maps, we still setup."""
    with patch(
        "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.get_multi_maps_list",
        side_effect=RoborockException(),
    ):
        await async_setup_component(hass, DOMAIN, {})
        assert mock_roborock_entry.state is ConfigEntryState.LOADED
        # No map data means no images
        assert len(hass.states.async_all("image")) == 0


async def test_reauth_started(
    hass: HomeAssistant, bypass_api_fixture, mock_roborock_entry: MockConfigEntry
) -> None:
    """Test reauth flow started."""
    with patch(
        "homeassistant.components.roborock.RoborockApiClient.get_home_data",
        side_effect=RoborockInvalidCredentials(),
    ):
        await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        assert mock_roborock_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"
