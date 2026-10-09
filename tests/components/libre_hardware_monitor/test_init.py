"""Tests for the LibreHardwareMonitor init."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.libre_hardware_monitor.const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LEGACY_THROUGHPUT_UNIT,
)
from homeassistant.components.libre_hardware_monitor.recorder import (
    async_custom_equivalent_units,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, UnitOfDataRate
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
    assert updated_config_entry.minor_version == 2


@pytest.mark.parametrize(
    ("version", "minor_version", "unique_id_prefix"),
    [
        pytest.param(1, 1, "lhm-", id="from_v1"),
        pytest.param(2, 1, "test_entry_id_", id="from_v2_minor_1"),
    ],
)
@pytest.mark.usefixtures("mock_lhm_client", "recorder_mock")
async def test_migration_to_sensor_device_classes(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    version: int,
    minor_version: int,
    unique_id_prefix: str,
) -> None:
    """Test that throughput sensor units are updated from every legacy version."""
    legacy_config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="192.168.0.20:8085",
        data=VALID_CONFIG,
        entry_id="test_entry_id",
        version=version,
        minor_version=minor_version,
    )
    legacy_config_entry.add_to_hass(hass)

    # Set up throughput sensor with old unit
    object_id = "nvidia_geforce_rtx_4080_gpu_pcie_tx_throughput"
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{unique_id_prefix}gpu-nvidia-0-throughput-1",
        suggested_object_id=object_id,
        config_entry=legacy_config_entry,
        unit_of_measurement=LEGACY_THROUGHPUT_UNIT,
    )

    await init_integration(hass, legacy_config_entry)

    entity_entry = entity_registry.async_get(f"sensor.{object_id}")
    assert entity_entry.unit_of_measurement == UnitOfDataRate.KIBIBYTES_PER_SECOND

    # the entity keeps reporting the migrated unit once it is set up
    state = hass.states.get(f"sensor.{object_id}")
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == (
        UnitOfDataRate.KIBIBYTES_PER_SECOND
    )

    custom_equivalent_units = async_custom_equivalent_units(hass)
    assert custom_equivalent_units == {
        f"sensor.{object_id}": {
            LEGACY_THROUGHPUT_UNIT: UnitOfDataRate.KIBIBYTES_PER_SECOND
        }
    }

    updated_config_entry = hass.config_entries.async_get_entry(
        legacy_config_entry.entry_id
    )
    assert updated_config_entry.version == 2
    assert updated_config_entry.minor_version == 2


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
