"""Tests for the Flexit climate platform."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_HVAC_ACTION,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    DOMAIN as CLIMATE_DOMAIN,
    HVACAction,
    HVACMode,
)
from homeassistant.components.flexit.climate import (
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CALL_TYPE_WRITE_REGISTER,
)
from homeassistant.components.modbus import DATA_MODBUS_HUBS, ModbusHub
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.components.climate.common import async_set_fan_mode, async_set_temperature

ENTITY_ID = "climate.flexit"
HUB_NAME = "modbus_hub"

# Default register map matching a plausible, "healthy" device response.
DEFAULT_REGISTERS: dict[tuple[str, int], int | None] = {
    (CALL_TYPE_REGISTER_HOLDING, 8): 215,  # target_temperature -> 21.5
    (CALL_TYPE_REGISTER_INPUT, 9): 200,  # current_temperature -> 20.0
    (CALL_TYPE_REGISTER_HOLDING, 17): 2,  # fan_mode index -> "Medium"
    (CALL_TYPE_REGISTER_INPUT, 8): 120,  # filter_hours
    (CALL_TYPE_REGISTER_INPUT, 14): 0,  # heat_recovery
    (CALL_TYPE_REGISTER_INPUT, 15): 0,  # heating
    (CALL_TYPE_REGISTER_INPUT, 13): 0,  # cooling
    (CALL_TYPE_REGISTER_INPUT, 27): 0,  # filter_alarm raw
    (CALL_TYPE_REGISTER_INPUT, 28): 0,  # heater_enabled raw
    (CALL_TYPE_REGISTER_INPUT, 11): 50,  # outdoor_air_temp -> 5.0
    (CALL_TYPE_REGISTER_INPUT, 48): 0,  # actual_air_speed
}


def _mock_hub(
    registers: dict[tuple[str, int], int | None],
) -> tuple[ModbusHub, AsyncMock]:
    """Create a mocked ModbusHub returning canned register values.

    A `None` value simulates a failed Modbus read (hub returns None). Writes
    always succeed and update `registers` in place, so a subsequent poll
    reads back the written value, unless the caller replaces the mock's
    return value.
    """

    async def async_pb_call(
        _slave: int | None, register: int, value: int, call_type: str
    ) -> MagicMock | None:
        if call_type == CALL_TYPE_WRITE_REGISTER:
            registers[(CALL_TYPE_REGISTER_HOLDING, register)] = value
            return MagicMock()
        raw = registers.get((call_type, register))
        if raw is None:
            return None
        return MagicMock(registers=[raw])

    hub = MagicMock(spec=ModbusHub)
    hub.async_pb_call = AsyncMock(side_effect=async_pb_call)
    return hub, hub.async_pb_call


async def _setup_flexit(
    hass: HomeAssistant,
    registers: dict[tuple[str, int], int | None] | None = None,
) -> AsyncMock:
    """Set up the flexit climate platform backed by a mocked Modbus hub."""
    hub, mock_call = _mock_hub(
        registers if registers is not None else DEFAULT_REGISTERS.copy()
    )
    hass.data.setdefault(DATA_MODBUS_HUBS, {})[HUB_NAME] = hub

    assert await async_setup_component(
        hass,
        CLIMATE_DOMAIN,
        {
            CLIMATE_DOMAIN: [
                {
                    "platform": "flexit",
                    "slave": 1,
                    "name": "Flexit",
                }
            ]
        },
    )
    await hass.async_block_till_done()

    return mock_call


async def test_static_attributes(hass: HomeAssistant) -> None:
    """Test static entity attributes match the device spec."""
    await _setup_flexit(hass)

    state = hass.states.get(ENTITY_ID)
    assert state.state == HVACMode.HEAT_COOL
    assert state.attributes[ATTR_MIN_TEMP] == 10.0
    assert state.attributes[ATTR_MAX_TEMP] == 30.0


async def test_setup_reads_temperatures_and_fan_mode(hass: HomeAssistant) -> None:
    """Test platform setup populates temperature and fan mode from registers."""
    await _setup_flexit(hass)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_TEMPERATURE] == 21.5
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 20.0
    assert state.attributes[ATTR_FAN_MODE] == "Medium"


async def test_filter_alarm_and_heater_enabled_are_bool(hass: HomeAssistant) -> None:
    """Test filter_alarm and heater_enabled are surfaced as bool, not int."""
    registers = DEFAULT_REGISTERS.copy()
    registers[(CALL_TYPE_REGISTER_INPUT, 27)] = 1
    registers[(CALL_TYPE_REGISTER_INPUT, 28)] = 1
    await _setup_flexit(hass, registers)

    attrs = hass.states.get(ENTITY_ID).attributes
    assert attrs["filter_alarm"] is True
    assert attrs["heater_enabled"] is True
    assert isinstance(attrs["filter_alarm"], bool)
    assert isinstance(attrs["heater_enabled"], bool)


async def test_filter_alarm_and_heater_enabled_false(hass: HomeAssistant) -> None:
    """Test filter_alarm and heater_enabled are False (bool) when register is 0."""
    await _setup_flexit(hass)

    attrs = hass.states.get(ENTITY_ID).attributes
    assert attrs["filter_alarm"] is False
    assert attrs["heater_enabled"] is False


async def test_handles_negative_register_values(hass: HomeAssistant) -> None:
    """Test signed 16-bit conversion of negative register values."""
    registers = DEFAULT_REGISTERS.copy()
    # 65536 - 50 = 65486 -> should be converted back to -50 -> -5.0 degrees.
    registers[(CALL_TYPE_REGISTER_INPUT, 11)] = 65486
    registers[(CALL_TYPE_REGISTER_INPUT, 9)] = 65516  # -20 raw -> -2.0 degrees
    await _setup_flexit(hass, registers)

    attrs = hass.states.get(ENTITY_ID).attributes
    assert attrs[ATTR_CURRENT_TEMPERATURE] == -2.0
    assert attrs["outdoor_air_temp"] == -5.0


async def test_returns_none_on_failed_reads(hass: HomeAssistant) -> None:
    """Test attributes become None (not 0/False) when a Modbus read fails."""
    registers: dict[tuple[str, int], int | None] = DEFAULT_REGISTERS.copy()
    registers[(CALL_TYPE_REGISTER_INPUT, 27)] = None  # filter_alarm read fails
    registers[(CALL_TYPE_REGISTER_INPUT, 28)] = None  # heater_enabled read fails
    registers[(CALL_TYPE_REGISTER_INPUT, 8)] = None  # filter_hours read fails
    await _setup_flexit(hass, registers)

    attrs = hass.states.get(ENTITY_ID).attributes
    assert attrs["filter_alarm"] is None
    assert attrs["heater_enabled"] is None
    assert attrs["filter_hours"] is None


@pytest.mark.parametrize(
    ("heating", "cooling", "heat_recovery", "air_speed", "expected_action"),
    [
        (10, 0, 0, 0, HVACAction.HEATING),
        (0, 10, 0, 0, HVACAction.COOLING),
        (0, 0, 10, 0, HVACAction.IDLE),
        (0, 0, 0, 10, HVACAction.FAN),
        (0, 0, 0, 0, HVACAction.OFF),
    ],
)
async def test_hvac_action(
    hass: HomeAssistant,
    heating: int,
    cooling: int,
    heat_recovery: int,
    air_speed: int,
    expected_action: HVACAction,
) -> None:
    """Test hvac_action resolves based on heating/cooling/recovery/air speed."""
    registers = DEFAULT_REGISTERS.copy()
    registers[(CALL_TYPE_REGISTER_INPUT, 15)] = heating
    registers[(CALL_TYPE_REGISTER_INPUT, 13)] = cooling
    registers[(CALL_TYPE_REGISTER_INPUT, 14)] = heat_recovery
    registers[(CALL_TYPE_REGISTER_INPUT, 48)] = air_speed
    await _setup_flexit(hass, registers)

    assert hass.states.get(ENTITY_ID).attributes[ATTR_HVAC_ACTION] is expected_action


async def test_extra_state_attributes(hass: HomeAssistant) -> None:
    """Test all flexit-specific state attributes are surfaced correctly."""
    await _setup_flexit(hass)

    attrs = hass.states.get(ENTITY_ID).attributes
    assert attrs["filter_hours"] == 120
    assert attrs["filter_alarm"] is False
    assert attrs["heat_recovery"] == 0
    assert attrs["heating"] == 0
    assert attrs["heater_enabled"] is False
    assert attrs["cooling"] == 0
    assert attrs["outdoor_air_temp"] == 5.0


async def test_async_set_temperature(hass: HomeAssistant) -> None:
    """Test setting a valid target temperature writes to the register."""
    mock_call = await _setup_flexit(hass)

    await async_set_temperature(hass, temperature=22.5, entity_id=ENTITY_ID)

    assert hass.states.get(ENTITY_ID).attributes[ATTR_TEMPERATURE] == 22.5
    mock_call.assert_any_await(1, 8, 225, CALL_TYPE_WRITE_REGISTER)


async def test_async_set_temperature_write_failure_does_not_update_state(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failed Modbus write does not update target_temperature."""
    registers = DEFAULT_REGISTERS.copy()
    registers[(CALL_TYPE_REGISTER_HOLDING, 8)] = None  # initial read also fails
    mock_call = await _setup_flexit(hass, registers)
    mock_call.side_effect = None
    mock_call.return_value = None
    caplog.set_level(logging.ERROR, logger="homeassistant.components.flexit.climate")

    await async_set_temperature(hass, temperature=22.5, entity_id=ENTITY_ID)

    mock_call.assert_any_await(1, 8, 225, CALL_TYPE_WRITE_REGISTER)
    assert "Modbus error setting target temperature to Flexit" in caplog.text
    assert hass.states.get(ENTITY_ID).attributes[ATTR_TEMPERATURE] is None


