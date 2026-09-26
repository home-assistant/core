"""Tests for the IONT integration.

The helpers here seed a ``MockModbusUnit`` the way a charger serves its
registers, so the tests drive the real ``pyiont`` library against a faithful
register image and only the Home Assistant wiring is under test.
"""

from modbus_connection.encode import encode_float32, encode_int
from modbus_connection.mock import MockModbusUnit
from pyiont import (
    AuthorizedBy,
    ChargingState,
    ChargingStrategy,
    ConnectionState,
    CurrentFlow,
    DeviceStatus,
    VehicleState,
)
from pyiont.const import (
    COMMAND_RESULT_ADDRESS,
    COMMAND_RESULT_OK,
    CONNECTOR_AUTHORIZE_OFFSET,
    CONNECTOR_BASE,
    CONNECTOR_DEAUTHORIZE_OFFSET,
    CONNECTOR_STRIDE,
    DEVICE_BASE,
    EXTERNAL_POWER_LIMIT_ADDRESS,
)

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_HOST = "192.168.1.60"
MOCK_PORT = 502
MOCK_USER_INPUT = {CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT}
MOCK_TITLE = "IONT charger"

# Registers the tests poke at, by what they hold.
STATUS_REGISTER = DEVICE_BASE + 0x007
CONNECTOR_COUNT_REGISTER = DEVICE_BASE + 0x00A
POWER_LIMIT_REGISTER = EXTERNAL_POWER_LIMIT_ADDRESS
RESULT_REGISTER = COMMAND_RESULT_ADDRESS


def connector_base(number: int) -> int:
    """First address of the block of the connector with a 1-based number."""
    return CONNECTOR_BASE + CONNECTOR_STRIDE * (number - 1)


def seed_device(unit: MockModbusUnit, *, connectors: int = 1) -> None:
    """Seed the device block of a three-phase, 32 A wallbox."""
    unit.input[DEVICE_BASE + 0x000] = 32  # main breaker
    unit.input[DEVICE_BASE + 0x001] = 32  # charger breaker
    unit.input[DEVICE_BASE + 0x002] = 3  # phases
    unit.input[DEVICE_BASE + 0x003] = 0  # free charging off
    unit.input[DEVICE_BASE + 0x004] = 11000  # user power ceiling
    unit.input[DEVICE_BASE + 0x005] = 7360  # available power
    unit.input[DEVICE_BASE + 0x006] = int(ChargingStrategy.ECO)
    unit.input[STATUS_REGISTER] = int(DeviceStatus.OPERATIONAL)
    unit.input[DEVICE_BASE + 0x008] = encode_int(86400, count=2)  # uptime
    unit.input[CONNECTOR_COUNT_REGISTER] = encode_int(connectors, count=2)
    unit.input[RESULT_REGISTER] = encode_int(COMMAND_RESULT_OK, count=2)
    unit.holding[POWER_LIMIT_REGISTER] = 7360


def seed_ac_connector(
    unit: MockModbusUnit, number: int = 1, *, connector_id: int | None = None
) -> None:
    """Seed one AC connector block with a car charging on three phases."""
    base = connector_base(number)
    unit.input[base + 0x00] = encode_int(0x1234_5678 + number, count=2)
    unit.input[base + 0x02] = number if connector_id is None else connector_id
    unit.input[base + 0x03] = int(CurrentFlow.AC)
    unit.input[base + 0x04] = int(ConnectionState.ONLINE)
    unit.input[base + 0x05] = int(VehicleState.WANTS_TO_CHARGE)
    unit.input[base + 0x06] = int(ChargingState.CHARGING_3F)
    unit.input[base + 0x07] = 1  # charging
    unit.input[base + 0x08] = 1  # authorized
    unit.input[base + 0x09] = int(AuthorizedBy.RFID)
    unit.input[base + 0x0A] = encode_float32(11000.0)
    unit.input[base + 0x0C] = encode_int(7150, count=2)
    unit.input[base + 0x0E] = encode_float32(236.1)
    unit.input[base + 0x10] = encode_float32(235.4)
    unit.input[base + 0x12] = encode_float32(237.0)
    unit.input[base + 0x14] = encode_float32(10.1)
    unit.input[base + 0x16] = encode_float32(10.0)
    unit.input[base + 0x18] = encode_float32(10.2)
    unit.input[base + 0x1A] = encode_float32(50.0)
    unit.input[base + 0x1C] = encode_float32(49.99)
    unit.input[base + 0x1E] = encode_float32(50.01)
    unit.input[base + 0x20] = encode_float32(3520.5)
    unit.input[base + 0x22] = encode_float32(12480.0)
    unit.input[base + 0x24] = encode_float32(1234567.0)
    unit.input[base + 0x26] = 0  # soc, AC reports 0
    unit.input[base + 0x28] = encode_float32(31.5)
    unit.input[base + 0x2A] = encode_float32(22.0)
    unit.holding[base + CONNECTOR_AUTHORIZE_OFFSET] = 0
    unit.holding[base + CONNECTOR_DEAUTHORIZE_OFFSET] = 0


def seed_dc_connector(unit: MockModbusUnit, number: int = 2) -> None:
    """Seed one DC connector block with a car at 74.5 % and nothing flowing."""
    seed_ac_connector(unit, number)
    base = connector_base(number)
    unit.input[base + 0x03] = int(CurrentFlow.DC)
    unit.input[base + 0x05] = int(VehicleState.CONNECTED)
    unit.input[base + 0x06] = int(ChargingState.PAUSED)
    unit.input[base + 0x07] = 0
    unit.input[base + 0x08] = 0
    unit.input[base + 0x09] = int(AuthorizedBy.NOT_CHARGING)
    unit.input[base + 0x0C] = encode_int(0, count=2)
    unit.input[base + 0x26] = 745


def seed_ac_charger(unit: MockModbusUnit) -> None:
    """Seed a single-connector AC wallbox."""
    seed_device(unit, connectors=1)
    seed_ac_connector(unit, 1)


def seed_dc_charger(unit: MockModbusUnit) -> None:
    """Seed a two-connector charger with an AC and a DC connector."""
    seed_device(unit, connectors=2)
    seed_ac_connector(unit, 1)
    seed_dc_connector(unit, 2)


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Add a config entry and set it up."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
