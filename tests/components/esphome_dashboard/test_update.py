"""Test the ESPHome Dashboard update platform."""

from unittest.mock import AsyncMock

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_update_entities(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test update entities are created correctly."""
    # Check that update entities are created
    state = hass.states.get("update.test_device")
    assert state is not None
    assert state.state == STATE_ON  # Update available
    assert state.attributes["installed_version"] == "2023.12.0"
    assert state.attributes["latest_version"] == "2024.1.0"

    state2 = hass.states.get("update.test_device_2")
    assert state2 is not None
    assert state2.state == STATE_OFF  # No update available
    assert state2.attributes["installed_version"] == "2023.11.0"
    assert state2.attributes["latest_version"] == "2023.11.0"

    # Verify entity registry entries
    entry = entity_registry.async_get("update.test_device")
    assert entry
    assert entry.unique_id == f"{init_integration.entry_id}_test_device"

    entry2 = entity_registry.async_get("update.test_device_2")
    assert entry2
    assert entry2.unique_id == f"{init_integration.entry_id}_test_device_2"


async def test_update_entity_device_removed(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_dashboard_api
) -> None:
    """Test update entity when device is removed from dashboard."""
    # Initially device exists
    state = hass.states.get("update.test_device")
    assert state is not None
    assert state.state == STATE_ON

    # Update coordinator data to remove device
    mock_dashboard_api.get_devices = AsyncMock(
        return_value={
            "configured": [
                {
                    "name": "test_device_2",
                    "current_version": "2023.11.0",
                    "target_version": "2023.11.0",
                    "configuration": "test_device_2.yaml",
                }
            ]
        }
    )

    # Trigger coordinator update
    coordinator = init_integration.runtime_data.coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Entity should now be unavailable
    state = hass.states.get("update.test_device")
    assert state is not None
    assert state.state == "unavailable"


async def test_coordinator_update_failure(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_dashboard_api
) -> None:
    """Test coordinator update failure."""
    # Initially entities are available
    state = hass.states.get("update.test_device")
    assert state is not None
    assert state.state == STATE_ON

    # Make API fail
    mock_dashboard_api.get_devices = AsyncMock(
        side_effect=Exception("Connection error")
    )

    # Trigger coordinator update
    coordinator = init_integration.runtime_data.coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Entities should become unavailable
    state = hass.states.get("update.test_device")
    assert state is not None
    assert state.state == "unavailable"


async def test_dynamic_device_addition(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_dashboard_api
) -> None:
    """Test that new devices are added dynamically."""
    # Initially two devices
    state = hass.states.get("update.test_device")
    assert state is not None
    state2 = hass.states.get("update.test_device_2")
    assert state2 is not None

    # No third device yet
    state3 = hass.states.get("update.test_device_3")
    assert state3 is None

    # Update coordinator data to add a new device
    mock_dashboard_api.get_devices = AsyncMock(
        return_value={
            "configured": [
                {
                    "name": "test_device",
                    "current_version": "2023.12.0",
                    "target_version": "2024.1.0",
                    "configuration": "test_device.yaml",
                },
                {
                    "name": "test_device_2",
                    "current_version": "2023.11.0",
                    "target_version": "2023.11.0",
                    "configuration": "test_device_2.yaml",
                },
                {
                    "name": "test_device_3",
                    "current_version": "2024.2.0",
                    "target_version": "2024.2.0",
                    "configuration": "test_device_3.yaml",
                },
            ]
        }
    )

    # Trigger coordinator update
    coordinator = init_integration.runtime_data.coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Third device should now exist
    state3 = hass.states.get("update.test_device_3")
    assert state3 is not None
    assert state3.state == STATE_OFF
    assert state3.attributes["installed_version"] == "2024.2.0"
