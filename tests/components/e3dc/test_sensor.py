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
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import MOCK_SERIAL, int32_words, seed

PV_POWER = "sensor.e3_dc_s10_x_pv_power"
GRID_POWER_L1 = "sensor.e3_dc_s10_x_grid_power_l1"
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
            {40206: int32_words(4200)},  # Battery remaining energy, in Wh
            "sensor.e3_dc_s10_x_stored_energy",
            "4.2",
            id="battery_limits",
        ),
        pytest.param(
            {40137: 2},  # SG Ready status
            "sensor.e3_dc_s10_x_sg_ready_status",
            "normal",
            id="wide_power_meters",
        ),
        pytest.param(
            {40137: 0},  # SG Ready status
            "sensor.e3_dc_s10_x_sg_ready_status",
            "unknown",
            id="sg_ready_unknown_value",
        ),
        pytest.param(
            {40194: 60},  # Active power failsafe timeout, in s
            "sensor.e3_dc_s10_x_active_power_failsafe_timeout",
            "60",
            id="grid_control",
        ),
        pytest.param(
            {40201: 10},  # Inverter mode
            "sensor.e3_dc_s10_x_inverter_mode",
            "idle_off_grid_power_save",
            id="inverter_mode_control",
        ),
        pytest.param(
            {40138: int32_words(-500)},  # Power meter slot 0 power L1, 32 bit
            "sensor.e3_dc_s10_x_grid_power_l1",
            "-500",
            id="grid_meter",
        ),
        pytest.param(
            {40144: int32_words(200)},  # Power meter slot 1 power L1, 32 bit
            "sensor.power_meter_2_power",
            "400",
            id="power_meters",
        ),
        pytest.param(
            {41006: int32_words(2000)},  # Inverter slot 0 active power L1, in W
            "sensor.e3_dc_s10_x_inverter_1_active_power_l1",
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
            {40088: 0},  # No wallbox available
            [
                "sensor.e3_dc_s10_x_wallbox_power",
                "sensor.e3_dc_s10_x_wallbox_solar_power",
            ],
            id="no_wallbox",
        ),
        pytest.param(
            {40109: 0},  # Power meter slot 1 not installed
            ["sensor.e3_dc_s10_x_additional_feeder_power"],
            id="no_additional_feeder",
        ),
        pytest.param(
            {40105: 0},  # Power meter slot 0 not installed
            [
                "sensor.e3_dc_s10_x_grid_power_l1",
                "sensor.e3_dc_s10_x_grid_power_l2",
                "sensor.e3_dc_s10_x_grid_power_l3",
            ],
            id="no_grid_meter",
        ),
        pytest.param(
            {40084: 0},  # Emergency power not supported
            ["sensor.e3_dc_s10_x_emergency_power"],
            id="no_emergency_power",
        ),
        pytest.param(
            {40208: int32_words(0)},  # Battery full charge energy, in Wh
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
            40137,  # Start of the SG Ready status and 32-bit power meter block
            ["sensor.e3_dc_s10_x_sg_ready_status"],
            id="no_wide_power_meters",
        ),
        pytest.param(
            40186,  # Start of the grid control block
            [
                "sensor.e3_dc_s10_x_active_power_failsafe_timeout",
                "sensor.e3_dc_s10_x_reactive_power_failsafe_timeout",
            ],
            id="no_grid_control",
        ),
        pytest.param(
            40200,  # Start of the inverter mode block
            ["sensor.e3_dc_s10_x_inverter_mode"],
            id="no_inverter_mode_control",
        ),
        pytest.param(
            40202,  # Start of the battery limits block
            BATTERY_LIMIT_SENSORS,
            id="no_battery_limits",
        ),
        pytest.param(
            41000,  # Start of the inverter slot 0 block
            [
                "sensor.e3_dc_s10_x_inverter_1_active_power_l1",
                "sensor.e3_dc_s10_x_inverter_1_dc_power_1",
            ],
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


def _part_devices(
    device_registry: dr.DeviceRegistry, entry: MockConfigEntry
) -> dict[str, tuple[str | None, str]]:
    """The part devices' names and how they link to the power station.

    The devices are keyed by their identifier without the serial number.
    """
    station = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL), entry.entry_id
    )
    connected = [
        device
        for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id)
        if device.via_device_id == station.id
    ]
    children = dr.async_entries_for_parent_device(device_registry, station.id)
    return {
        identifier.removeprefix(f"{MOCK_SERIAL}_"): (device.name, relation)
        for relation, devices in (("via", connected), ("child", children))
        for device in devices
        for _, identifier in device.identifiers
    }


