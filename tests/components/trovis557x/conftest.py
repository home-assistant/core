"""Fixtures for the Trovis 557x tests.

The ``mock_modbus_connection`` / ``mock_modbus_unit`` fixtures come from the
``modbus_connection`` library's pytest plugin (registered as a ``pytest11``
entry point). Seeding the unit's stores drives the real ``trovis_modbus``
library exactly as a device would.
"""

from unittest.mock import AsyncMock, patch

from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest

from homeassistant.components.modbus_connection.const import (
    CONNECTION_TCP,
    DOMAIN as MODBUS_CONNECTION_DOMAIN,
)
from homeassistant.components.trovis557x.const import (
    CONF_CONNECTION,
    CONF_UNIT_ID,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

UNIT_ID = 247

HOLDING: dict[int, int] = {
    0: 5579,  # model
    2: 305,  # firmware -> 3.05
    3: 110,  # hardware -> 1.10
    5: 12345,  # serial
    9: 123,  # outside_1 -> 12.3
    19: 200,  # room_1 -> 20.0
    22: 450,  # storage_1 -> 45.0
    98: 900,  # max flow setpoint -> 90.0
    99: 1430,  # time
    100: 2106,  # date
    101: 2026,  # year
    102: 1,  # switch_top -> AUTOMATIC
    105: 1,  # hc1 mode -> AUTOMATIC
    106: 42,  # hc1 control signal
    111: 1,  # hot_water mode -> AUTOMATIC
    999: 550,  # hc1 flow_setpoint -> 55.0
    1000: 800,  # hc1 flow_max
    1001: 200,  # hc1 flow_min
    1002: 210,  # hc1 room_setpoint_day -> 21.0
    1003: 180,  # hc1 room_setpoint_night
    1004: 210,  # hc1 room_setpoint_active -> 21.0
    1005: 12,  # hc1 slope
    1006: 0,  # hc1 level
    1799: 500,  # hot_water setpoint_day -> 50.0
    1800: 600,  # hot_water setpoint_max
    1801: 450,  # hot_water setpoint_min
    1807: 500,  # hot_water setpoint_active -> 50.0
    1837: 670,  # hot_water active_charge_setpoint -> 67.0
}
COILS: dict[int, bool] = {
    56: True,  # hc1 pump
    999: True,  # hc1 automatic
    1000: True,  # hc1 day active
    59: True,  # hot_water charge pump
    1799: True,  # hot_water automatic
}


@pytest.fixture
def mock_modbus_unit(
    mock_modbus_connection: MockModbusConnection,
) -> MockModbusUnit:
    """A seeded Trovis controller on unit ``UNIT_ID``.

    Overrides the library plugin's ``mock_modbus_unit`` to pick the Trovis unit
    and preload a full controller register/coil image.
    """
    unit = mock_modbus_connection.for_unit(UNIT_ID)
    for address, value in HOLDING.items():
        unit.holding[address] = value
    for address, value in COILS.items():
        unit.coils[address] = value
    return unit


@pytest.fixture
async def connection_entry(
    hass: HomeAssistant,
    mock_modbus_connection: MockModbusConnection,
    mock_modbus_unit: MockModbusUnit,
) -> MockConfigEntry:
    """Set up a loaded ``modbus_connection`` entry backed by the seeded mock."""
    entry = MockConfigEntry(
        domain=MODBUS_CONNECTION_DOMAIN,
        title="1.2.3.4:502",
        data={CONF_TYPE: CONNECTION_TCP, CONF_HOST: "1.2.3.4", CONF_PORT: 502},
    )
    entry.add_to_hass(hass)
    connect = AsyncMock(return_value=mock_modbus_connection)
    with (
        patch("homeassistant.components.modbus_connection.connect_tcp", connect),
        patch("homeassistant.components.modbus_connection.connect_serial", connect),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


@pytest.fixture
def mock_config_entry(connection_entry: MockConfigEntry) -> MockConfigEntry:
    """A Trovis config entry pointing at ``connection_entry`` and ``UNIT_ID``."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Trovis 5579",
        data={
            CONF_CONNECTION: connection_entry.entry_id,
            CONF_UNIT_ID: UNIT_ID,
        },
    )
