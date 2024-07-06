"""Test the MadVR coordinator."""

from unittest.mock import patch

from homeassistant.components.madvr.coordinator import MadVRCoordinator
from homeassistant.core import HomeAssistant

from .const import MOCK_MAC


async def test_coordinator_initialization(
    hass: HomeAssistant, mock_madvr_client, mock_config_entry
) -> None:
    """Test MadVRCoordinator initialization and update."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.madvr.PLATFORMS", []):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    assert isinstance(coordinator, MadVRCoordinator)
    assert coordinator.mac == MOCK_MAC

    # Simulate initial data push
    initial_data = {
        "mac_address": MOCK_MAC,
        "incoming_res": "1080p",
    }
    coordinator.handle_push_data(initial_data)
    await hass.async_block_till_done()
    assert coordinator.data == initial_data

    # Simulate update
    updated_data = {
        "mac_address": MOCK_MAC,
        "incoming_res": "4k",
    }
    coordinator.handle_push_data(updated_data)
    await hass.async_block_till_done()
    assert coordinator.data == updated_data


async def test_coordinator_error_handling(
    hass: HomeAssistant, mock_madvr_client, mock_config_entry
) -> None:
    """Test MadVRCoordinator error handling."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.madvr.PLATFORMS", []):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    assert coordinator.mac == MOCK_MAC

    # Simulate error
    error_data = {"error": "Connection error"}
    coordinator.handle_push_data(error_data)
    await hass.async_block_till_done()
    assert coordinator.data == error_data

    # Simulate recovery
    valid_data = {"mac_address": MOCK_MAC, "incoming_res": "1080p"}
    coordinator.handle_push_data(valid_data)
    await hass.async_block_till_done()
    assert coordinator.data == valid_data
