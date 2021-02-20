"""Test the Z-Wave JS climate platform."""
import pytest
from zwave_js_server.event import Event

from homeassistant.components.climate.const import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_PRESET_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    CURRENT_HVAC_IDLE,
    DOMAIN as CLIMATE_DOMAIN,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    PRESET_NONE,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.components.zwave_js.climate import ATTR_FAN_STATE
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE

CLIMATE_RADIO_THERMOSTAT_ENTITY = "climate.z_wave_thermostat"
CLIMATE_DANFOSS_LC13_ENTITY = "climate.living_connect_z_thermostat"
CLIMATE_FLOOR_THERMOSTAT_ENTITY = "climate.floor_thermostat"


async def test_thermostat_v2(
    hass, client, climate_radio_thermostat_ct100_plus, integration
):
    """Test a thermostat v2 command class entity."""
    node = climate_radio_thermostat_ct100_plus
    state = hass.states.get(CLIMATE_RADIO_THERMOSTAT_ENTITY)

    assert state
    assert state.state == HVAC_MODE_HEAT
    assert state.attributes[ATTR_HVAC_MODES] == [
        HVAC_MODE_OFF,
        HVAC_MODE_HEAT,
        HVAC_MODE_COOL,
        HVAC_MODE_HEAT_COOL,
    ]
    assert state.attributes[ATTR_CURRENT_HUMIDITY] == 30
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 22.2
    assert state.attributes[ATTR_TEMPERATURE] == 22.2
    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_IDLE
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_NONE
    assert state.attributes[ATTR_FAN_MODE] == "Auto low"
    assert state.attributes[ATTR_FAN_STATE] == "Idle / off"

    # Test setting preset mode
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {
            ATTR_ENTITY_ID: CLIMATE_RADIO_THERMOSTAT_ENTITY,
            ATTR_PRESET_MODE: PRESET_NONE,
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 13
    assert args["valueId"] == {
        "commandClassName": "Thermostat Mode",
        "commandClass": 64,
        "endpoint": 1,
        "property": "mode",
        "propertyName": "mode",
        "metadata": {
            "type": "number",
            "readable": True,
            "writeable": True,
            "min": 0,
            "max": 31,
            "label": "Thermostat mode",
            "states": {"0": "Off", "1": "Heat", "2": "Cool", "3": "Auto"},
        },
        "value": 1,
    }
    assert args["value"] == 1

    client.async_send_command.reset_mock()

    # Test setting hvac mode
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {
            ATTR_ENTITY_ID: CLIMATE_RADIO_THERMOSTAT_ENTITY,
            ATTR_HVAC_MODE: HVAC_MODE_COOL,
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 13
    assert args["valueId"] == {
        "commandClassName": "Thermostat Mode",
        "commandClass": 64,
        "endpoint": 1,
        "property": "mode",
        "propertyName": "mode",
        "metadata": {
            "type": "number",
            "readable": True,
            "writeable": True,
            "min": 0,
            "max": 31,
            "label": "Thermostat mode",
            "states": {"0": "Off", "1": "Heat", "2": "Cool", "3": "Auto"},
        },
        "value": 1,
    }
    assert args["value"] == 2

    client.async_send_command.reset_mock()

    # Test setting temperature
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: CLIMATE_RADIO_THERMOSTAT_ENTITY,
            ATTR_HVAC_MODE: HVAC_MODE_COOL,
            ATTR_TEMPERATURE: 25,
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 2
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 13
    assert args["valueId"] == {
        "commandClassName": "Thermostat Mode",
        "commandClass": 64,
        "endpoint": 1,
        "property": "mode",
        "propertyName": "mode",
        "metadata": {
            "type": "number",
            "readable": True,
            "writeable": True,
            "min": 0,
            "max": 31,
            "label": "Thermostat mode",
            "states": {"0": "Off", "1": "Heat", "2": "Cool", "3": "Auto"},
        },
        "value": 1,
    }
    assert args["value"] == 2
    args = client.async_send_command.call_args_list[1][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 13
    assert args["valueId"] == {
        "commandClassName": "Thermostat Setpoint",
        "commandClass": 67,
        "endpoint": 1,
        "property": "setpoint",
        "propertyKey": 1,
        "propertyName": "setpoint",
        "propertyKeyName": "Heating",
        "metadata": {
            "type": "number",
            "readable": True,
            "writeable": True,
            "unit": "°F",
            "ccSpecific": {"setpointType": 1},
        },
        "value": 72,
    }
    assert args["value"] == 77

    client.async_send_command.reset_mock()

    # Test cool mode update from value updated event
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 13,
            "args": {
                "commandClassName": "Thermostat Mode",
                "commandClass": 64,
                "endpoint": 1,
                "property": "mode",
                "propertyName": "mode",
                "newValue": 2,
                "prevValue": 1,
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(CLIMATE_RADIO_THERMOSTAT_ENTITY)
    assert state.state == HVAC_MODE_COOL
    assert state.attributes[ATTR_TEMPERATURE] == 22.8

    # Test heat_cool mode update from value updated event
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 13,
            "args": {
                "commandClassName": "Thermostat Mode",
                "commandClass": 64,
                "endpoint": 1,
                "property": "mode",
                "propertyName": "mode",
                "newValue": 3,
                "prevValue": 1,
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(CLIMATE_RADIO_THERMOSTAT_ENTITY)
    assert state.state == HVAC_MODE_HEAT_COOL
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] == 22.8
    assert state.attributes[ATTR_TARGET_TEMP_LOW] == 22.2

    client.async_send_command.reset_mock()

    # Test setting temperature with heat_cool
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: CLIMATE_RADIO_THERMOSTAT_ENTITY,
            ATTR_TARGET_TEMP_HIGH: 30,
            ATTR_TARGET_TEMP_LOW: 25,
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 2
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 13
    assert args["valueId"] == {
        "commandClassName": "Thermostat Setpoint",
        "commandClass": 67,
        "endpoint": 1,
        "property": "setpoint",
        "propertyKey": 1,
        "propertyName": "setpoint",
        "propertyKeyName": "Heating",
        "metadata": {
            "type": "number",
            "readable": True,
            "writeable": True,
            "unit": "°F",
            "ccSpecific": {"setpointType": 1},
        },
        "value": 72,
    }
    assert args["value"] == 77

    args = client.async_send_command.call_args_list[1][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 13
    assert args["valueId"] == {
        "commandClassName": "Thermostat Setpoint",
        "commandClass": 67,
        "endpoint": 1,
        "property": "setpoint",
        "propertyKey": 2,
        "propertyName": "setpoint",
        "propertyKeyName": "Cooling",
        "metadata": {
            "type": "number",
            "readable": True,
            "writeable": True,
            "unit": "°F",
            "ccSpecific": {"setpointType": 2},
        },
        "value": 73,
    }
    assert args["value"] == 86

    client.async_send_command.reset_mock()

    with pytest.raises(ValueError):
        # Test setting unknown preset mode
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {
                ATTR_ENTITY_ID: CLIMATE_RADIO_THERMOSTAT_ENTITY,
                ATTR_PRESET_MODE: "unknown_preset",
            },
            blocking=True,
        )

    assert len(client.async_send_command.call_args_list) == 0

    # Test setting invalid hvac mode
    with pytest.raises(ValueError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: CLIMATE_RADIO_THERMOSTAT_ENTITY,
                ATTR_HVAC_MODE: HVAC_MODE_DRY,
            },
            blocking=True,
        )

    # Test setting invalid preset mode
    with pytest.raises(ValueError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {
                ATTR_ENTITY_ID: CLIMATE_RADIO_THERMOSTAT_ENTITY,
                ATTR_PRESET_MODE: "invalid_mode",
            },
            blocking=True,
        )

    client.async_send_command.reset_mock()

    # Test setting fan mode
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {
            ATTR_ENTITY_ID: CLIMATE_RADIO_THERMOSTAT_ENTITY,
            ATTR_FAN_MODE: "Low",
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 13
    assert args["valueId"] == {
        "endpoint": 1,
        "commandClass": 68,
        "commandClassName": "Thermostat Fan Mode",
        "property": "mode",
        "propertyName": "mode",
        "ccVersion": 0,
        "metadata": {
            "type": "number",
            "readable": True,
            "writeable": True,
            "min": 0,
            "max": 255,
            "states": {"0": "Auto low", "1": "Low"},
            "label": "Thermostat fan mode",
        },
        "value": 0,
    }
    assert args["value"] == 1

    client.async_send_command.reset_mock()

    # Test setting invalid fan mode
    with pytest.raises(ValueError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {
                ATTR_ENTITY_ID: CLIMATE_RADIO_THERMOSTAT_ENTITY,
                ATTR_FAN_MODE: "fake value",
            },
            blocking=True,
        )


async def test_thermostat_different_endpoints(
    hass, client, climate_radio_thermostat_ct100_plus_different_endpoints, integration
):
    """Test an entity with values on a different endpoint from the primary value."""
    state = hass.states.get(CLIMATE_RADIO_THERMOSTAT_ENTITY)

    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 22.5


async def test_setpoint_thermostat(hass, client, climate_danfoss_lc_13, integration):
    """Test a setpoint thermostat command class entity."""
    node = climate_danfoss_lc_13
    state = hass.states.get(CLIMATE_DANFOSS_LC13_ENTITY)

    assert state
    assert state.state == HVAC_MODE_HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 25
    assert state.attributes[ATTR_HVAC_MODES] == [HVAC_MODE_HEAT]
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_NONE

    client.async_send_command.reset_mock()

    # Test setting temperature
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: CLIMATE_DANFOSS_LC13_ENTITY,
            ATTR_TEMPERATURE: 21.5,
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 5
    assert args["valueId"] == {
        "endpoint": 0,
        "commandClass": 67,
        "commandClassName": "Thermostat Setpoint",
        "property": "setpoint",
        "propertyName": "setpoint",
        "propertyKeyName": "Heating",
        "ccVersion": 2,
        "metadata": {
            "type": "number",
            "readable": True,
            "writeable": True,
            "unit": "\u00b0C",
            "ccSpecific": {"setpointType": 1},
        },
        "value": 25,
    }
    assert args["value"] == 21.5

    client.async_send_command.reset_mock()

    # Test setpoint mode update from value updated event
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 5,
            "args": {
                "commandClassName": "Thermostat Setpoint",
                "commandClass": 67,
                "endpoint": 0,
                "property": "setpoint",
                "propertyKeyName": "Heating",
                "propertyName": "setpoint",
                "newValue": 23,
                "prevValue": 21.5,
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(CLIMATE_DANFOSS_LC13_ENTITY)
    assert state.state == HVAC_MODE_HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 23

    client.async_send_command.reset_mock()


async def test_thermostat_heatit(hass, client, climate_heatit_z_trm3, integration):
    """Test a thermostat v2 command class entity."""
    state = hass.states.get(CLIMATE_FLOOR_THERMOSTAT_ENTITY)

    assert state
    assert state.state == HVAC_MODE_HEAT
    assert state.attributes[ATTR_HVAC_MODES] == [
        HVAC_MODE_OFF,
        HVAC_MODE_HEAT,
    ]
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 22.9
    assert state.attributes[ATTR_TEMPERATURE] == 22.5
    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_IDLE
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_NONE
