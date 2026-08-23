"""Test the Sofar Inverter Modbus sensor platform."""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import ModbusTimeoutError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorStateClass
from homeassistant.components.sofar.const import DEFAULT_SCAN_INTERVAL
from homeassistant.components.sofar.sensor import (
    SofarCommunicationHealthLastErrorSensor,
    SofarCommunicationHealthLastErrorTimeSensor,
    SofarCommunicationHealthSensor,
    SofarCommunicationHealthSuccessRateSensor,
    SofarSensor,
    SofarSensorDescription,
    SofarTotalSensor,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MOCK_SERIAL

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test all entities match their snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


async def test_communication_health_sensor(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test communication_health tracks poll outcomes, incl. disabled entities."""
    health_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, "sofar", f"{MOCK_SERIAL}_communication_health"
    )
    success_rate_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN,
        "sofar",
        f"{MOCK_SERIAL}_communication_health_success_rate",
    )
    last_error_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, "sofar", f"{MOCK_SERIAL}_communication_health_last_error"
    )
    last_error_time_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN,
        "sofar",
        f"{MOCK_SERIAL}_communication_health_last_error_time",
    )
    assert health_id is not None
    assert success_rate_id is not None
    assert last_error_id is not None
    assert last_error_time_id is not None
    last_error_entry = entity_registry.async_get(last_error_id)
    last_error_time_entry = entity_registry.async_get(last_error_time_id)
    assert last_error_entry is not None
    assert last_error_entry.disabled_by is not None
    assert last_error_time_entry is not None
    assert last_error_time_entry.disabled_by is not None

    # Disabled by default: not in hass.states, so instantiate directly.
    readings = init_integration.runtime_data.readings
    last_error_sensor = SofarCommunicationHealthLastErrorSensor(readings)
    last_error_time_sensor = SofarCommunicationHealthLastErrorTimeSensor(readings)

    assert (state := hass.states.get(health_id)) is not None
    assert state.state == "good"
    assert (state := hass.states.get(success_rate_id)) is not None
    assert state.state == "100.0"
    assert last_error_sensor.native_value is None
    assert last_error_time_sensor.native_value is None

    unit = readings.connection.for_unit(1)
    unit.fail_read(0x0484, ModbusTimeoutError("stuck"))
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(health_id)) is not None
    assert state.state != "good"
    assert (state := hass.states.get(success_rate_id)) is not None
    assert float(state.state) == readings.success_rate
    assert readings.success_rate is not None
    assert readings.success_rate < 100.0
    assert last_error_sensor.native_value is not None
    assert "ModbusTimeoutError" in last_error_sensor.native_value
    assert last_error_time_sensor.native_value is not None


async def test_communication_health_sensor_degraded_bucket(
    init_integration: MockConfigEntry,
) -> None:
    """Test the health sensor reports "degraded" for a rate in [80, 100)."""
    readings = init_integration.runtime_data.readings
    readings._poll_outcomes.clear()
    readings._poll_outcomes.extend([True] * 9 + [False])

    health_sensor = SofarCommunicationHealthSensor(readings)
    assert readings.success_rate == 90.0
    assert health_sensor.native_value == "degraded"

    readings._poll_outcomes.clear()
    assert readings.success_rate is None
    assert health_sensor.native_value == "unknown"


async def test_communication_health_entities_stay_available_on_dead_link(
    init_integration: MockConfigEntry,
) -> None:
    """Test communication_health stays available when the link is down."""
    readings = init_integration.runtime_data.readings
    health_sensor = SofarCommunicationHealthSensor(readings)
    success_rate_sensor = SofarCommunicationHealthSuccessRateSensor(readings)
    last_error_sensor = SofarCommunicationHealthLastErrorSensor(readings)
    last_error_time_sensor = SofarCommunicationHealthLastErrorTimeSensor(readings)

    readings.last_update_success = False
    assert health_sensor.available
    assert success_rate_sensor.available
    assert last_error_sensor.available
    assert last_error_time_sensor.available


async def test_total_sensor_restore_data_parsing(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test SofarTotalSensor restore parsing: valid, invalid, and None."""
    runtime_data = init_integration.runtime_data
    device = runtime_data.readings.device
    description = SofarSensorDescription(
        key="load_consumption_total",
        component="energy",
        translation_key="load_consumption_total",
    )

    device.energy.load_consumption_total = None
    sensor = SofarTotalSensor(runtime_data, description)
    sensor.hass = hass
    sensor.async_get_last_sensor_data = AsyncMock(
        return_value=SimpleNamespace(native_value="555.5")
    )
    await sensor.async_added_to_hass()
    assert sensor.native_value == 555.5
    assert sensor._total_increasing_high_water == 555.5
    assert sensor._smoothed_total_increasing(555.4) == 555.5

    invalid_sensor = SofarTotalSensor(runtime_data, description)
    invalid_sensor.hass = hass
    invalid_sensor.async_get_last_sensor_data = AsyncMock(
        return_value=SimpleNamespace(native_value="not_a_number")
    )
    await invalid_sensor.async_added_to_hass()
    assert invalid_sensor._total_increasing_high_water is None

    device.energy.load_consumption_total = 120.0
    total_sensor = SofarTotalSensor(runtime_data, description)
    assert total_sensor.native_value == 120.0

    device.energy.load_consumption_total = None
    unset_sensor = SofarTotalSensor(runtime_data, description)
    assert unset_sensor.native_value is None


async def test_smoothed_total_increasing_dip_tolerance(
    init_integration: MockConfigEntry,
) -> None:
    """Test small total_increasing dips are ignored, large drops pass through."""
    runtime_data = init_integration.runtime_data
    description = SofarSensorDescription(
        key="load_consumption_total",
        component="energy",
        translation_key="load_consumption_total",
    )
    sensor = SofarTotalSensor(runtime_data, description)
    sensor._attr_native_value = 1000.0
    sensor._total_increasing_high_water = 1000.0

    assert sensor._smoothed_total_increasing(999.9) == 1000.0

    assert sensor._smoothed_total_increasing(1005.0) == 1005.0
    assert sensor._total_increasing_high_water == 1005.0

    assert sensor._smoothed_total_increasing(10.0) == 10.0
    assert sensor._total_increasing_high_water == 10.0


async def test_sensor_dead_link_unavailable(init_integration: MockConfigEntry) -> None:
    """Test SofarSensor.available is False when the last update failed."""
    runtime_data = init_integration.runtime_data
    description = SofarSensorDescription(
        key="grid_frequency",
        component="grid",
        translation_key="grid_frequency",
    )
    sensor = SofarSensor(runtime_data, description)
    assert sensor.native_value == 50.0
    runtime_data.readings.last_update_success = False
    assert not sensor.available


async def test_sensor_availability_on_component_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
) -> None:
    """Test SofarSensor.available reflects its own component, not the link."""
    runtime_data = init_integration.runtime_data
    description = SofarSensorDescription(
        key="grid_frequency",
        component="grid",
        translation_key="grid_frequency",
    )
    sensor = SofarSensor(runtime_data, description)
    assert sensor.available

    unit = runtime_data.readings.connection.for_unit(1)
    unit.fail_read(0x0484, ModbusTimeoutError("stuck"))
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert not sensor.available

    unit.fail_read(0x0484, None)
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert sensor.available


async def test_sofar_sensor_enum_native_value(
    init_integration: MockConfigEntry,
) -> None:
    """Test SofarSensor translates an IntEnum value to its label."""
    runtime_data = init_integration.runtime_data
    description = SofarSensorDescription(
        key="system_state",
        component="state",
        translation_key="system_state",
    )
    sensor = SofarSensor(runtime_data, description)
    assert sensor.native_value == "Grid Connected"


async def test_total_sensor_total_increasing_uses_smoothing(
    init_integration: MockConfigEntry,
) -> None:
    """Test a TOTAL_INCREASING description routes through the dip smoother."""
    runtime_data = init_integration.runtime_data
    description = SofarSensorDescription(
        key="load_consumption_total",
        component="energy",
        translation_key="load_consumption_total",
        state_class=SensorStateClass.TOTAL_INCREASING,
    )
    runtime_data.readings.device.energy.load_consumption_total = 42.0
    sensor = SofarTotalSensor(runtime_data, description)
    assert sensor.native_value == 42.0
    assert sensor._total_increasing_high_water == 42.0
    assert sensor.available
