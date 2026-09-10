"""Fixtures for the SolarEdge Modbus tests.

The ``mock_modbus_connection`` / ``mock_modbus_unit`` fixtures come from the
``modbus-connection`` library's pytest plugin (registered as a ``pytest11``
entry point). Seeding the unit's holding store with a captured register dump
drives the real ``solaredged`` library exactly as a device would.
"""

from collections.abc import AsyncIterator, Generator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import patch

from modbus_connection import ModbusUnit
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest

from homeassistant.components.solaredge_modbus.const import (
    CONF_UNIT_ID,
    DOMAIN,
    TYPE_TCP,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_load_json_object_fixture

HOST = "1.2.3.4"
PORT = 1502
UNIT_ID = 1
SERIAL_NUMBER = "7E123ABC"
METER_SERIAL_NUMBER = "7E4A11C2"
BATTERY_SERIAL_NUMBERS = ("7E7C33E4", "7E8D44F5")

# Where a meter's block starts, how far the next one sits, and where in it the
# serial number lives, as SunSpec lays them out.
METER_BASE = 40121
METER_STRIDE = 174
METER_SERIAL_BASE = 40171

# The same for the batteries, whose blocks sit at fixed offsets rather than a
# stride, with the rated-energy register the probe counts them by.
BATTERY_SERIAL_BASE = 57648
BATTERY_RATED_ENERGY = 57666
BATTERY_OFFSETS = (0, 256, 768)


def tcp_data(unit_id: int = UNIT_ID) -> dict[str, Any]:
    """Config entry data for an inverter reached over Modbus TCP."""
    return {
        CONF_TYPE: TYPE_TCP,
        CONF_HOST: HOST,
        CONF_PORT: PORT,
        CONF_UNIT_ID: unit_id,
    }


async def async_seed_unit(
    hass: HomeAssistant, unit: MockModbusUnit, serial_registers: list[int] | None = None
) -> None:
    """Seed a mock unit with the captured SE10000H register dump.

    The capture predates several of the points this integration reads, so those
    registers carry hand-picked values instead: distinct per point, and
    consistent with what the device did report (phase values sum to the
    recorded totals, apparent power exceeds real power). The meter's identity
    block is hand-picked the same way, since the capture skips it. Pass
    ``serial_registers`` to override the inverter serial number ("7E123ABC" as
    captured).
    """
    registers = (await async_load_json_object_fixture(hass, "se10000h.json", DOMAIN))[
        "holding"
    ]
    unit.holding.update({int(address): value for address, value in registers.items()})

    if serial_registers is not None:
        unit.holding.update(
            dict(zip(range(40052, 40056), serial_registers, strict=True))
        )


def add_second_meter(unit: MockModbusUnit, serial_number: str) -> None:
    """Wire a second meter onto a seeded unit.

    Every address of a meter shifts by the SunSpec stride per meter, so the
    first meter's block, copied one stride up, is a second meter that reports
    the same measurements under its own serial number.
    """
    block = {
        address + METER_STRIDE: value
        for address, value in unit.holding.items()
        if METER_BASE <= address < METER_BASE + METER_STRIDE
    }
    padded = serial_number.ljust(32, "\0").encode()
    block.update(
        {
            METER_SERIAL_BASE + METER_STRIDE + index: (
                (padded[index * 2] << 8) | padded[index * 2 + 1]
            )
            for index in range(16)
        }
    )
    unit.holding.update(block)


@pytest.fixture
async def mock_modbus_unit(
    hass: HomeAssistant, mock_modbus_connection: MockModbusConnection
) -> MockModbusUnit:
    """A seeded SolarEdge inverter on unit ``UNIT_ID``.

    Overrides the library plugin's ``mock_modbus_unit`` to preload a captured
    register dump of an SE10000H.
    """
    unit = mock_modbus_connection.for_unit(UNIT_ID)
    await async_seed_unit(hass, unit)
    return unit


@pytest.fixture(autouse=True)
def mock_shared_connection(
    mock_modbus_connection: MockModbusConnection, mock_modbus_unit: MockModbusUnit
) -> Generator[None]:
    """Hand out units on the seeded mock instead of opening a real connection."""

    @asynccontextmanager
    async def async_temporary_unit(
        hass: HomeAssistant, params: Any, unit_id: int
    ) -> AsyncIterator[ModbusUnit]:
        yield mock_modbus_connection.for_unit(unit_id)

    with (
        patch(
            "homeassistant.components.solaredge_modbus.async_get_unit",
            side_effect=lambda hass, entry, params, unit_id: (
                mock_modbus_connection.for_unit(unit_id)
            ),
        ),
        patch(
            "homeassistant.components.solaredge_modbus.config_flow.async_get_temporary_unit",
            async_temporary_unit,
        ),
    ):
        yield


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """A SolarEdge Modbus config entry for the seeded inverter."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="SolarEdge SE10000H",
        unique_id=SERIAL_NUMBER,
        data=tcp_data(),
    )
