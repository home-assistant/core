"""Test the Sofar Inverter Modbus sensor platform."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection
import pytest
from sofar_modbus.modern.device import SofarInverter
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorStateClass
from homeassistant.components.sofar.coordinator import SCAN_INTERVAL
from homeassistant.components.sofar.sensor import (
    SENSOR_DESCRIPTIONS,
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


def test_sensor_description_components_are_real() -> None:
    """Guards SENSOR_DESCRIPTIONS against a component/key transcription slip."""
    inverter = SofarInverter(MockModbusConnection().for_unit(1))
    for description in SENSOR_DESCRIPTIONS:
        component = getattr(inverter, description.component, None)
        assert component is not None, f"unknown component {description.component!r}"
        assert hasattr(component, description.key), (
            f"{description.component}.{description.key} does not exist"
        )


async def test_sensor_entities_created_and_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the four shipped sensors are created with the right values."""
    pv_power_1_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, "sofar", f"{MOCK_SERIAL}_pv_power_1"
    )
    pv_power_2_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, "sofar", f"{MOCK_SERIAL}_pv_power_2"
    )
    pv_power_total_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, "sofar", f"{MOCK_SERIAL}_pv_power_total"
    )
    solar_generation_total_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, "sofar", f"{MOCK_SERIAL}_solar_generation_total"
    )
    assert pv_power_1_id is not None
    assert pv_power_2_id is not None
    assert pv_power_total_id is not None
    assert solar_generation_total_id is not None

    assert (state := hass.states.get(pv_power_1_id)) is not None
    assert float(state.state) == 2.5
    assert (state := hass.states.get(pv_power_2_id)) is not None
    assert float(state.state) == 1.8
    assert (state := hass.states.get(pv_power_total_id)) is not None
    assert float(state.state) == 4.3
    assert (state := hass.states.get(solar_generation_total_id)) is not None
    assert float(state.state) == 15.0


async def test_total_sensor_restore_data_parsing(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test SofarTotalSensor restore parsing: valid, invalid, and None."""
    coordinator = init_integration.runtime_data
    device = coordinator.device
    description = SofarSensorDescription(
        key="load_consumption_total",
        component="energy",
        translation_key="load_consumption_total",
    )

    device.energy.load_consumption_total = None
    sensor = SofarTotalSensor(coordinator, description)
    sensor.hass = hass
    sensor.async_get_last_sensor_data = AsyncMock(
        return_value=SimpleNamespace(native_value="555.5")
    )
    await sensor.async_added_to_hass()
    assert sensor.native_value == 555.5

    invalid_sensor = SofarTotalSensor(coordinator, description)
    invalid_sensor.hass = hass
    invalid_sensor.async_get_last_sensor_data = AsyncMock(
        return_value=SimpleNamespace(native_value="not_a_number")
    )
    await invalid_sensor.async_added_to_hass()
    assert invalid_sensor.native_value is None

    blank_sensor = SofarTotalSensor(coordinator, description)
    blank_sensor.hass = hass
    blank_sensor.async_get_last_sensor_data = AsyncMock(
        return_value=SimpleNamespace(native_value=None)
    )
    await blank_sensor.async_added_to_hass()
    assert blank_sensor.native_value is None

    device.energy.load_consumption_total = 120.0
    total_sensor = SofarTotalSensor(coordinator, description)
    assert total_sensor.native_value == 120.0

    device.energy.load_consumption_total = None
    unset_sensor = SofarTotalSensor(coordinator, description)
    assert unset_sensor.native_value is None


async def test_total_sensor_seeds_high_water_from_restored_value(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test a restored value seeds the library's high-water mark."""
    coordinator = init_integration.runtime_data
    device = coordinator.device
    description = SofarSensorDescription(
        key="load_consumption_total",
        component="energy",
        translation_key="load_consumption_total",
        state_class=SensorStateClass.TOTAL_INCREASING,
    )
    sensor = SofarTotalSensor(coordinator, description)
    sensor.hass = hass
    sensor.async_get_last_sensor_data = AsyncMock(
        return_value=SimpleNamespace(native_value="555.5")
    )
    with patch.object(device.energy, "seed_high_water") as mock_seed:
        await sensor.async_added_to_hass()
    mock_seed.assert_called_once_with("load_consumption_total", 555.5)


async def test_sensor_dead_link_unavailable(init_integration: MockConfigEntry) -> None:
    """Test SofarSensor.available is False when the last update failed."""
    coordinator = init_integration.runtime_data
    description = SofarSensorDescription(
        key="grid_frequency",
        component="grid",
        translation_key="grid_frequency",
    )
    sensor = SofarSensor(coordinator, description)
    assert sensor.native_value == 50.0
    coordinator.last_update_success = False
    assert not sensor.available


async def test_sensor_availability_on_component_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test SofarSensor.available reflects its own component, not the link."""
    coordinator = init_integration.runtime_data
    description = SofarSensorDescription(
        key="grid_frequency",
        component="grid",
        translation_key="grid_frequency",
    )
    sensor = SofarSensor(coordinator, description)
    assert sensor.available

    unit = mock_connection.for_unit(1)
    unit.fail_read(0x0484, ModbusTimeoutError("stuck"))
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert not sensor.available

    unit.fail_read(0x0484, None)
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert sensor.available


async def test_total_sensor_total_increasing_uses_corrected_value(
    init_integration: MockConfigEntry,
) -> None:
    """Test a TOTAL_INCREASING description reads corrected() from the library."""
    coordinator = init_integration.runtime_data
    description = SofarSensorDescription(
        key="load_consumption_total",
        component="energy",
        translation_key="load_consumption_total",
        state_class=SensorStateClass.TOTAL_INCREASING,
    )
    device = coordinator.device
    sensor = SofarTotalSensor(coordinator, description)
    with patch.object(device.energy, "corrected", return_value=42.0) as mock_corrected:
        assert sensor.native_value == 42.0
    mock_corrected.assert_called_once_with("load_consumption_total")
    assert sensor.available
