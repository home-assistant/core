"""Test the Z-Wave JS climate platform."""
import pytest
from zwave_js_server.const import CommandClass
from zwave_js_server.const.command_class.humidity_control import HumidityControlMode
from zwave_js_server.event import Event

from homeassistant.components.humidifier import HumidifierDeviceClass
from homeassistant.components.humidifier.const import (
    ATTR_AVAILABLE_MODES,
    ATTR_HUMIDITY,
    ATTR_MAX_HUMIDITY,
    ATTR_MIN_HUMIDITY,
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MIN_HUMIDITY,
    DOMAIN as HUMIDIFIER_DOMAIN,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_MODE,
    SUPPORT_MODES,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_MODE,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)

from .common import HUMIDIFIER_ADC_T3000_ENTITY


async def test_humidifier(hass, client, climate_adc_t3000, integration):
    """Test a thermostat v2 command class entity."""

    node = climate_adc_t3000
    state = hass.states.get(HUMIDIFIER_ADC_T3000_ENTITY)

    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_AVAILABLE_MODES] == [
        "Off",
        "Humidify",
        "De-humidify",
        "Auto",
    ]
    assert state.attributes[ATTR_DEVICE_CLASS] == HumidifierDeviceClass.HUMIDIFIER
    assert state.attributes[ATTR_MODE] == "Auto"
    assert state.attributes[ATTR_HUMIDITY] == 35
    assert state.attributes[ATTR_MIN_HUMIDITY] == 10
    assert state.attributes[ATTR_MAX_HUMIDITY] == 70
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == SUPPORT_MODES

    client.async_send_command.reset_mock()

    # Test setting mode
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_MODE,
        {
            ATTR_ENTITY_ID: HUMIDIFIER_ADC_T3000_ENTITY,
            ATTR_MODE: "Humidify",
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 68
    assert args["valueId"] == {
        "ccVersion": 2,
        "commandClassName": "Humidity Control Mode",
        "commandClass": CommandClass.HUMIDITY_CONTROL_MODE,
        "endpoint": 0,
        "property": "mode",
        "propertyName": "mode",
        "metadata": {
            "type": "number",
            "readable": True,
            "writeable": True,
            "min": 0,
            "max": 255,
            "label": "Humidity control mode",
            "states": {"0": "Off", "1": "Humidify", "2": "De-humidify", "3": "Auto"},
        },
        "value": int(HumidityControlMode.AUTO),
    }
    assert args["value"] == int(HumidityControlMode.HUMIDIFY)

    client.async_send_command.reset_mock()

    # Test setting humidity
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_HUMIDITY,
        {
            ATTR_ENTITY_ID: HUMIDIFIER_ADC_T3000_ENTITY,
            ATTR_HUMIDITY: 41,
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 68
    assert args["valueId"] == {
        "ccVersion": 1,
        "commandClassName": "Humidity Control Setpoint",
        "commandClass": CommandClass.HUMIDITY_CONTROL_SETPOINT,
        "endpoint": 0,
        "property": "setpoint",
        "propertyKey": 1,
        "propertyName": "setpoint",
        "propertyKeyName": "Humidifier",
        "metadata": {
            "type": "number",
            "readable": True,
            "writeable": True,
            "unit": "%",
            "min": 10,
            "max": 70,
            "ccSpecific": {"setpointType": 1},
        },
        "value": 35,
    }
    assert args["value"] == 41

    client.async_send_command.reset_mock()

    # Test de-humidify mode update from value updated event
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 68,
            "args": {
                "commandClassName": "Humidity Control Mode",
                "commandClass": CommandClass.HUMIDITY_CONTROL_MODE,
                "endpoint": 0,
                "property": "mode",
                "propertyName": "mode",
                "newValue": int(HumidityControlMode.DEHUMIDIFY),
                "prevValue": int(HumidityControlMode.HUMIDIFY),
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(HUMIDIFIER_ADC_T3000_ENTITY)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_HUMIDITY] == 60

    client.async_send_command.reset_mock()

    client.async_send_command.reset_mock()

    # Test off mode update from value updated event
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 68,
            "args": {
                "commandClassName": "Humidity Control Mode",
                "commandClass": CommandClass.HUMIDITY_CONTROL_MODE,
                "endpoint": 0,
                "property": "mode",
                "propertyName": "mode",
                "newValue": int(HumidityControlMode.OFF),
                "prevValue": int(HumidityControlMode.HUMIDIFY),
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(HUMIDIFIER_ADC_T3000_ENTITY)
    assert state.state == STATE_OFF
    assert ATTR_HUMIDITY not in state.attributes
    assert state.attributes[ATTR_MIN_HUMIDITY] == DEFAULT_MIN_HUMIDITY
    assert state.attributes[ATTR_MAX_HUMIDITY] == DEFAULT_MAX_HUMIDITY

    client.async_send_command.reset_mock()

    # Test turning off
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: HUMIDIFIER_ADC_T3000_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 68
    assert args["valueId"] == {
        "ccVersion": 2,
        "commandClassName": "Humidity Control Mode",
        "commandClass": CommandClass.HUMIDITY_CONTROL_MODE,
        "endpoint": 0,
        "property": "mode",
        "propertyName": "mode",
        "metadata": {
            "type": "number",
            "readable": True,
            "writeable": True,
            "min": 0,
            "max": 255,
            "label": "Humidity control mode",
            "states": {"0": "Off", "1": "Humidify", "2": "De-humidify", "3": "Auto"},
        },
        "value": int(HumidityControlMode.OFF),
    }
    assert args["value"] == int(HumidityControlMode.OFF)

    client.async_send_command.reset_mock()

    # Test turning on
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: HUMIDIFIER_ADC_T3000_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 68
    assert args["valueId"] == {
        "ccVersion": 2,
        "commandClassName": "Humidity Control Mode",
        "commandClass": CommandClass.HUMIDITY_CONTROL_MODE,
        "endpoint": 0,
        "property": "mode",
        "propertyName": "mode",
        "metadata": {
            "type": "number",
            "readable": True,
            "writeable": True,
            "min": 0,
            "max": 255,
            "label": "Humidity control mode",
            "states": {"0": "Off", "1": "Humidify", "2": "De-humidify", "3": "Auto"},
        },
        "value": int(HumidityControlMode.OFF),
    }
    assert args["value"] == int(HumidityControlMode.AUTO)

    client.async_send_command.reset_mock()

    # Test setting invalid mode
    with pytest.raises(ValueError):
        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            SERVICE_SET_MODE,
            {
                ATTR_ENTITY_ID: HUMIDIFIER_ADC_T3000_ENTITY,
                ATTR_MODE: "fake value",
            },
            blocking=True,
        )