@pytest.mark.parametrize(
    ("holding", "devices"),
    [
        pytest.param(
            {},
            {
                "power_meter_2": ("Power meter 2", "via"),
                "inverter_1": ("Inverter 1", "child"),
            },
            id="one_of_each",
        ),
        pytest.param(
            {
                40113: 4,  # Power meter slot 2 measures external consumption
                41052: 2302,  # Inverter slot 1 voltage L1, in 0.1 V
            },
            {
                "power_meter_2": ("Power meter 2", "via"),
                "power_meter_3": ("Power meter 3", "via"),
                "inverter_1": ("Inverter 1", "child"),
                "inverter_2": ("Inverter 2", "via"),
            },
            id="several",
        ),
    ],
)
@pytest.mark.usefixtures("mock_get_unit")
async def test_part_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_unit: MockModbusUnit,
    mock_config_entry: MockConfigEntry,
    holding: dict[int, int | list[int]],
    devices: dict[str, tuple[str, str]],
) -> None:
    """Test the power meters and inverters get a device named after their slot."""
    seed(mock_unit, holding)
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # The power station's own inverter is a child device, the other parts are
    # connected through it. The meter at the grid connection point has no device.
    assert _part_devices(device_registry, mock_config_entry) == devices


@pytest.mark.parametrize(
    ("setup_holding", "holding", "entity_id"),
    [
        pytest.param(
            {},
            {
                40113: 2,  # Power meter slot 2 measures external production
                40150: int32_words(300),  # Power meter slot 2 power L1, 32 bit
            },
            "sensor.power_meter_3_power",
            id="power_meter",
        ),
        pytest.param(
            {},
            {
                41052: 2302,  # Inverter slot 1 voltage L1, in 0.1 V
                41040: int32_words(1200),  # Inverter slot 1 active power L1, in W
            },
            "sensor.inverter_2_active_power_l1",
            id="inverter",
        ),
        pytest.param(
            {40105: 0},  # Power meter slot 0 not installed
            {40105: 1},  # Power meter slot 0 at the grid connection point
            GRID_POWER_L1,
            id="grid_meter",
        ),
    ],
)
@pytest.mark.usefixtures("mock_get_unit")
async def test_added_when_reported(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    mock_unit: MockModbusUnit,
    mock_config_entry: MockConfigEntry,
    setup_holding: dict[int, int | list[int]],
    holding: dict[int, int | list[int]],
    entity_id: str,
) -> None:
    """Test hardware the power station reports after setup gets its sensors."""
    seed(mock_unit, setup_holding)
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert entity_registry.async_get(entity_id) is None

    seed(mock_unit, holding)
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert entity_registry.async_get(entity_id) is not None


@pytest.mark.parametrize(
    ("setup_holding", "holding", "entity_id"),
    [
        pytest.param(
            {},
            {40109: 0},  # Power meter slot 1 not installed
            "sensor.power_meter_2_power",
            id="power_meter",
        ),
        pytest.param(
            {41052: 2302},  # Inverter slot 1 voltage L1, connected
            {41052: 0},  # Inverter slot 1 voltage L1, disconnected
            "sensor.inverter_2_active_power_l1",
            id="inverter",
        ),
    ],
)
@pytest.mark.usefixtures("mock_get_unit")
async def test_part_unavailable_when_gone(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_unit: MockModbusUnit,
    mock_config_entry: MockConfigEntry,
    setup_holding: dict[int, int | list[int]],
    holding: dict[int, int | list[int]],
    entity_id: str,
) -> None:
    """Test a part's sensors become unavailable once the part is gone."""
    seed(mock_unit, setup_holding)
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE

    seed(mock_unit, holding)
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
