"""Tests for the LibreHardwareMonitor init."""

import logging
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.libre_hardware_monitor.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import init_integration
from .conftest import VALID_CONFIG

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


@pytest.mark.usefixtures("mock_lhm_client")
async def test_unique_id_migration(
    hass: HomeAssistant,
    mock_lhm_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration of entities with old unique ID format."""
    config_entry_v1 = MockConfigEntry(
        domain=DOMAIN,
        title="192.168.0.20:8085",
        data=VALID_CONFIG,
        entry_id="test_entry_id",
        version=1,
    )

    config_entry_v1.add_to_hass(hass)

    actual_sensor_id = "lpc-nct6687d-0-voltage-0"

    old_unique_id = f"lhm-{actual_sensor_id}"
    entity_id = "sensor.msi_mag_b650m_mortar_wifi_ms_7d76_12v_voltage"

    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        old_unique_id,
        suggested_object_id="msi_mag_b650m_mortar_wifi_ms_7d76_12v_voltage",
        config_entry=config_entry_v1,
    )

    assert (
        entity_registry.async_get_entity_id("sensor", DOMAIN, old_unique_id)
        == entity_id
    )

    await hass.async_block_till_done()

    entity_registry_after = er.async_get(hass)
    assert (
        entity_registry_after.async_get_entity_id("sensor", DOMAIN, old_unique_id)
        == entity_id
    )

    await init_integration(hass, config_entry_v1)

    await hass.async_block_till_done()

    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None, "Entity should exist after migration"

    new_unique_id = f"{config_entry_v1.entry_id}_{actual_sensor_id}"
    assert entity_entry.unique_id == new_unique_id, (
        f"Unique ID not migrated: {entity_entry.unique_id}"
    )

    assert entity_registry.async_get_entity_id("sensor", DOMAIN, old_unique_id) is None


async def test_legacy_device_ids_are_updated(
    hass: HomeAssistant,
    mock_lhm_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that non-unique legacy device IDs are updated."""
    mock_config_entry.add_to_hass(hass)

    legacy_device_ids = ["amdcpu-0", "gpu-nvidia-0", "lpc-nct6687d-0"]

    created_devices = []
    for device_id in legacy_device_ids:
        device = device_registry.async_get_or_create(
            config_entry_id=mock_config_entry.entry_id,
            identifiers={(DOMAIN, device_id)},  # Old format without entry_id prefix
            name=f"Test Device {device_id}",
        )
        created_devices.append(device)

    device_entries_before = dr.async_entries_for_config_entry(
        registry=device_registry, config_entry_id=mock_config_entry.entry_id
    )
    assert {
        next(iter(device.identifiers))[1] for device in device_entries_before
    } == set(legacy_device_ids)

    await init_integration(hass, mock_config_entry)

    device_entries_after = dr.async_entries_for_config_entry(
        registry=device_registry, config_entry_id=mock_config_entry.entry_id
    )
    expected_device_ids = [
        f"{mock_config_entry.entry_id}_{device_id}" for device_id in legacy_device_ids
    ]
    assert {
        next(iter(device.identifiers))[1] for device in device_entries_after
    } == set(expected_device_ids)
