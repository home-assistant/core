"""Tests for the Device Utils."""

import pytest
import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device import (
    async_device_info_to_link_from_device_id,
    async_device_info_to_link_from_entity,
    async_entity_id_to_device_id,
    async_remove_stale_devices_links_keep_current_device,
    async_remove_stale_devices_links_keep_entity_device,
)

from tests.common import MockConfigEntry


async def test_entity_id_to_device_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test returning an entity's device ID."""
    config_entry = MockConfigEntry(domain="my")
    config_entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        identifiers={("test", "current_device")},
        connections={("mac", "30:31:32:33:34:00")},
        config_entry_id=config_entry.entry_id,
    )
    assert device is not None

    # Entity registry
    entity = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "source",
        config_entry=config_entry,
        device_id=device.id,
    )
    await hass.async_block_till_done()
    assert entity_registry.async_get("sensor.test_source") is not None

    device_id = async_entity_id_to_device_id(
        hass,
        entity_id_or_uuid=entity.entity_id,
    )
    assert device_id == device.id

    with pytest.raises(vol.Invalid):
        async_entity_id_to_device_id(
            hass,
            entity_id_or_uuid="unknown_uuid",
        )


async def test_device_info_to_link(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for returning device info with device link information."""
    config_entry = MockConfigEntry(domain="my")
    config_entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        identifiers={("test", "my_device")},
        connections={("mac", "30:31:32:33:34:00")},
        config_entry_id=config_entry.entry_id,
    )
    assert device is not None

    # Source entity registry
    source_entity = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "source",
        config_entry=config_entry,
        device_id=device.id,
    )
    await hass.async_block_till_done()
    assert entity_registry.async_get("sensor.test_source") is not None

    result = async_device_info_to_link_from_entity(
        hass, entity_id_or_uuid=source_entity.entity_id
    )
    assert result == {
        "identifiers": {("test", "my_device")},
        "connections": {("mac", "30:31:32:33:34:00")},
    }

    result = async_device_info_to_link_from_device_id(hass, device_id=device.id)
    assert result == {
        "identifiers": {("test", "my_device")},
        "connections": {("mac", "30:31:32:33:34:00")},
    }

    # With a non-existent entity id
    result = async_device_info_to_link_from_entity(
        hass, entity_id_or_uuid="sensor.invalid"
    )
    assert result is None

    # With a non-existent device id
    result = async_device_info_to_link_from_device_id(hass, device_id="abcdefghi")
    assert result is None

    # With a None device id
    result = async_device_info_to_link_from_device_id(hass, device_id=None)
    assert result is None


async def test_remove_stale_device_links_keep_entity_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test cleaning works for entity."""
    config_entry = MockConfigEntry(domain="hue")
    config_entry.add_to_hass(hass)

    current_device = device_registry.async_get_or_create(
        identifiers={("test", "current_device")},
        connections={("mac", "30:31:32:33:34:00")},
        config_entry_id=config_entry.entry_id,
    )
    assert current_device is not None

    device_registry.async_get_or_create(
        identifiers={("test", "stale_device_1")},
        connections={("mac", "30:31:32:33:34:01")},
        config_entry_id=config_entry.entry_id,
    )

    device_registry.async_get_or_create(
        identifiers={("test", "stale_device_2")},
        connections={("mac", "30:31:32:33:34:02")},
        config_entry_id=config_entry.entry_id,
    )

    # Source entity registry
    source_entity = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "source",
        config_entry=config_entry,
        device_id=current_device.id,
    )
    await hass.async_block_till_done()
    assert entity_registry.async_get("sensor.test_source") is not None

    devices_config_entry = device_registry.devices.get_devices_for_config_entry_id(
        config_entry.entry_id
    )

    # 3 devices linked to the config entry are expected (1 current device + 2 stales)
    assert len(devices_config_entry) == 3

    # Manual cleanup should unlink stales devices from the config entry
    async_remove_stale_devices_links_keep_entity_device(
        hass,
        entry_id=config_entry.entry_id,
        source_entity_id_or_uuid=source_entity.entity_id,
    )

    devices_config_entry = device_registry.devices.get_devices_for_config_entry_id(
        config_entry.entry_id
    )

    # After cleanup, only one device is expected to be linked to the config entry
    assert len(devices_config_entry) == 1

    assert current_device in devices_config_entry


async def test_remove_stale_devices_links_keep_current_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test cleanup works for device id."""
    config_entry = MockConfigEntry(domain="hue")
    config_entry.add_to_hass(hass)

    current_device = device_registry.async_get_or_create(
        identifiers={("test", "current_device")},
        connections={("mac", "30:31:32:33:34:00")},
        config_entry_id=config_entry.entry_id,
    )
    assert current_device is not None

    device_registry.async_get_or_create(
        identifiers={("test", "stale_device_1")},
        connections={("mac", "30:31:32:33:34:01")},
        config_entry_id=config_entry.entry_id,
    )

    device_registry.async_get_or_create(
        identifiers={("test", "stale_device_2")},
        connections={("mac", "30:31:32:33:34:02")},
        config_entry_id=config_entry.entry_id,
    )

    devices_config_entry = device_registry.devices.get_devices_for_config_entry_id(
        config_entry.entry_id
    )

    # 3 devices linked to the config entry are expected (1 current device + 2 stales)
    assert len(devices_config_entry) == 3

    # Manual cleanup should unlink stales devices from the config entry
    async_remove_stale_devices_links_keep_current_device(
        hass,
        entry_id=config_entry.entry_id,
        current_device_id=current_device.id,
    )

    devices_config_entry = device_registry.devices.get_devices_for_config_entry_id(
        config_entry.entry_id
    )

    # After cleanup, only one device is expected to be linked to the config entry
    assert len(devices_config_entry) == 1

    assert current_device in devices_config_entry
