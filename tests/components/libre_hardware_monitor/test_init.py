"""Tests for the LibreHardwareMonitor init."""

import logging

from homeassistant.components.libre_hardware_monitor.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import init_integration
from .conftest import VALID_CONFIG

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


async def test_migration_to_unique_ids(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that non-unique legacy entity and device IDs are updated."""
    legacy_config_entry_v1 = MockConfigEntry(
        domain=DOMAIN,
        title="192.168.0.20:8085",
        data=VALID_CONFIG,
        entry_id="test_entry_id",
        version=1,
    )
    legacy_config_entry_v1.add_to_hass(hass)

    # Set up devices with legacy device ID
    legacy_device_ids = ["amdcpu-0", "gpu-nvidia-0", "lpc-nct6687d-0"]
    for device_id in legacy_device_ids:
        device_registry.async_get_or_create(
            config_entry_id=legacy_config_entry_v1.entry_id,
            identifiers={(DOMAIN, device_id)},  # Old format without entry_id prefix
            name=f"Test Device {device_id}",
        )

    # Set up entity with legacy entity ID
    existing_sensor_id = "lpc-nct6687d-0-voltage-0"
    legacy_entity_id = f"lhm-{existing_sensor_id}"

    entity_object_id = "sensor.msi_mag_b650m_mortar_wifi_ms_7d76_12v_voltage"
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        legacy_entity_id,
        suggested_object_id="msi_mag_b650m_mortar_wifi_ms_7d76_12v_voltage",
        config_entry=legacy_config_entry_v1,
    )

    # Verify state before migration
    device_entries_before = dr.async_entries_for_config_entry(
        registry=device_registry, config_entry_id=legacy_config_entry_v1.entry_id
    )
    assert {
        next(iter(device.identifiers))[1] for device in device_entries_before
    } == set(legacy_device_ids)

    assert (
        entity_registry.async_get_entity_id("sensor", DOMAIN, legacy_entity_id)
        == entity_object_id
    )

    await init_integration(hass, legacy_config_entry_v1)

    # Verify state after migration
    device_entries_after = dr.async_entries_for_config_entry(
        registry=device_registry, config_entry_id=legacy_config_entry_v1.entry_id
    )
    expected_unique_device_ids = [
        f"{legacy_config_entry_v1.entry_id}_{device_id}"
        for device_id in legacy_device_ids
    ]
    assert {
        next(iter(device.identifiers))[1] for device in device_entries_after
    } == set(expected_unique_device_ids)

    entity_entry = entity_registry.async_get(entity_object_id)
    assert entity_entry is not None, "Entity should exist after migration"

    new_unique_entity_id = f"{legacy_config_entry_v1.entry_id}_{existing_sensor_id}"
    assert entity_entry.unique_id == new_unique_entity_id, (
        f"Unique ID not migrated: {entity_entry.unique_id}"
    )

    assert (
        entity_registry.async_get_entity_id("sensor", DOMAIN, legacy_entity_id) is None
    )
