"""Tests for the Flexit climate platform."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.climate import HVACAction, HVACMode
from homeassistant.components.flexit.climate import (
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CALL_TYPE_WRITE_REGISTER,
    Flexit,
)
from homeassistant.components.modbus import ModbusHub
from homeassistant.const import ATTR_TEMPERATURE

# Default register map matching a plausible, "healthy" device response.
DEFAULT_REGISTERS: dict[tuple[str, int], int] = {
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


def _make_hub(
    registers: dict[tuple[str, int], int | None],
) -> tuple[ModbusHub, AsyncMock]:
    """Create a mocked ModbusHub returning canned register values.

    A `None` value simulates a failed Modbus read (hub returns None). Writes
    always succeed unless the caller replaces the mock's return value.
    """

    async def async_pb_call(
        _slave: int | None, register: int, value: int, call_type: str
    ) -> MagicMock | None:
        if call_type == CALL_TYPE_WRITE_REGISTER:
            return MagicMock()
        raw = registers.get((call_type, register))
        if raw is None:
            return None
        return MagicMock(registers=[raw])

    hub = MagicMock(spec=ModbusHub)
    hub.async_pb_call = AsyncMock(side_effect=async_pb_call)
    return hub, hub.async_pb_call


def _make_flexit(
    registers: dict[tuple[str, int], int | None] | None = None,
) -> Flexit:
    """Create a Flexit entity backed by a mocked hub."""
    hub, _ = _make_hub(registers if registers is not None else DEFAULT_REGISTERS)
    return Flexit(hub, 1, "Flexit")


async def test_static_attributes() -> None:
    """Test static entity attributes match the device spec."""
    flexit = _make_flexit()

    assert flexit.hvac_mode == HVACMode.HEAT_COOL
    assert flexit.hvac_modes == [HVACMode.HEAT_COOL]
    assert flexit.min_temp == 10.0
    assert flexit.max_temp == 30.0


async def test_async_update_reads_temperatures_and_fan_mode() -> None:
    """Test async_update populates temperature and fan mode from registers."""
    flexit = _make_flexit()

    await flexit.async_update()

    assert flexit.target_temperature == 21.5
    assert flexit.current_temperature == 20.0
    assert flexit.fan_mode == "Medium"


async def test_async_update_filter_alarm_and_heater_enabled_are_bool() -> None:
    """Test filter_alarm and heater_enabled are surfaced as bool, not int."""
    registers = DEFAULT_REGISTERS.copy()
    registers[(CALL_TYPE_REGISTER_INPUT, 27)] = 1
    registers[(CALL_TYPE_REGISTER_INPUT, 28)] = 1
    flexit = _make_flexit(registers)

    await flexit.async_update()

    attrs = flexit.extra_state_attributes
    assert attrs["filter_alarm"] is True
    assert attrs["heater_enabled"] is True
    assert isinstance(attrs["filter_alarm"], bool)
    assert isinstance(attrs["heater_enabled"], bool)


async def test_async_update_filter_alarm_and_heater_enabled_false() -> None:
    """Test filter_alarm and heater_enabled are False (bool) when register is 0."""
    flexit = _make_flexit()

    await flexit.async_update()

    attrs = flexit.extra_state_attributes
    assert attrs["filter_alarm"] is False
    assert attrs["heater_enabled"] is False


async def test_async_update_handles_negative_register_values() -> None:
    """Test signed 16-bit conversion of negative register values."""
    registers = DEFAULT_REGISTERS.copy()
    # 65536 - 50 = 65486 -> should be converted back to -50 -> -5.0 degrees.
    registers[(CALL_TYPE_REGISTER_INPUT, 11)] = 65486
    registers[(CALL_TYPE_REGISTER_INPUT, 9)] = 65516  # -20 raw -> -2.0 degrees
    flexit = _make_flexit(registers)

    await flexit.async_update()

    assert flexit.current_temperature == -2.0
    assert flexit.extra_state_attributes["outdoor_air_temp"] == -5.0


async def test_async_update_returns_none_on_failed_reads() -> None:
    """Test attributes become None (not 0/False) when a Modbus read fails."""
    registers: dict[tuple[str, int], int | None] = DEFAULT_REGISTERS.copy()
    registers[(CALL_TYPE_REGISTER_INPUT, 27)] = None  # filter_alarm read fails
    registers[(CALL_TYPE_REGISTER_INPUT, 28)] = None  # heater_enabled read fails
    registers[(CALL_TYPE_REGISTER_INPUT, 8)] = None  # filter_hours read fails
    flexit = _make_flexit(registers)

    await flexit.async_update()

    attrs = flexit.extra_state_attributes
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
async def test_async_update_hvac_action(
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
    flexit = _make_flexit(registers)

    await flexit.async_update()

    assert flexit.hvac_action is expected_action


async def test_extra_state_attributes() -> None:
    """Test all extra_state_attributes keys/values are surfaced correctly."""
    flexit = _make_flexit()

    await flexit.async_update()

    assert flexit.extra_state_attributes == {
        "filter_hours": 120,
        "filter_alarm": False,
        "heat_recovery": 0,
        "heating": 0,
        "heater_enabled": False,
        "cooling": 0,
        "outdoor_air_temp": 5.0,
    }


async def test_async_set_temperature() -> None:
    """Test setting a valid target temperature writes to the register."""
    hub, mock_call = _make_hub(DEFAULT_REGISTERS)
    flexit = Flexit(hub, 1, "Flexit")

    await flexit.async_set_temperature(**{ATTR_TEMPERATURE: 22.5})

    assert flexit.target_temperature == 22.5
    mock_call.assert_awaited_with(1, 8, 225, CALL_TYPE_WRITE_REGISTER)


async def test_async_set_temperature_missing_value_is_noop() -> None:
    """Test missing ATTR_TEMPERATURE does not write to the hub."""
    hub, mock_call = _make_hub(DEFAULT_REGISTERS)
    flexit = Flexit(hub, 1, "Flexit")

    await flexit.async_set_temperature()

    mock_call.assert_not_awaited()
    assert flexit.target_temperature is None


async def test_async_set_temperature_write_failure_does_not_update_state() -> None:
    """Test a failed Modbus write does not update target_temperature."""
    hub, mock_call = _make_hub(DEFAULT_REGISTERS)
    mock_call.side_effect = None
    mock_call.return_value = None
    flexit = Flexit(hub, 1, "Flexit")

    await flexit.async_set_temperature(**{ATTR_TEMPERATURE: 22.5})

    assert flexit.target_temperature is None


async def test_async_set_fan_mode() -> None:
    """Test setting a valid fan mode writes the correct index to the register."""
    hub, mock_call = _make_hub(DEFAULT_REGISTERS)
    flexit = Flexit(hub, 1, "Flexit")

    await flexit.async_set_fan_mode("High")

    assert flexit.fan_mode == "High"
    mock_call.assert_awaited_with(1, 17, 3, CALL_TYPE_WRITE_REGISTER)


async def test_async_set_fan_mode_write_failure_does_not_update_state() -> None:
    """Test a failed Modbus write does not update fan_mode."""
    hub, mock_call = _make_hub(DEFAULT_REGISTERS)
    mock_call.side_effect = None
    mock_call.return_value = None
    flexit = Flexit(hub, 1, "Flexit")

    await flexit.async_set_fan_mode("High")

    assert flexit.fan_mode is None
