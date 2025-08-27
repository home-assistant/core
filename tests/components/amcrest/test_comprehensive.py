"""Test comprehensive device and entity creation."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.amcrest.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


async def test_comprehensive_device_creation(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    caplog,
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
    device = device_registry.async_get_device(identifiers={(DOMAIN, "ABCD1234567890")})

    if device is None:
        _LOGGER.debug(
            "Device not found with config entry ID, checking with all possible identifiers..."
        )
        # Try to find device with any amcrest identifier
        for dev in device_registry.devices.values():
            for identifier in dev.identifiers:
                if identifier[0] == DOMAIN:
                    _LOGGER.debug(
                        "Found Amcrest device: %s, identifiers: %s",
                        dev.name,
                        dev.identifiers,
                    )

    assert device is not None, "Device should be registered in device registry"

    # Test basic device properties
    assert device.name == "Living Room"
    assert device.manufacturer == "Amcrest"

    # Test entities are linked to device
    camera_entity = entity_registry.async_get("camera.living_room_camera")
    if camera_entity:
        assert camera_entity.device_id == device.id
        assert camera_entity.platform == DOMAIN
