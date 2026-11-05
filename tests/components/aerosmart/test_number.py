"""Tests for the aerosmart number platform."""

from modbus_connection import ModbusConnectionError
from modbus_connection.mock import MockModbusUnit
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

ROOM_SETPOINT = "number.aerosmart_room_temperature_setpoint"
HOT_WATER_SETPOINT = "number.aerosmart_domestic_hot_water_temperature_setpoint"


async def test_number_entities_and_writes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit_ventilation: MockModbusUnit,
    mock_modbus_unit_heat_pump: MockModbusUnit,
) -> None:
    """Test temperature setpoint state and confirmed writes."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    room = hass.states.get(ROOM_SETPOINT)
    assert room is not None
    assert room.state == "21.0"
    assert room.attributes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    hot_water = hass.states.get(HOT_WATER_SETPOINT)
    assert hot_water is not None
    assert hot_water.state == "50.0"

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: ROOM_SETPOINT, "value": 21.5},
        blocking=True,
    )
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: HOT_WATER_SETPOINT, "value": 51.5},
        blocking=True,
    )

    assert [
        mock_modbus_unit_ventilation.holding[address] for address in (5016, 5017)
    ] == [0, 21500]
    assert [
        mock_modbus_unit_heat_pump.holding[address] for address in (5064, 5065)
    ] == [0, 51500]
    room = hass.states.get(ROOM_SETPOINT)
    assert room is not None
    assert room.state == "21.5"
    hot_water = hass.states.get(HOT_WATER_SETPOINT)
    assert hot_water is not None
    assert hot_water.state == "51.5"


async def test_number_write_error_is_translated(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit_ventilation: MockModbusUnit,
) -> None:
    """Test a rejected Modbus write becomes a Home Assistant error."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_modbus_unit_ventilation.fail_write(
        5016, ModbusConnectionError("simulated write failure")
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: ROOM_SETPOINT, "value": 21.5},
            blocking=True,
        )