async def test_async_set_fan_mode(hass: HomeAssistant) -> None:
    """Test setting a valid fan mode writes the correct index to the register."""
    mock_call = await _setup_flexit(hass)

    await async_set_fan_mode(hass, "High", entity_id=ENTITY_ID)

    assert hass.states.get(ENTITY_ID).attributes[ATTR_FAN_MODE] == "High"
    mock_call.assert_any_await(1, 17, 3, CALL_TYPE_WRITE_REGISTER)


async def test_async_set_fan_mode_write_failure_does_not_update_state(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failed Modbus write does not update fan_mode."""
    registers = DEFAULT_REGISTERS.copy()
    registers[(CALL_TYPE_REGISTER_HOLDING, 17)] = None  # initial read also fails
    mock_call = await _setup_flexit(hass, registers)
    mock_call.side_effect = None
    mock_call.return_value = None
    caplog.set_level(logging.ERROR, logger="homeassistant.components.flexit.climate")

    await async_set_fan_mode(hass, "High", entity_id=ENTITY_ID)

    mock_call.assert_any_await(1, 17, 3, CALL_TYPE_WRITE_REGISTER)
    assert "Modbus error setting fan mode to Flexit" in caplog.text
    assert hass.states.get(ENTITY_ID).attributes[ATTR_FAN_MODE] is None
