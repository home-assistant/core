"""Tests for the BLUETTI Modbus sensor entities."""

from bluetti_modbus_lib import PvType, get_device
from freezegun.api import FrozenDateTimeFactory
from modbus_connection.mock import MockModbusUnit
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bluetti_modbus.const import SCAN_INTERVAL
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

INVERTER_POWER_ENTITY = "sensor.balco_260_total_inverter_power"
PV_AC_ENERGY_ENTITY = "sensor.balco_260_pv_ac_energy"
PV_1_TYPE_ENTITY = "sensor.balco_260_pv_1_input_type"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """All sensor entities and their states match the snapshot."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_inverter_power_is_signed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Power flowing into the battery reads as a negative inverter power."""
    field = get_device("balco260").get_field("d_inverter_total")
    assert field is not None
    low, high = field.encode(-1200)
    mock_modbus_unit.holding[field.address] = low
    mock_modbus_unit.holding[field.address + 1] = high

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(INVERTER_POWER_ENTITY)
    assert state is not None
    assert state.state == "-1200"


async def test_pv_ac_energy_zero_is_unknown(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A PV AC energy read as 0 is unknown, not a meter reset."""
    field = get_device("balco260").get_field("pv_ac_e")
    assert field is not None
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(PV_AC_ENERGY_ENTITY)
    assert state is not None
    assert state.state == "95.6"

    mock_modbus_unit.holding[field.address] = 0
    mock_modbus_unit.holding[field.address + 1] = 0
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(PV_AC_ENERGY_ENTITY)
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param(0, "reserve", id="reserve"),
        pytest.param(1, "car", id="car"),
        pytest.param(2, "adapter", id="adapter"),
        pytest.param(3, "other", id="other"),
        pytest.param(100, "dc_pv", id="dc_pv"),
        pytest.param(101, "ac_pv", id="ac_pv"),
        pytest.param(7, STATE_UNKNOWN, id="undecoded"),
    ],
)
async def test_pv_input_type_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
    raw: int,
    expected: str,
) -> None:
    """Every PV input type the device reports maps to a declared state."""
    field = get_device("balco260").get_field("pv_1_i_type")
    assert field is not None
    mock_modbus_unit.holding[field.address] = raw

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(PV_1_TYPE_ENTITY)
    assert state is not None
    assert state.state == expected


def test_pv_input_type_states_cover_the_library_enum() -> None:
    """A PV input type added to the library needs a state here first."""
    assert sorted(member.value for member in PvType) == [0, 1, 2, 3, 100, 101]
