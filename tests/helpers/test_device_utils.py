"""Tests for the Device Utils."""

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    device_utils as du,
    entity_registry as er,
)

from tests.common import MockConfigEntry


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

    # Only with the entity id
    result = await du.async_device_info_to_link(hass, entity_id=source_entity.entity_id)
    assert result == {
        "identifiers": {("test", "my_device")},
        "connections": {("mac", "30:31:32:33:34:00")},
    }

    # Only with the device id
    result = await du.async_device_info_to_link(hass, device_id=device.id)
    assert result == {
        "identifiers": {("test", "my_device")},
        "connections": {("mac", "30:31:32:33:34:00")},
    }

    # With a non-existent entity id
    result = await du.async_device_info_to_link(hass, entity_id="sensor.invalid")
    assert result is None

    # With a non-existent device id
    result = await du.async_device_info_to_link(hass, device_id="abcdefghi")
    assert result is None

    # Without informing one of the entity_id or device_id parameters
    result = await du.async_device_info_to_link(hass)
    assert result is None


@pytest.mark.parametrize(
    ("test_entity_id", "test_device_id"),
    [(True, False), (False, True), (True, True), (False, False)],
)
async def test_remove_stale_device_links_helpers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    test_entity_id: bool,
    test_device_id: bool,
) -> None:
    """Test cleanup works."""
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
    await du.async_remove_stale_device_links_helpers(
        hass,
        entry_id=config_entry.entry_id,
        source_entity_id=source_entity.entity_id if test_entity_id else None,
        device_id=current_device.id if test_device_id else None,
    )

    devices_config_entry = device_registry.devices.get_devices_for_config_entry_id(
        config_entry.entry_id
    )

    # After cleanup, only one device is expected to be linked to the configuration entry if at least source_entity_id or device_id was given, else zero
    assert len(devices_config_entry) == (1 if (test_entity_id or test_device_id) else 0)
