"""Test the LibreHardwareMonitor sensor."""

from dataclasses import replace
from datetime import timedelta
import logging
from types import MappingProxyType
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from librehardwaremonitor_api import (
    LibreHardwareMonitorConnectionError,
    LibreHardwareMonitorNoDevicesError,
)
from librehardwaremonitor_api.model import (
    DeviceId,
    DeviceName,
    LibreHardwareMonitorData,
    LibreHardwareMonitorSensorData,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.libre_hardware_monitor.const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_sensors_are_created(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_lhm_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensors are created."""
    await init_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "error", [LibreHardwareMonitorConnectionError, LibreHardwareMonitorNoDevicesError]
)
async def test_sensors_go_unavailable_in_case_of_error_and_recover_after_successful_retry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_lhm_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    error: type[Exception],
) -> None:
    """Test sensors go unavailable."""
    await init_integration(hass, mock_config_entry)

    initial_states = hass.states.async_all()
    assert initial_states == snapshot(name="valid_sensor_data")

    mock_lhm_client.get_data.side_effect = error

    freezer.tick(timedelta(DEFAULT_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    unavailable_states = hass.states.async_all()
    assert all(state.state == STATE_UNAVAILABLE for state in unavailable_states)

    mock_lhm_client.get_data.side_effect = None

    freezer.tick(timedelta(DEFAULT_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    recovered_states = hass.states.async_all()
    assert all(state.state != STATE_UNAVAILABLE for state in recovered_states)


async def test_sensors_are_updated(
    hass: HomeAssistant,
    mock_lhm_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors are updated."""
    await init_integration(hass, mock_config_entry)

    entity_id = "sensor.amd_ryzen_7_7800x3d_package_temperature"

    state = hass.states.get(entity_id)

    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "52.8"

    updated_data = dict(mock_lhm_client.get_data.return_value.sensor_data)
    updated_data["amdcpu-0-temperature-3"] = replace(
        updated_data["amdcpu-0-temperature-3"], value="42,1"
    )
    mock_lhm_client.get_data.return_value = replace(
        mock_lhm_client.get_data.return_value,
        sensor_data=MappingProxyType(updated_data),
    )

    freezer.tick(timedelta(DEFAULT_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "42.1"


async def test_sensor_state_is_unknown_when_no_sensor_data_is_provided(
    hass: HomeAssistant,
    mock_lhm_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor state is unknown when sensor data is missing."""
    await init_integration(hass, mock_config_entry)

    entity_id = "sensor.amd_ryzen_7_7800x3d_package_temperature"

    state = hass.states.get(entity_id)

    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "52.8"

    updated_data = dict(mock_lhm_client.get_data.return_value.sensor_data)
    del updated_data["amdcpu-0-temperature-3"]
    mock_lhm_client.get_data.return_value = replace(
        mock_lhm_client.get_data.return_value,
        sensor_data=MappingProxyType(updated_data),
    )

    freezer.tick(timedelta(DEFAULT_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == STATE_UNKNOWN


async def test_orphaned_devices_are_removed(
    hass: HomeAssistant,
    mock_lhm_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that devices in HA that do not receive updates are removed."""
    await init_integration(hass, mock_config_entry)

    mock_lhm_client.get_data.return_value = LibreHardwareMonitorData(
        main_device_ids_and_names=MappingProxyType(
            {
                DeviceId("amdcpu-0"): DeviceName("AMD Ryzen 7 7800X3D"),
                DeviceId("gpu-nvidia-0"): DeviceName("NVIDIA GeForce RTX 4080 SUPER"),
            }
        ),
        sensor_data=mock_lhm_client.get_data.return_value.sensor_data,
    )

    device_registry = dr.async_get(hass)
    orphaned_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, f"{mock_config_entry.entry_id}_lpc-nct6687d-0")},
    )

    with patch.object(
        device_registry,
        "async_remove_device",
        wraps=device_registry.async_update_device,
    ) as mock_remove:
        freezer.tick(timedelta(DEFAULT_SCAN_INTERVAL))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        mock_remove.assert_called_once_with(orphaned_device.id)


async def test_legacy_device_ids_are_updated(
    hass: HomeAssistant,
    mock_lhm_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that non-unique legacy device IDs are updated."""
    # Manually create devices with legacy identifiers first
    legacy_device_ids = ["amdcpu-0", "gpu-nvidia-0", "lpc-nct6687d-0"]

    # Create devices with old identifiers (without entry_id prefix)
    created_devices = []
    for device_id in legacy_device_ids:
        device = device_registry.async_get_or_create(
            config_entry_id=mock_config_entry.entry_id,
            identifiers={(DOMAIN, device_id)},  # Old format without entry_id prefix
            name=f"Test Device {device_id}",
        )
        created_devices.append(device)

    # Verify devices were created with legacy identifiers
    device_entries_before = dr.async_entries_for_config_entry(
        registry=device_registry, config_entry_id=mock_config_entry.entry_id
    )
    assert {
        next(iter(device.identifiers))[1] for device in device_entries_before
    } == set(legacy_device_ids)

    # Initialize integration - should trigger migration
    await init_integration(hass, mock_config_entry)

    # Verify devices now have new identifiers with entry_id prefix
    device_entries_after = dr.async_entries_for_config_entry(
        registry=device_registry, config_entry_id=mock_config_entry.entry_id
    )
    expected_device_ids = [
        f"{mock_config_entry.entry_id}_{device_id}" for device_id in legacy_device_ids
    ]
    assert {
        next(iter(device.identifiers))[1] for device in device_entries_after
    } == set(expected_device_ids)


async def test_unique_id_migration(
    hass: HomeAssistant,
    mock_lhm_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration of entities with old unique ID format."""
    # Manually create entity with old unique ID format first
    old_unique_id = "lhm-test-sensor-id"
    entity_id = "sensor.test_device_test_sensor"

    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        old_unique_id,
        suggested_object_id="test_device_test_sensor",
        config_entry=mock_config_entry,
    )

    # Verify entity exists with old unique ID
    assert (
        entity_registry.async_get_entity_id("sensor", DOMAIN, old_unique_id)
        == entity_id
    )

    # Create sensor data that matches the old entity
    sensor_data = LibreHardwareMonitorSensorData(
        sensor_id="test-sensor-id",
        name="Test Sensor",
        value="50.0",
        unit="°C",
        min="0.0",
        max="100.0",
        device_id="test-device",
        device_name="Test Device",
        device_type="Test",
    )

    # Update mock data
    updated_data = dict(mock_lhm_client.get_data.return_value.sensor_data)
    updated_data["test-sensor-id"] = sensor_data

    mock_lhm_client.get_data.return_value = replace(
        mock_lhm_client.get_data.return_value,
        sensor_data=MappingProxyType(updated_data),
    )

    # Now initialize the integration - this should trigger the migration
    await init_integration(hass, mock_config_entry)

    # Verify entity now has new unique ID
    new_unique_id = f"lhm_{mock_config_entry.entry_id}_test-sensor-id"
    assert (
        entity_registry.async_get_entity_id("sensor", DOMAIN, new_unique_id)
        == entity_id
    )
    assert entity_registry.async_get_entity_id("sensor", DOMAIN, old_unique_id) is None


async def test_integration_does_not_log_new_devices_on_first_refresh(
    hass: HomeAssistant,
    mock_lhm_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that initial data update does not cause warning about new devices."""
    mock_lhm_client.get_data.return_value = LibreHardwareMonitorData(
        main_device_ids_and_names=MappingProxyType(
            {
                **mock_lhm_client.get_data.return_value.main_device_ids_and_names,
                DeviceId("generic-memory"): DeviceName("Generic Memory"),
            }
        ),
        sensor_data=mock_lhm_client.get_data.return_value.sensor_data,
    )

    with caplog.at_level(logging.WARNING):
        await init_integration(hass, mock_config_entry)
        assert len(caplog.records) == 0
