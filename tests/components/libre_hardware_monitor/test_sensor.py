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
from homeassistant.components.libre_hardware_monitor.sensor import (
    MISSING_SENSOR_REMOVAL_UPDATES,
    STATE_MAX_VALUE,
    STATE_MIN_VALUE,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
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

TEMPERATURE_SENSOR_ID = "amdcpu-0-temperature-3"


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
            # LHM labels binary gigabytes as GB
            "GB",
            SensorDeviceClass.DATA_SIZE,
            UnitOfInformation.GIBIBYTES,
            id="data",
        ),
        pytest.param(
            SensorType.DATA,
            "B",
            SensorDeviceClass.DATA_SIZE,
            UnitOfInformation.GIBIBYTES,
            id="data_bytes",
        ),
        pytest.param(
            SensorType.SMALL_DATA,
            # LHM labels binary megabytes as MB
            "MB",
            SensorDeviceClass.DATA_SIZE,
            UnitOfInformation.GIBIBYTES,
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
            # LHM sends the micro sign (U+00B5), HA normalizes it to greek mu (U+03BC)
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


async def test_min_max_follow_selected_conductivity_unit(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_lhm_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test min and max are converted from the micro sign spelling LHM reports."""
    sensor_id = "gpu-nvidia-0-conductivity-0"
    mock_lhm_client.get_data.return_value = replace(
        mock_lhm_client.get_data.return_value,
        sensor_data=MappingProxyType(
            {
                sensor_id: LibreHardwareMonitorSensorData(
                    name="Coolant",
                    value="42.0",
                    type=SensorType.CONDUCTIVITY,
                    min="40.0",
                    max="44.0",
                    unit="\u00b5S/cm",
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

    entity_registry.async_update_entity_options(
        entity_id,
        "sensor",
        {"unit_of_measurement": UnitOfConductivity.MILLISIEMENS_PER_CM},
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == (
        UnitOfConductivity.MILLISIEMENS_PER_CM
    )
    assert float(state.state) == pytest.approx(0.042)
    assert state.attributes[STATE_MIN_VALUE] == pytest.approx(0.04)
    assert state.attributes[STATE_MAX_VALUE] == pytest.approx(0.044)


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
) -> None:
    """Test invalid auth after sensor update."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_lhm_client.get_data.side_effect = LibreHardwareMonitorUnauthorizedError

    freezer.tick(timedelta(DEFAULT_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH})

    unavailable_states = hass.states.async_all()
    assert all(state.state == STATE_UNAVAILABLE for state in unavailable_states)


async def test_sensor_invalid_auth_during_startup(
    hass: HomeAssistant,
    mock_lhm_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test invalid auth in initial sensor update during integration startup."""
    mock_lhm_client.get_data.side_effect = LibreHardwareMonitorUnauthorizedError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

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


async def test_missing_device_is_removed_after_grace_period(
    hass: HomeAssistant,
    mock_lhm_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a device missing from LHM is removed when its holds no more sensors."""
    orphaned_device = await _mock_orphaned_device(
        device_registry, hass, mock_config_entry, mock_lhm_client
    )

    await _async_poll(hass, freezer, MISSING_SENSOR_REMOVAL_UPDATES - 1)
    assert device_registry.async_get(orphaned_device.id)
    assert er.async_entries_for_device(entity_registry, orphaned_device.id)

    await _async_poll(hass, freezer)
    assert device_registry.async_get(orphaned_device.id) is None
    assert not er.async_entries_for_device(entity_registry, orphaned_device.id)


async def test_device_returning_within_grace_period_is_kept(
    hass: HomeAssistant,
    mock_lhm_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a device that is briefly missing keeps its registry entry."""
    initial_data = mock_lhm_client.get_data.return_value
    orphaned_device = await _mock_orphaned_device(
        device_registry, hass, mock_config_entry, mock_lhm_client
    )

    await _async_poll(hass, freezer, MISSING_SENSOR_REMOVAL_UPDATES - 1)
    mock_lhm_client.get_data.return_value = initial_data
    await _async_poll(hass, freezer, MISSING_SENSOR_REMOVAL_UPDATES)

    assert device_registry.async_get(orphaned_device.id)


async def test_stale_device_is_removed_after_grace_period(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_lhm_client: AsyncMock,
) -> None:
    """Test a device that vanished while HA was not running is cleaned up."""
    mock_config_entry.add_to_hass(hass)
    stale_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, f"{mock_config_entry.entry_id}_nvme-0")},
    )
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{mock_config_entry.entry_id}_nvme-0-temperature-0",
        config_entry=mock_config_entry,
        device_id=stale_device.id,
    )

    await init_integration(hass, mock_config_entry)

    # setting up counts as the first update without the device
    await _async_poll(hass, freezer, MISSING_SENSOR_REMOVAL_UPDATES - 2)
    assert device_registry.async_get(stale_device.id)

    await _async_poll(hass, freezer)
    assert device_registry.async_get(stale_device.id) is None


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


async def _async_poll(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, times: int = 1
) -> None:
    """Advance time by the given number of update intervals."""
    for _ in range(times):
        freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()


def _set_sensor_data(
    mock_lhm_client: AsyncMock, sensor_data: dict[str, LibreHardwareMonitorSensorData]
) -> None:
    """Make the next update report the given sensors."""
    mock_lhm_client.get_data.return_value = replace(
        mock_lhm_client.get_data.return_value,
        sensor_data=MappingProxyType(sensor_data),
    )


async def test_new_sensor_of_known_device_is_added(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_lhm_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a sensor that appears on an existing device is added without reload."""
    await init_integration(hass, mock_config_entry)

    # e.g. an LHM update renaming /gpu-nvidia/0/smalldata/1 to /gpu-nvidia/0/data/1
    new_sensor_id = "gpu-nvidia-0-data-1"
    initial_data = mock_lhm_client.get_data.return_value.sensor_data
    _set_sensor_data(
        mock_lhm_client,
        {
            **initial_data,
            new_sensor_id: LibreHardwareMonitorSensorData(
                name="GPU Memory Used",
                value="733.0",
                type=None,
                min="700.0",
                max="800.0",
                unit=None,
                device_id="gpu-nvidia-0",
                device_name="NVIDIA GeForce RTX 4080 SUPER",
                device_type="NVIDIA",
                sensor_id=new_sensor_id,
            ),
        },
    )
    await _async_poll(hass, freezer)

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{mock_config_entry.entry_id}_{new_sensor_id}"
    )
    assert entity_id
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "733.0"


async def test_missing_sensor_is_removed_after_grace_period(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_lhm_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a sensor missing from LHM is removed only after the grace period."""
    await init_integration(hass, mock_config_entry)

    unique_id = f"{mock_config_entry.entry_id}_{TEMPERATURE_SENSOR_ID}"
    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id

    initial_data = dict(mock_lhm_client.get_data.return_value.sensor_data)
    _set_sensor_data(
        mock_lhm_client,
        {
            sensor_id: data
            for sensor_id, data in initial_data.items()
            if sensor_id != TEMPERATURE_SENSOR_ID
        },
    )

    await _async_poll(hass, freezer, MISSING_SENSOR_REMOVAL_UPDATES - 1)
    assert entity_registry.async_get(entity_id)
    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    await _async_poll(hass, freezer)
    assert entity_registry.async_get(entity_id) is None
    assert hass.states.get(entity_id) is None

    # a sensor that comes back later is added as a new sensor
    _set_sensor_data(mock_lhm_client, initial_data)
    await _async_poll(hass, freezer)
    assert entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)


async def test_sensor_returning_within_grace_period_is_kept(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_lhm_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a sensor LHM briefly fails to read is not removed."""
    await init_integration(hass, mock_config_entry)

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{mock_config_entry.entry_id}_{TEMPERATURE_SENSOR_ID}"
    )
    assert entity_id

    initial_data = dict(mock_lhm_client.get_data.return_value.sensor_data)
    data_without_sensor = {
        sensor_id: data
        for sensor_id, data in initial_data.items()
        if sensor_id != TEMPERATURE_SENSOR_ID
    }

    # the missing count starts over once the sensor is reported again
    for sensor_data in (data_without_sensor, initial_data, data_without_sensor):
        _set_sensor_data(mock_lhm_client, sensor_data)
        await _async_poll(hass, freezer, MISSING_SENSOR_REMOVAL_UPDATES - 1)

    assert entity_registry.async_get(entity_id)


async def test_failed_updates_do_not_count_towards_removal(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_lhm_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the grace period only counts updates that reached LHM."""
    await init_integration(hass, mock_config_entry)

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{mock_config_entry.entry_id}_{TEMPERATURE_SENSOR_ID}"
    )
    assert entity_id

    _set_sensor_data(
        mock_lhm_client,
        {
            sensor_id: data
            for sensor_id, data in mock_lhm_client.get_data.return_value.sensor_data.items()
            if sensor_id != TEMPERATURE_SENSOR_ID
        },
    )
    await _async_poll(hass, freezer, MISSING_SENSOR_REMOVAL_UPDATES - 1)

    # the computer going offline must not remove its sensors
    mock_lhm_client.get_data.side_effect = LibreHardwareMonitorConnectionError
    await _async_poll(hass, freezer, MISSING_SENSOR_REMOVAL_UPDATES)
    assert entity_registry.async_get(entity_id)

    mock_lhm_client.get_data.side_effect = None
    await _async_poll(hass, freezer)
    assert entity_registry.async_get(entity_id) is None


async def test_stale_registry_entry_is_removed_after_grace_period(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_lhm_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a sensor that vanished while HA was not running is cleaned up."""
    mock_config_entry.add_to_hass(hass)
    # e.g. an NVMe health sensor that LHM moved from index 100 to 25
    stale_entry = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{mock_config_entry.entry_id}_nvme-0-level-100",
        config_entry=mock_config_entry,
    )

    await init_integration(hass, mock_config_entry)

    # setting up counts as the first update without the sensor
    await _async_poll(hass, freezer, MISSING_SENSOR_REMOVAL_UPDATES - 2)
    assert entity_registry.async_get(stale_entry.entity_id)

    await _async_poll(hass, freezer)
    assert entity_registry.async_get(stale_entry.entity_id) is None


async def test_sensors_are_added_again_when_removed_device_returns(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_lhm_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the sensors of a device that disappeared and came back are restored."""
    initial_data = mock_lhm_client.get_data.return_value
    orphaned_device = await _mock_orphaned_device(
        device_registry, hass, mock_config_entry, mock_lhm_client
    )
    await _async_poll(hass, freezer, MISSING_SENSOR_REMOVAL_UPDATES)
    assert device_registry.async_get(orphaned_device.id) is None

    mock_lhm_client.get_data.return_value = initial_data
    await _async_poll(hass, freezer)

    assert entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{mock_config_entry.entry_id}_gpu-nvidia-0-temperature-0"
    )


def _sensor(
    sensor_id: str, name: str, device_id: str, device_name: str
) -> LibreHardwareMonitorSensorData:
    """Return data for a sensor without a type."""
    return LibreHardwareMonitorSensorData(
        name=name,
        value="42.0",
        type=None,
        min="40.0",
        max="44.0",
        unit=None,
        device_id=device_id,
        device_name=device_name,
        device_type="NVIDIA",
        sensor_id=sensor_id,
    )


GPU_DEVICE = ("gpu-nvidia-0", "NVIDIA GeForce RTX 4080 SUPER")


async def test_renamed_sensor_takes_over_entity_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_lhm_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a sensor whose id changes in an LHM update keeps its entity id."""
    initial_data = mock_lhm_client.get_data.return_value.sensor_data
    old_sensor = _sensor(
        "gpu-nvidia-0-smalldata-1", "GPU Memory Used Data", *GPU_DEVICE
    )
    other_sensor = _sensor(
        "gpu-nvidia-0-smalldata-2", "GPU Memory Free Data", *GPU_DEVICE
    )
    _set_sensor_data(
        mock_lhm_client,
        {
            **initial_data,
            old_sensor.sensor_id: old_sensor,
            other_sensor.sensor_id: other_sensor,
        },
    )
    await init_integration(hass, mock_config_entry)

    old_unique_id = f"{mock_config_entry.entry_id}_{old_sensor.sensor_id}"
    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, old_unique_id)
    assert entity_id

    new_sensor = _sensor("gpu-nvidia-0-data-1", "GPU Memory Used Data", *GPU_DEVICE)
    _set_sensor_data(
        mock_lhm_client, {**initial_data, new_sensor.sensor_id: new_sensor}
    )
    await _async_poll(hass, freezer)

    # the replaced sensor is removed right away instead of after the grace period
    assert entity_registry.async_get_entity_id("sensor", DOMAIN, old_unique_id) is None
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{mock_config_entry.entry_id}_{new_sensor.sensor_id}"
        )
        == entity_id
    )
    assert hass.states.get(entity_id).state == "42.0"
    # a sensor with another name going missing at the same time is not replaced
    assert entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{mock_config_entry.entry_id}_{other_sensor.sensor_id}"
    )


