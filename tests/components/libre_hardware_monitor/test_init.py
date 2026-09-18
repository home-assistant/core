"""Tests for the LibreHardwareMonitor init."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.libre_hardware_monitor.const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import init_integration
from .conftest import VALID_CONFIG

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("mock_lhm_client")
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
    legacy_device_ids = ["amdcpu-0", "gpu-nvidia-0", "motherboard"]
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

    updated_config_entry = hass.config_entries.async_get_entry(
        legacy_config_entry_v1.entry_id
    )
    assert updated_config_entry.version == 2


@pytest.mark.usefixtures("mock_deprecated_lhm_client")
async def test_deprecated_version_blocks_setup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that a deprecated LHM version prevents setup with an error."""
    await init_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.error_reason_translation_domain == DOMAIN
    assert mock_config_entry.error_reason_translation_key == "deprecated_version"


async def test_downgrade_to_deprecated_version_fails_entry(
    hass: HomeAssistant,
    mock_lhm_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that downgrading to a deprecated LHM version while running fails the entry."""
    await init_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_lhm_client.get_data.return_value = replace(
        mock_lhm_client.get_data.return_value, is_deprecated_version=True
    )

    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.error_reason_translation_domain == DOMAIN
    assert mock_config_entry.error_reason_translation_key == "deprecated_version"
