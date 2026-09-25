"""Test the LibreHardwareMonitor sensor."""

from dataclasses import replace
from datetime import timedelta
from types import MappingProxyType
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from librehardwaremonitor_api import (
    LibreHardwareMonitorConnectionError,
    LibreHardwareMonitorNoDevicesError,
    LibreHardwareMonitorUnauthorizedError,
)
from librehardwaremonitor_api.model import (
    DeviceId,
    DeviceName,
    LibreHardwareMonitorSensorData,
)
from librehardwaremonitor_api.sensor_type import SensorType
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.libre_hardware_monitor.const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfConductivity,
    UnitOfDataRate,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfInformation,
    UnitOfPower,
    UnitOfSoundPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry

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
    ("sensor_type", "lhm_unit", "expected_device_class", "expected_unit"),
    [
        pytest.param(
            SensorType.VOLTAGE,
            "V",
            SensorDeviceClass.VOLTAGE,
            UnitOfElectricPotential.VOLT,
            id="voltage",
        ),
        pytest.param(
            SensorType.CURRENT,
            "A",
            SensorDeviceClass.CURRENT,
            UnitOfElectricCurrent.AMPERE,
            id="current",
        ),
        pytest.param(
            SensorType.POWER,
            "W",
            SensorDeviceClass.POWER,
            UnitOfPower.WATT,
            id="power",
        ),
        pytest.param(
            SensorType.CLOCK,
            "MHz",
            SensorDeviceClass.FREQUENCY,
            UnitOfFrequency.MEGAHERTZ,
            id="clock",
        ),
        pytest.param(
            SensorType.FREQUENCY,
            "Hz",
            SensorDeviceClass.FREQUENCY,
            UnitOfFrequency.HERTZ,
            id="frequency",
        ),
        pytest.param(
            SensorType.TEMPERATURE,
            "°C",
            SensorDeviceClass.TEMPERATURE,
            UnitOfTemperature.CELSIUS,
            id="temperature",
        ),
        pytest.param(
            SensorType.FLOW,
            "L/h",
            SensorDeviceClass.VOLUME_FLOW_RATE,
            UnitOfVolumeFlowRate.LITERS_PER_HOUR,
            id="flow",
        ),
        pytest.param(
            SensorType.DATA,
            "GB",
            SensorDeviceClass.DATA_SIZE,
            UnitOfInformation.GIGABYTES,
            id="data",
        ),
        pytest.param(
            SensorType.SMALL_DATA,
            "MB",
            SensorDeviceClass.DATA_SIZE,
            UnitOfInformation.MEGABYTES,
            id="small_data",
        ),
        pytest.param(
            SensorType.THROUGHPUT,
            "B/s",
            SensorDeviceClass.DATA_RATE,
            UnitOfDataRate.KIBIBYTES_PER_SECOND,
            id="throughput",
        ),
        pytest.param(
            SensorType.TIMESPAN,
            "s",
            SensorDeviceClass.DURATION,
            UnitOfTime.SECONDS,
            id="timespan",
        ),
        pytest.param(
            SensorType.ENERGY,
            "mWh",
            SensorDeviceClass.ENERGY_STORAGE,
            UnitOfEnergy.MILLIWATT_HOUR,
            id="energy",
        ),
        pytest.param(
            SensorType.NOISE,
            "dBA",
            SensorDeviceClass.SOUND_PRESSURE,
            UnitOfSoundPressure.WEIGHTED_DECIBEL_A,
            id="noise",
        ),
        pytest.param(
            SensorType.CONDUCTIVITY,
            # LHM uses the micro sign, HA normalizes it to the greek mu
            "\u00b5S/cm",
            SensorDeviceClass.CONDUCTIVITY,
            UnitOfConductivity.MICROSIEMENS_PER_CM,
            id="conductivity",
        ),
        pytest.param(
            SensorType.HUMIDITY,
            "%",
            SensorDeviceClass.HUMIDITY,
            PERCENTAGE,
            id="humidity",
        ),
        pytest.param(SensorType.FACTOR, None, None, None, id="factor_unmapped"),
        pytest.param(None, None, None, None, id="unknown_type"),
    ],
)
async def test_sensor_device_class_mapping(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_lhm_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    sensor_type: SensorType | None,
    lhm_unit: str | None,
    expected_device_class: SensorDeviceClass | None,
    expected_unit: str | None,
) -> None:
    """Test every LHM sensor type gets the expected device class and unit."""
    sensor_id = "gpu-nvidia-0-test-0"
    mock_lhm_client.get_data.return_value = replace(
        mock_lhm_client.get_data.return_value,
        sensor_data=MappingProxyType(
            {
                sensor_id: LibreHardwareMonitorSensorData(
                    name="Test",
                    value="42.0",
                    type=sensor_type,
                    min="40.0",
                    max="44.0",
                    unit=lhm_unit,
                    device_id="gpu-nvidia-0",
                    device_name="NVIDIA GeForce RTX 4080 SUPER",
                    device_type="NVIDIA",
                    sensor_id=sensor_id,
                )
            }
        ),
    )

    await init_integration(hass, mock_config_entry)

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{mock_config_entry.entry_id}_{sensor_id}"
    )
    assert entity_id

    state = hass.states.get(entity_id)

    assert state
    assert state.attributes.get(ATTR_DEVICE_CLASS) == expected_device_class
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == expected_unit


