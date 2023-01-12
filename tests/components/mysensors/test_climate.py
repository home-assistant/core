"""Provide tests for mysensors climate platform."""
from __future__ import annotations

from collections.abc import Callable
from unittest.mock import MagicMock, call

from mysensors.sensor import Sensor

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant


async def test_hvac_node_auto(
    hass: HomeAssistant,
    hvac_node_auto: Sensor,
    receive_message: Callable[[str], None],
    transport_write: MagicMock,
) -> None:
    """Test a hvac auto node."""
    entity_id = "climate.hvac_node_1_1"

    state = hass.states.get(entity_id)

    assert state
    assert state.state == HVACMode.OFF

    # Test set hvac mode auto
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.AUTO},
        blocking=True,
    )

    assert transport_write.call_count == 1
    assert transport_write.call_args == call("1;1;1;1;21;AutoChangeOver\n")

    receive_message("1;1;1;0;21;AutoChangeOver\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == HVACMode.AUTO
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] == 21.0
    assert state.attributes[ATTR_TARGET_TEMP_LOW] == 19.0
    assert state.attributes[ATTR_FAN_MODE] == "Normal"
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 20.0

    transport_write.reset_mock()

    # Test set low/high target temperature
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TARGET_TEMP_HIGH: 22.0,
            ATTR_TARGET_TEMP_LOW: 20.0,
        },
        blocking=True,
    )

    assert transport_write.call_count == 2
    assert transport_write.call_args_list[0] == call("1;1;1;1;45;20.0\n")
    assert transport_write.call_args_list[1] == call("1;1;1;1;44;22.0\n")

    receive_message("1;1;1;0;45;20.0\n")
    receive_message("1;1;1;0;44;22.0\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == HVACMode.AUTO
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] == 22.0
    assert state.attributes[ATTR_TARGET_TEMP_LOW] == 20.0
    assert state.attributes[ATTR_FAN_MODE] == "Normal"

    transport_write.reset_mock()

    # Test set fan mode
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_FAN_MODE: "Max",
        },
        blocking=True,
    )

    assert transport_write.call_count == 1
    assert transport_write.call_args == call("1;1;1;1;22;Max\n")

    receive_message("1;1;1;0;22;Max\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == HVACMode.AUTO
    assert state.attributes[ATTR_FAN_MODE] == "Max"

    transport_write.reset_mock()

    # Test set hvac mode off
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )

    assert transport_write.call_count == 1
    assert transport_write.call_args == call("1;1;1;1;21;Off\n")

    receive_message("1;1;1;0;21;Off\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == HVACMode.OFF


async def test_hvac_node_heat(
    hass: HomeAssistant,
    hvac_node_heat: Sensor,
    receive_message: Callable[[str], None],
    transport_write: MagicMock,
) -> None:
    """Test a hvac heat node."""
    entity_id = "climate.hvac_node_1_1"

    state = hass.states.get(entity_id)

    assert state
    assert state.state == HVACMode.OFF

    # Test set hvac mode heat
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )

    assert transport_write.call_count == 1
    assert transport_write.call_args == call("1;1;1;1;21;HeatOn\n")

    receive_message("1;1;1;0;21;HeatOn\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 19.0
    assert state.attributes[ATTR_FAN_MODE] == "Normal"
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 20.0

    transport_write.reset_mock()

    # Test set low/high target temperature
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TEMPERATURE: 20.0,
        },
        blocking=True,
    )

    assert transport_write.call_count == 1
    assert transport_write.call_args == call("1;1;1;1;45;20.0\n")

    receive_message("1;1;1;0;45;20.0\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 20.0
    assert state.attributes[ATTR_FAN_MODE] == "Normal"

    transport_write.reset_mock()

    # Test set fan mode
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_FAN_MODE: "Min",
        },
        blocking=True,
    )

    assert transport_write.call_count == 1
    assert transport_write.call_args == call("1;1;1;1;22;Min\n")

    receive_message("1;1;1;0;22;Min\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_FAN_MODE] == "Min"

    transport_write.reset_mock()

    # Test set hvac mode off
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )

    assert transport_write.call_count == 1
    assert transport_write.call_args == call("1;1;1;1;21;Off\n")

    receive_message("1;1;1;0;21;Off\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == HVACMode.OFF


async def test_hvac_node_cool(
    hass: HomeAssistant,
    hvac_node_cool: Sensor,
    receive_message: Callable[[str], None],
    transport_write: MagicMock,
) -> None:
    """Test a hvac cool node."""
    entity_id = "climate.hvac_node_1_1"

    state = hass.states.get(entity_id)

    assert state
    assert state.state == HVACMode.OFF

    # Test set hvac mode heat
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.COOL},
        blocking=True,
    )

    assert transport_write.call_count == 1
    assert transport_write.call_args == call("1;1;1;1;21;CoolOn\n")

    receive_message("1;1;1;0;21;CoolOn\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == HVACMode.COOL
    assert state.attributes[ATTR_TEMPERATURE] == 21.0
    assert state.attributes[ATTR_FAN_MODE] == "Normal"
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 20.0

    transport_write.reset_mock()

    # Test set low/high target temperature
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TEMPERATURE: 20.0,
        },
        blocking=True,
    )

    assert transport_write.call_count == 1
    assert transport_write.call_args == call("1;1;1;1;44;20.0\n")

    receive_message("1;1;1;0;44;20.0\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == HVACMode.COOL
    assert state.attributes[ATTR_TEMPERATURE] == 20.0
    assert state.attributes[ATTR_FAN_MODE] == "Normal"

    transport_write.reset_mock()

    # Test set fan mode
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_FAN_MODE: "Auto",
        },
        blocking=True,
    )

    assert transport_write.call_count == 1
    assert transport_write.call_args == call("1;1;1;1;22;Auto\n")

    receive_message("1;1;1;0;22;Auto\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == HVACMode.COOL
    assert state.attributes[ATTR_FAN_MODE] == "Auto"

    transport_write.reset_mock()

    # Test set hvac mode off
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )

    assert transport_write.call_count == 1
    assert transport_write.call_args == call("1;1;1;1;21;Off\n")

    receive_message("1;1;1;0;21;Off\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == HVACMode.OFF