async def test_sensor_renamed_while_ha_was_stopped_takes_over_entity_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_lhm_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a sensor whose id changed while HA was not running keeps its entity id."""
    nvme_device = ("nvme-0", "Samsung SSD 990 PRO 2TB")
    initial_data = mock_lhm_client.get_data.return_value.sensor_data
    old_sensor = _sensor("nvme-0-level-100", "Available Spare Level", *nvme_device)
    _set_sensor_data(
        mock_lhm_client, {**initial_data, old_sensor.sensor_id: old_sensor}
    )
    mock_lhm_client.get_data.return_value = replace(
        mock_lhm_client.get_data.return_value,
        main_device_ids_and_names=MappingProxyType(
            {
                **mock_lhm_client.get_data.return_value.main_device_ids_and_names,
                DeviceId(nvme_device[0]): DeviceName(nvme_device[1]),
            }
        ),
    )
    await init_integration(hass, mock_config_entry)

    old_unique_id = f"{mock_config_entry.entry_id}_{old_sensor.sensor_id}"
    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, old_unique_id)
    assert entity_id
    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    new_sensor = _sensor("nvme-0-level-25", "Available Spare Level", *nvme_device)
    _set_sensor_data(
        mock_lhm_client, {**initial_data, new_sensor.sensor_id: new_sensor}
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get_entity_id("sensor", DOMAIN, old_unique_id) is None
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{mock_config_entry.entry_id}_{new_sensor.sensor_id}"
        )
        == entity_id
    )
