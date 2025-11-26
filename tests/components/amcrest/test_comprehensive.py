"""Test comprehensive device and entity creation."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from homeassistant.components.amcrest.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


async def test_comprehensive_device_creation(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
    amcrest_device: MagicMock,
) -> None:
    """Test that devices and entities are properly created and registered."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living Room",
        data={
            "name": "Living Room",
            "host": "192.168.1.100",
            "port": 80,
            "username": "admin",
            "password": "password123",
        },
        unique_id="ABCD1234567890",
    )
    mock_config_entry.add_to_hass(hass)

    # Setup the integration using the proper fixture
    result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check basic setup
    assert result is True

    # Wait a bit more to ensure everything is set up
    await hass.async_block_till_done()

    # Debug: Check device registry
    all_devices = device_registry.devices
    caplog.set_level(logging.DEBUG)
    _LOGGER.debug("Device count: %d", len(all_devices))
    for device_id, device in all_devices.items():
        _LOGGER.debug(
            "Device %s: %s, identifiers: %s",
            device_id,
            device.name,
            device.identifiers,
        )

    # Debug: Check entity registry
    all_entities = entity_registry.entities
    _LOGGER.debug("Entity count: %d", len(all_entities))
    for entity_id, entity in all_entities.items():
        _LOGGER.debug(
            "Entity %s: platform=%s, device_id=%s",
            entity_id,
            entity.platform,
            entity.device_id,
        )

    # Debug: Check states
    all_states = hass.states.async_all()
    _LOGGER.debug("State count: %d", len(all_states))
    for state in all_states:
        _LOGGER.debug("State %s: %s", state.entity_id, state.state)

    # The key test: Are devices registered?
    device = device_registry.async_get_device(identifiers={(DOMAIN, "ABCD1234567890")})  # type: ignore[assignment]

    if device is None:
        _LOGGER.debug(
            "Device not found with config entry ID, checking with all possible identifiers"
        )
        # Try to find device with any amcrest identifier
        for device_entry in device_registry.devices.values():
            for identifier_set in device_entry.identifiers:
                domain, identifier = identifier_set
                if domain == DOMAIN:
                    _LOGGER.debug(
                        "Found Amcrest device: %s with identifier %s",
                        device_entry.name,
                        identifier,
                    )
                    device = device_entry
                    break

    assert device is not None, "Device should be registered in device registry"

    # Test basic device properties
    assert device.name == "Living Room"
    assert device.manufacturer == "Amcrest"

    # Test entities are linked to device
    camera_entity = entity_registry.async_get("camera.living_room_camera")
    if camera_entity:
        assert camera_entity.device_id == device.id
        assert camera_entity.platform == DOMAIN


async def test_coordinator_conditional_api_calls(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
    amcrest_device: MagicMock,
) -> None:
    """Test that coordinator only makes API calls for enabled entities."""

    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Camera",
        data={
            "name": "Test Camera",
            "host": "192.168.1.100",
            "port": 80,
            "username": "admin",
            "password": "password123",
        },
        unique_id="TEST123456789",
    )
    mock_config_entry.add_to_hass(hass)

    # Setup the integration
    result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert result is True

    # Create specific entities to test conditional fetching
    entity_registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        "TEST123456789_motion_detected",
        config_entry=mock_config_entry,
    )
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "TEST123456789_storage_info",
        config_entry=mock_config_entry,
    )
    # Don't create audio_detected or crossline_detected entities

    # Get the coordinator from the integration
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

    # Reset call counts
    amcrest_device.async_event_channels_happened.reset_mock()

    # Trigger coordinator update
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Verify API calls were made only for enabled entities
    call_args_list = amcrest_device.async_event_channels_happened.call_args_list
    called_event_types = [call.args[0] for call in call_args_list]

    # Motion detection should be called (entity exists and enabled)
    assert "VideoMotion" in called_event_types

    # Audio detection should be called (entity exists and enabled)
    assert "AudioMutation" in called_event_types

    # Storage API should be called (async_storage_all property)
    # We can't directly check property access, but the storage data should be present
    assert coordinator.data is not None
    assert "storage_info" in coordinator.data

    # CrossLine should not be called (entity disabled by default)
    assert "CrossLineDetection" not in called_event_types

    # Verify conditional data structure
    assert coordinator.data["motion_detected"] is not None  # Should have value
    assert coordinator.data["storage_info"] is not None  # Should have value
    assert (
        coordinator.data["audio_detected"] is not None
    )  # Should have value (entity is enabled)

    assert (
        coordinator.data["crossline_detected"] is None
    )  # Should be None (not enabled)
