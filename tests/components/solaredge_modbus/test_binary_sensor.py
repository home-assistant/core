"""Tests for the SolarEdge Modbus binary sensor entities."""

from unittest.mock import patch

from modbus_connection import IllegalDataAddressError
from modbus_connection.encode import encode_int
from modbus_connection.mock import MockModbusUnit
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

CHARGING_ENTITY = "binary_sensor.battery_1_charging"
PROBLEM_ENTITY = "binary_sensor.solaredge_se10000h_problem"
ON_GRID_ENTITY = "binary_sensor.solaredge_se10000h_on_grid"
BATTERY_STATUS_REGISTER = 57734


async def _setup_binary_sensor_platform(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    with patch(
        "homeassistant.components.solaredge_modbus.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def test_binary_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """All binary sensor entities and their states match the snapshot."""
    await _setup_binary_sensor_platform(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_no_on_grid_sensor_without_grid_status_extension(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Firmware without the grid status extension gets no on-grid sensor."""
    # A real device answers reads of the absent extension with a Modbus
    # exception (illegal data address).
    mock_modbus_unit.fail_read(40113, IllegalDataAddressError())

    await _setup_binary_sensor_platform(hass, mock_config_entry)

    assert hass.states.get(ON_GRID_ENTITY) is None


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        pytest.param(3, STATE_ON, id="charging"),
        pytest.param(4, STATE_OFF, id="discharging"),
        pytest.param(6, STATE_OFF, id="preserving charge"),
        pytest.param(0xFFFFFFFF, STATE_UNKNOWN, id="not implemented"),
    ],
)
async def test_battery_charging(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
    status: int,
    expected: str,
) -> None:
    """The charging sensor follows the battery status, and admits ignorance.

    Home Assistant's battery-charging triggers and conditions key on this
    device class, so the status enum alone would leave them out of reach.
    """
    # The battery block is word-swapped, which the encoder can do itself.
    words = encode_int(status, count=2, word_order="little")
    for offset, word in enumerate(words):
        mock_modbus_unit.holding[BATTERY_STATUS_REGISTER + offset] = word

    await _setup_binary_sensor_platform(hass, mock_config_entry)

    state = hass.states.get(CHARGING_ENTITY)
    assert state is not None
    assert state.state == expected


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        pytest.param(7, STATE_ON, id="fault"),
        pytest.param(4, STATE_OFF, id="producing"),
        pytest.param(2, STATE_OFF, id="sleeping"),
        pytest.param(99, STATE_UNKNOWN, id="not a known status"),
    ],
)
async def test_inverter_problem(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
    status: int,
    expected: str,
) -> None:
    """A faulted inverter is a problem, and an unreadable status is unknown."""
    mock_modbus_unit.holding[40107] = status

    await _setup_binary_sensor_platform(hass, mock_config_entry)

    state = hass.states.get(PROBLEM_ENTITY)
    assert state is not None
    assert state.state == expected