@pytest.mark.parametrize(
    "error", [LibreHardwareMonitorConnectionError, LibreHardwareMonitorNoDevicesError]
)
async def test_sensors_go_unavailable_on_error_and_recover(
    hass: HomeAssistant,
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


async def test_sensor_invalid_auth_after_update(
    hass: HomeAssistant,
    mock_lhm_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test invalid auth after sensor update."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_lhm_client.get_data.side_effect = LibreHardwareMonitorUnauthorizedError

    freezer.tick(timedelta(DEFAULT_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert "Authentication against LibreHardwareMonitor instance failed" in caplog.text

    unavailable_states = hass.states.async_all()
    assert all(state.state == STATE_UNAVAILABLE for state in unavailable_states)


async def test_sensor_invalid_auth_during_startup(
    hass: HomeAssistant,
    mock_lhm_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test invalid auth in initial sensor update during integration startup."""
    mock_lhm_client.get_data.side_effect = LibreHardwareMonitorUnauthorizedError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert "Authentication against LibreHardwareMonitor instance failed" in caplog.text
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.reason == "Authentication failed"

    unavailable_states = hass.states.async_all()
    assert all(state.state == STATE_UNAVAILABLE for state in unavailable_states)


@pytest.mark.parametrize(
    ("object_id", "sensor_id", "new_value", "state_value"),
    [
        (
            "gaming_pc_amd_ryzen_7_7800x3d_package_temperature",
            "amdcpu-0-temperature-3",
            "42.1",
            "42.1",
        ),
        (
            "gaming_pc_nvidia_geforce_rtx_4080_super_gpu_pcie_tx_throughput",
            "gpu-nvidia-0-throughput-1",
            "811161600.0",
            "792150.0",
        ),
    ],
)
async def test_sensors_are_updated(
    hass: HomeAssistant,
    mock_lhm_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    object_id: str,
    sensor_id: str,
    new_value: str,
    state_value: str,
) -> None:
    """Test sensors are updated with properly formatted values."""
    await init_integration(hass, mock_config_entry)

    updated_data = dict(mock_lhm_client.get_data.return_value.sensor_data)
    updated_data[sensor_id] = replace(updated_data[sensor_id], value=new_value)
    mock_lhm_client.get_data.return_value = replace(
        mock_lhm_client.get_data.return_value,
        sensor_data=MappingProxyType(updated_data),
    )

    freezer.tick(timedelta(DEFAULT_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.{object_id}")

    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == state_value


async def test_sensor_state_is_unknown_when_no_sensor_data_is_provided(
    hass: HomeAssistant,
    mock_lhm_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor state is unknown when sensor data is missing."""
    await init_integration(hass, mock_config_entry)

    entity_id = "sensor.gaming_pc_amd_ryzen_7_7800x3d_package_temperature"

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


async def test_orphaned_devices_are_removed_if_not_present_after_update(
    hass: HomeAssistant,
    mock_lhm_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test devices not found in LHM data after update are removed."""
    orphaned_device = await _mock_orphaned_device(
        device_registry, hass, mock_config_entry, mock_lhm_client
    )

    freezer.tick(timedelta(DEFAULT_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert device_registry.async_get(orphaned_device.id) is None


async def test_orphaned_devices_are_removed_if_not_present_during_startup(
    hass: HomeAssistant,
    mock_lhm_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test devices not found in LHM data during startup are removed."""
    orphaned_device = await _mock_orphaned_device(
        device_registry, hass, mock_config_entry, mock_lhm_client
    )

    hass.config_entries.async_schedule_reload(mock_config_entry.entry_id)

    assert device_registry.async_get(orphaned_device.id) is None


async def _mock_orphaned_device(
    device_registry: dr.DeviceRegistry,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lhm_client: AsyncMock,
) -> DeviceEntry:
    await init_integration(hass, mock_config_entry)

    removed_device = "gpu-nvidia-0"
    previous_data = mock_lhm_client.get_data.return_value
    assert removed_device in previous_data.main_device_ids_and_names

    mock_lhm_client.get_data.return_value = replace(
        mock_lhm_client.get_data.return_value,
        main_device_ids_and_names=MappingProxyType(
            {
                device_id: name
                for (device_id, name) in previous_data.main_device_ids_and_names.items()
                if device_id != removed_device
            }
        ),
        sensor_data=MappingProxyType(
            {
                sensor_id: data
                for (sensor_id, data) in previous_data.sensor_data.items()
                if not sensor_id.startswith(removed_device)
            }
        ),
    )

    return device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, f"{mock_config_entry.entry_id}_{removed_device}")},
    )


async def test_integration_dynamically_adds_new_devices(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_lhm_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that new devices are created when detected."""
    await init_integration(hass, mock_config_entry)

    device_entries: list[DeviceEntry] = dr.async_entries_for_config_entry(
        registry=device_registry, config_entry_id=mock_config_entry.entry_id
    )
    assert len(device_entries) == 3

    mock_lhm_client.get_data.return_value = replace(
        mock_lhm_client.get_data.return_value,
        main_device_ids_and_names=MappingProxyType(
            {
                **mock_lhm_client.get_data.return_value.main_device_ids_and_names,
                DeviceId("generic-memory"): DeviceName("Generic Memory"),
            }
        ),
        sensor_data=MappingProxyType(
            {
                **mock_lhm_client.get_data.return_value.sensor_data,
                "generic-memory-test-sensor": LibreHardwareMonitorSensorData(
                    name="Test sensor",
                    value="30",
                    type=SensorType.FACTOR,
                    min="12",
                    max="36",
                    unit=None,
                    device_id="generic-memory",
                    device_name="Generic Memory",
                    device_type="MEMORY",
                    sensor_id="generic-memory-test-sensor",
                ),
            }
        ),
    )

    freezer.tick(timedelta(DEFAULT_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    device_entries: list[DeviceEntry] = dr.async_entries_for_config_entry(
        registry=device_registry, config_entry_id=mock_config_entry.entry_id
    )
    assert len(device_entries) == 4
    expected_device = next(entry for entry in device_entries if "Generic" in entry.name)
    assert expected_device.name == "[GAMING-PC] Generic Memory"

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert "sensor.gaming_pc_generic_memory_test_sensor" in [
        entry.entity_id for entry in entity_entries
    ]
