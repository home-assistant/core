"""Test comprehensive device and entity creation verification."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.components.amcrest.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_device_and_entity_creation_verification(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
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

    # Check basic setup worked
    assert result is True

    # Wait for entity platform setup to complete
    await hass.async_block_till_done()

    # Test 1: Check states are created
    all_states = hass.states.async_all()
    amcrest_states = [
        state
        for state in all_states
        if state.entity_id.startswith(
            ("binary_sensor.living_room_", "camera.living_room_")
        )
    ]
    assert len(amcrest_states) > 0, (
        f"Expected Amcrest entities to be created, found states: {[s.entity_id for s in all_states]}"
    )

    # Test 2: Check device registry
    devices = device_registry.devices
    amcrest_devices = []
    for device in devices.values():
        for identifier in device.identifiers:
            if identifier[0] == DOMAIN:
                amcrest_devices.append(device)
                break

    # Verify device is registered
    assert len(amcrest_devices) > 0, (
        f"Expected at least one Amcrest device in registry. Found devices: {[d.name for d in devices.values()]}"
    )

    # The key device should be registered with serial number identifier
    device = device_registry.async_get_device(identifiers={(DOMAIN, "ABCD1234567890")})  # type: ignore[assignment]
    assert device is not None, (
        "Device should be registered with serial number identifier"
    )
    assert device.name == "Living Room"
    assert device.manufacturer == "Amcrest"

    # Test 3: Check entity registry
    entities = entity_registry.entities
    amcrest_entities = [
        entity for entity in entities.values() if entity.platform == DOMAIN
    ]

    # We should have entities registered in the entity registry
    assert len(amcrest_entities) > 0, (
        f"Expected Amcrest entities in registry. Found entities: {list(entities.keys())}"
    )

    # Test 4: All entities should be linked to the device
    for entity in amcrest_entities:
        assert entity.device_id == device.id, (
            f"Entity {entity.entity_id} should be linked to device {device.id}"
        )

    # Test 5: Check that entities have unique IDs
    for entity in amcrest_entities:
        assert entity.unique_id is not None, (
            f"Entity {entity.entity_id} should have a unique ID"
        )
        assert "ABCD1234567890" in entity.unique_id, (
            f"Entity {entity.entity_id} unique ID should contain serial number"
        )

    # Test 6: Basic functionality - camera should be present
    camera_entities = [e for e in amcrest_entities if e.entity_id.startswith("camera.")]
    assert len(camera_entities) >= 1, "At least one camera entity should be created"

    # Test 7: Binary sensors should be present (based on polling config)
    binary_sensor_entities = [
        e for e in amcrest_entities if e.entity_id.startswith("binary_sensor.")
    ]
    assert len(binary_sensor_entities) >= 1, (
        "At least one binary sensor entity should be created"
    )
