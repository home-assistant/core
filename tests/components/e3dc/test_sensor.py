"""Tests for the E3/DC sensor platform."""

from datetime import timedelta

from e3dc_ess_modbus.model import register
from freezegun.api import FrozenDateTimeFactory
from modbus_connection import IllegalDataAddressError
from modbus_connection.mock import MockModbusUnit
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.e3dc.const import DOMAIN, SCAN_INTERVAL
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import MOCK_SERIAL, int32_words, seed

PV_POWER = "sensor.e3_dc_s10_x_pv_power"
BATTERY_LIMIT_SENSORS = [
    "sensor.e3_dc_s10_x_maximum_charge_power",
    "sensor.e3_dc_s10_x_maximum_discharge_power",
    "sensor.e3_dc_s10_x_stored_energy",
    "sensor.e3_dc_s10_x_battery_capacity",
]


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SENSOR]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test all entities match their snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


@pytest.mark.parametrize(
    ("holding", "entity_id", "state"),
    [
        pytest.param(
            {40206: int32_words(4200)},
            "sensor.e3_dc_s10_x_stored_energy",
            "4.2",
            id="battery_limits",
        ),
        pytest.param(
            {40137: 2},
            "sensor.e3_dc_s10_x_sg_ready_status",
            "normal",
            id="wide_power_meters",
        ),
        pytest.param(
            {40137: 0},
            "sensor.e3_dc_s10_x_sg_ready_status",
            "unknown",
            id="sg_ready_unknown_value",
        ),
        pytest.param(
            {40194: 60},
            "sensor.e3_dc_s10_x_active_power_failsafe_timeout",
            "60",
            id="grid_control",
        ),
        pytest.param(
            {40201: 10},
            "sensor.e3_dc_s10_x_inverter_mode",
            "idle_off_grid_power_save",
            id="inverter_mode_control",
        ),
        pytest.param(
            {40138: int32_words(-500)},
            "sensor.power_meter_0_power",
            "-800",
            id="power_meters",
        ),
        pytest.param(
            {41006: int32_words(2000)},
            "sensor.inverter_0_active_power_l1",
            "2000",
            id="inverters",
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_sensor_follows_poll(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_unit: MockModbusUnit,
    holding: dict[int, int | list[int]],
    entity_id: str,
    state: str,
) -> None:
    """Test a sensor takes the value its register holds at the next poll."""
    seed(mock_unit, holding)
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == state


@pytest.mark.parametrize(
    ("holding", "entity_ids"),
    [
        pytest.param(
            {40088: 0},
            [
                "sensor.e3_dc_s10_x_wallbox_power",
                "sensor.e3_dc_s10_x_wallbox_solar_power",
            ],
            id="no_wallbox",
        ),
        pytest.param(
            {40109: 0},
            ["sensor.e3_dc_s10_x_additional_feeder_power"],
            id="no_additional_feeder",
        ),
        pytest.param(
            {40084: 0},
            ["sensor.e3_dc_s10_x_emergency_power"],
            id="no_emergency_power",
        ),
        pytest.param(
            {40208: int32_words(0)},
            BATTERY_LIMIT_SENSORS,
            id="no_battery_capacity",
        ),
    ],
)
@pytest.mark.usefixtures("mock_get_unit")
async def test_optional_hardware_missing(
    hass: HomeAssistant,
    mock_unit: MockModbusUnit,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    holding: dict[int, int | list[int]],
    entity_ids: list[str],
) -> None:
    """Test sensors for hardware the power station lacks are not created."""
    seed(mock_unit, holding)
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(PV_POWER) is not None
    for entity_id in entity_ids:
        assert entity_registry.async_get(entity_id) is None


@pytest.mark.parametrize(
    ("refused_register", "entity_ids"),
    [
        pytest.param(
            40137,
            ["sensor.e3_dc_s10_x_sg_ready_status"],
            id="no_wide_power_meters",
        ),
        pytest.param(
            40186,
            [
                "sensor.e3_dc_s10_x_active_power_failsafe_timeout",
                "sensor.e3_dc_s10_x_reactive_power_failsafe_timeout",
            ],
            id="no_grid_control",
        ),
        pytest.param(
            40200,
            ["sensor.e3_dc_s10_x_inverter_mode"],
            id="no_inverter_mode_control",
        ),
        pytest.param(40202, BATTERY_LIMIT_SENSORS, id="no_battery_limits"),
        pytest.param(
            41000,
            ["sensor.inverter_0_active_power_l1", "sensor.inverter_0_dc_power_1"],
            id="no_inverters",
        ),
    ],
)
@pytest.mark.usefixtures("mock_get_unit")
async def test_block_missing_from_firmware(
    hass: HomeAssistant,
    mock_unit: MockModbusUnit,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    refused_register: int,
    entity_ids: list[str],
) -> None:
    """Test sensors for a register block that older firmware refuses are not created."""
    mock_unit.fail_read(register(refused_register), IllegalDataAddressError())
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(PV_POWER) is not None
    for entity_id in entity_ids:
        assert entity_registry.async_get(entity_id) is None


async def test_part_devices(
    device_registry: dr.DeviceRegistry, init_integration: MockConfigEntry
) -> None:
    """Test each power meter and inverter gets a device under the power station."""
    station = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL), init_integration.entry_id
    )
    parts = {
        device.name: device.identifiers
        for device in dr.async_entries_for_config_entry(
            device_registry, init_integration.entry_id
        )
        if device.via_device_id == station.id
    }

    assert parts == {
        "Power meter 0": {(DOMAIN, f"{MOCK_SERIAL}_power_meter_0")},
        "Power meter 1": {(DOMAIN, f"{MOCK_SERIAL}_power_meter_1")},
        "Inverter 0": {(DOMAIN, f"{MOCK_SERIAL}_inverter_0")},
    }


@pytest.mark.parametrize(
    ("holding", "entity_id"),
    [
        pytest.param(
            {40113: 2, 40150: int32_words(300)},
            "sensor.power_meter_2_power",
            id="power_meter",
        ),
        pytest.param(
            {41034 + 18: 2302, 41034 + 6: int32_words(1200)},
            "sensor.inverter_1_active_power_l1",
            id="inverter",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_part_added_when_reported(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_unit: MockModbusUnit,
    holding: dict[int, int | list[int]],
    entity_id: str,
) -> None:
    """Test a meter configured or an inverter connected after setup gets its sensors."""
    assert hass.states.get(entity_id) is None

    seed(mock_unit, holding)
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id) is not None
