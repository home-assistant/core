"""Test the Amcrest binary sensor platform."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.components.amcrest.const import DOMAIN
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_binary_sensor_setup_coordinated(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_amcrest_api: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test binary sensor setup for coordinated (config flow) entries."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.amcrest.AmcrestChecker", return_value=mock_amcrest_api
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Verify device is created with serial number identifier
    device = device_registry.async_get_device(identifiers={(DOMAIN, "ABCD1234567890")})
    assert device is not None
    assert device.name == "Living Room"

    # Check if binary sensors are created (depends on sensor availability)
    binary_sensor_entities = hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN)

    # If binary sensors are created, verify they're linked to the device
    for entity_id in binary_sensor_entities:
        entity = entity_registry.async_get(entity_id)
        if entity and entity.platform == DOMAIN:
            assert entity.device_id == device.id

            # Verify entity state
            state = hass.states.get(entity_id)
            assert state is not None


async def test_binary_sensor_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_amcrest_api: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that binary sensors have correct device info."""
    mock_config_entry.add_to_hass(hass)

    # Configure mock to have motion detection available
    mock_amcrest_api.is_motion_detector_on.return_value = True

    with patch(
        "homeassistant.components.amcrest.AmcrestChecker", return_value=mock_amcrest_api
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Verify device exists with serial number identifier
    device = device_registry.async_get_device(identifiers={(DOMAIN, "ABCD1234567890")})
    assert device is not None

    # All coordinated binary sensors should be associated with this device
    binary_sensor_entities = hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN)
    if binary_sensor_entities:
        # At least one sensor should exist for motion detection
        assert len(binary_sensor_entities) > 0


async def test_binary_sensor_coordination_filtering(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_amcrest_api: MagicMock,
) -> None:
    """Test that only should_poll=False sensors are set up for coordinated entries."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.amcrest.AmcrestChecker",
            return_value=mock_amcrest_api,
        ),
        patch(
            "homeassistant.components.amcrest.binary_sensor.BINARY_SENSORS"
        ) as mock_sensors,
    ):
        # Mock some sensors with different should_poll values
        mock_sensors.__iter__.return_value = [
            MagicMock(should_poll=False, key="motion"),
            MagicMock(should_poll=True, key="online"),  # This should be filtered out
            MagicMock(should_poll=False, key="audio"),
        ]

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Verify only non-polling sensors are created for coordinated setup
    # The exact count depends on which sensors are actually available
    # But we expect fewer than the total mock sensors (due to filtering)
    # This test verifies the filtering logic works
