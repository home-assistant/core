"""Fixtures for the IONT tests.

The ``mock_modbus_connection`` fixture comes from the ``modbus-connection``
library's pytest plugin. Its ``mock_modbus_unit`` is overridden here to come
seeded as a single-connector AC wallbox.
"""

from collections.abc import AsyncIterator, Generator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, patch

from modbus_connection import ModbusUnit
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest

from homeassistant.components.iont.const import DOMAIN, UNIT_ID
from homeassistant.core import HomeAssistant

from . import MOCK_TITLE, MOCK_USER_INPUT, seed_ac_charger, setup_integration

from tests.common import MockConfigEntry


@pytest.fixture
def mock_modbus_unit(mock_modbus_connection: MockModbusConnection) -> MockModbusUnit:
    """A seeded AC wallbox on the unit ID the integration talks to."""
    unit = mock_modbus_connection.for_unit(UNIT_ID)
    seed_ac_charger(unit)
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
            "homeassistant.components.iont.async_get_unit",
            side_effect=lambda hass, entry, params, unit_id: (
                mock_modbus_connection.for_unit(unit_id)
            ),
        ),
        patch(
            "homeassistant.components.iont.config_flow.async_get_temporary_unit",
            async_temporary_unit,
        ),
    ):
        yield


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.iont.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """An IONT config entry for the seeded charger."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_TITLE,
        data=MOCK_USER_INPUT,
        entry_id="01JIONTCHARGER00000000000A",
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the IONT integration for testing."""
    await setup_integration(hass, mock_config_entry)
    return mock_config_entry
