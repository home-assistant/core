"""Fixtures for the BLUETTI Modbus tests.

The ``mock_modbus_connection`` / ``mock_modbus_unit`` fixtures come from the
``modbus-connection`` library's pytest plugin (registered as a ``pytest11``
entry point).
"""

from collections.abc import AsyncIterator, Generator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import patch

from bluetti_modbus_lib.devices.getter import get_device
from modbus_connection import ModbusUnit
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest

from homeassistant.components.bluetti_modbus.const import (
    CONF_UNIT_ID,
    DEVICE_TYPE_BALCO260,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

HOST = "1.2.3.4"
PORT = 502
UNIT_ID = 1
ENTRY_ID = "01K3ZZZZZZZZZZZZZZZZZZZZZZ"
# A real Balco260 always has a non-zero manufactured serial (the config flow
# rejects 0 as not a real device identity - see config_flow.py), so this
# can't be zero-seeded like everything else; seed_unit() overrides it after
# the generic zero pass.
SERIAL = "1234"


def bluetti_data(unit_id: int = UNIT_ID) -> dict[str, Any]:
    """Config entry data for a device reached over Modbus TCP."""
    return {
        CONF_HOST: HOST,
        CONF_PORT: PORT,
        CONF_UNIT_ID: unit_id,
    }


def seed_unit(unit: MockModbusUnit) -> None:
    """Seed a mock unit so every field Balco260 has decodes cleanly.

    There is no captured full register dump for this hardware yet (unlike a
    single self-describing header block, BLUETTI's map has none to capture
    once): every field's own registers are zeroed directly from the library's
    field metadata instead. Zero decodes safely everywhere, including the
    enum-typed status/warning/fault fields, whose "normal" member is always 0
    - except d_serial, which the config flow treats 0 as a failed probe, not
    a real device (see config_flow.py); the register holding its
    least-significant word is overridden with SERIAL's value afterwards.
    """
    device = get_device(DEVICE_TYPE_BALCO260)
    assert device is not None
    for name in device.field_names():
        field = device.get_field(name)
        assert field is not None
        for offset in range(field.count):
            unit.holding[field.address + offset] = 0

    serial_field = device.get_field("d_serial")
    assert serial_field is not None
    unit.holding[serial_field.address] = int(SERIAL)


@pytest.fixture(autouse=True)
def mock_shared_connection(
    mock_modbus_connection: MockModbusConnection,
) -> Generator[None]:
    """Hand out units on the seeded mock instead of opening a real connection."""

    @asynccontextmanager
    async def async_temporary_unit(
        hass: HomeAssistant, params: Any, unit_id: int
    ) -> AsyncIterator[ModbusUnit]:
        yield mock_modbus_connection.for_unit(unit_id)

    with (
        patch(
            "homeassistant.components.bluetti_modbus.async_get_unit",
            side_effect=lambda hass, entry, params, unit_id: (
                mock_modbus_connection.for_unit(unit_id)
            ),
        ),
        patch(
            "homeassistant.components.bluetti_modbus.config_flow.async_get_temporary_unit",
            async_temporary_unit,
        ),
    ):
        yield


@pytest.fixture
def mock_modbus_unit(mock_modbus_connection: MockModbusConnection) -> MockModbusUnit:
    """A seeded BLUETTI power station on unit ``UNIT_ID``.

    Overrides the library plugin's ``mock_modbus_unit`` to preload every
    register this device type's fields cover.
    """
    unit = mock_modbus_connection.for_unit(UNIT_ID)
    seed_unit(unit)
    return unit


@pytest.fixture
def mock_config_entry(mock_modbus_unit: MockModbusUnit) -> MockConfigEntry:
    """A BLUETTI Modbus config entry for the seeded device."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id=ENTRY_ID,
        unique_id=SERIAL,
        title="Balco260",
        data=bluetti_data(),
    )
