"""Fixtures for the aerosmart tests."""

from collections.abc import AsyncGenerator, Generator
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.aerosmart.const import (
    CONF_UNIT_HEAT_PUMP,
    CONF_UNIT_VENTILATION,
    DOMAIN,
    TYPE_TCP,
)
from homeassistant.components.modbus import async_get_temporary_unit, async_get_unit
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TYPE

UNIT_VENTILATION = 1
UNIT_HEAT_PUMP = 2


@dataclass
class MockModbusApi:
    """Mocks for the persistent and temporary Home Assistant Modbus APIs."""

    get_unit: MagicMock
    temporary_unit: MagicMock


# uint32 fields span 2 registers, big word order: [high_word, low_word].
VENTILATION_HOLDING: dict[int, list[int]] = {
    1174: [0, 3],  # general.wochentag
    202: [0, 123],  # outside_temperature.temp_aussenluft (scale 0.001 -> 0.123)
}
HEAT_PUMP_HOLDING: dict[int, list[int]] = {
    1044: [0, 1],  # heat_pump.waermepumpe
    1314: [0, 1],  # heat_pump.wp_status: Wärmepumpe aus
    212: [0, 45000],  # hot_water_heat_pump.warmwasser_speicher_oben (-> 45.0)
    1212: [0, 45],  # hot_water_heat_pump.wp_vorruebergehende_boilertemperatur
}


@pytest.fixture
def mock_modbus_unit_ventilation(
    mock_modbus_connection: MockModbusConnection,
) -> MockModbusUnit:
    """A seeded aerosmart ventilation unit (Modbus unit 1)."""
    unit = mock_modbus_connection.for_unit(UNIT_VENTILATION)
    for address, words in VENTILATION_HOLDING.items():
        unit.holding[address] = words
    return unit


@pytest.fixture
def mock_modbus_unit_heat_pump(
    mock_modbus_connection: MockModbusConnection,
) -> MockModbusUnit:
    """A seeded aerosmart heat pump unit (Modbus unit 2)."""
    unit = mock_modbus_connection.for_unit(UNIT_HEAT_PUMP)
    for address, words in HEAT_PUMP_HOLDING.items():
        unit.holding[address] = words
    return unit


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent the created entry from actually setting up during flow tests."""
    with patch(
        "homeassistant.components.aerosmart.async_setup_entry",
        return_value=None,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(autouse=True)
async def mock_modbus_api(
    mock_modbus_connection: MockModbusConnection,
) -> AsyncGenerator[MockModbusApi]:
    """Route Home Assistant's shared Modbus API through the in-memory mock."""
    await mock_modbus_connection.connect()
    get_unit = MagicMock(wraps=async_get_unit)
    temporary_unit_factory = MagicMock(wraps=async_get_temporary_unit)
    with (
        patch("homeassistant.components.aerosmart.async_get_unit", get_unit),
        patch(
            "homeassistant.components.aerosmart.config_flow.async_get_temporary_unit",
            temporary_unit_factory,
        ),
        patch(
            "homeassistant.components.modbus.connection.ModbusConnection",
            return_value=mock_modbus_connection,
        ),
    ):
        yield MockModbusApi(get_unit=get_unit, temporary_unit=temporary_unit_factory)


@pytest.fixture
def mock_config_entry(
    mock_modbus_unit_ventilation: MockModbusUnit,
    mock_modbus_unit_heat_pump: MockModbusUnit,
) -> MockConfigEntry:
    """An aerosmart config entry using Home Assistant's shared connection."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="aerosmart",
        entry_id="01JZ8M2Q4T6Y9V3B5N7K1W0XAE",
        data={
            CONF_TYPE: TYPE_TCP,
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 502,
            CONF_UNIT_VENTILATION: UNIT_VENTILATION,
            CONF_UNIT_HEAT_PUMP: UNIT_HEAT_PUMP,
        },
    )
