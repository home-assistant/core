"""Common fixtures for the SMA Modbus integration tests.

The tests use a seeded ``MockModbusConnection`` from ``modbus_connection.mock``.
The mock unit is patched into ``async_get_unit`` and
``async_get_temporary_unit`` so the SMA library can read discovery registers
from it, just like it would from a real device.
"""

from collections.abc import Generator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import patch

from modbus_connection.mock import MockModbusUnit
import pytest

from homeassistant.core import HomeAssistant

from . import make_config_entry, make_mock_unit

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """A SMA Modbus config entry."""
    return make_config_entry()


@pytest.fixture(autouse=True)
def mock_async_get_unit(hass: HomeAssistant) -> Generator[MockModbusUnit]:
    """Seed a mock unit and patch async_get_unit / async_get_temporary_unit.

    The same seeded unit is returned for any unit ID so the sma_modbus
    library's ``for_unit()`` calls (including cross-unit Type Label reads)
    all resolve to it.
    """
    unit = make_mock_unit()

    @asynccontextmanager
    async def _async_get_temporary_unit_mock(
        hass: HomeAssistant, params: Any, unit_id: int
    ) -> Any:
        yield make_mock_unit()

    with (
        patch(
            "homeassistant.components.sma_modbus.async_get_unit",
            return_value=unit,
        ),
        patch(
            "homeassistant.components.sma_modbus.config_flow.async_get_temporary_unit",
            _async_get_temporary_unit_mock,
        ),
    ):
        yield unit
