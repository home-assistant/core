"""Test the Z-Wave JS humidifier platform."""

from zwave_js_server.const import CommandClass
from zwave_js_server.const.command_class.humidity_control import HumidityControlMode
from zwave_js_server.event import Event

from homeassistant.components.humidifier import (
    ATTR_HUMIDITY,
    ATTR_MAX_HUMIDITY,
    ATTR_MIN_HUMIDITY,
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MIN_HUMIDITY,
    DOMAIN as HUMIDIFIER_DOMAIN,
    SERVICE_SET_HUMIDITY,
    HumidifierDeviceClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant

from .common import DEHUMIDIFIER_ADC_T3000_ENTITY, HUMIDIFIER_ADC_T3000_ENTITY


async def test_humidifier(
    hass: HomeAssistant, client, climate_adc_t3000, integration
) -> None:
    """Test a humidity control command class entity."""

    node = climate_adc_t3000
    state = hass.states.get(HUMIDIFIER_ADC_T3000_ENTITY)

    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_DEVICE_CLASS] == HumidifierDeviceClass.HUMIDIFIER
    assert state.attributes[ATTR_HUMIDITY] == 35
    assert state.attributes[ATTR_MIN_HUMIDITY] == 10
    assert state.attributes[ATTR_MAX_HUMIDITY] == 70

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
        "commandClass": CommandClass.HUMIDITY_CONTROL_SETPOINT,
        "endpoint": 0,
        "property": "setpoint",
        "propertyKey": 1,
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
    assert state.state == STATE_OFF

    client.async_send_command.reset_mock()

    # Test auto mode update from value updated event
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
                "newValue": int(HumidityControlMode.AUTO),
                "prevValue": int(HumidityControlMode.HUMIDIFY),
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(HUMIDIFIER_ADC_T3000_ENTITY)
    assert state.state == STATE_ON

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

    client.async_send_command.reset_mock()

    # Test turning off when device is previously humidifying
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
                "newValue": int(HumidityControlMode.HUMIDIFY),
                "prevValue": int(HumidityControlMode.OFF),
            },
        },
    )
    node.receive_event(event)

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
        "commandClass": CommandClass.HUMIDITY_CONTROL_MODE,
        "endpoint": 0,
        "property": "mode",
    }
    assert args["value"] == int(HumidityControlMode.OFF)

    client.async_send_command.reset_mock()

    # Test turning off when device is previously auto
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
                "newValue": int(HumidityControlMode.AUTO),
                "prevValue": int(HumidityControlMode.OFF),
            },
        },
    )
    node.receive_event(event)

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
        "commandClass": CommandClass.HUMIDITY_CONTROL_MODE,
        "endpoint": 0,
        "property": "mode",
    }
    assert args["value"] == int(HumidityControlMode.DEHUMIDIFY)

    client.async_send_command.reset_mock()

    # Test turning off when device is previously de-humidifying
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
                "prevValue": int(HumidityControlMode.OFF),
            },
        },
    )
    node.receive_event(event)

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: HUMIDIFIER_ADC_T3000_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 0

    client.async_send_command.reset_mock()

    # Test turning off when device is previously off
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
                "prevValue": int(HumidityControlMode.AUTO),
            },
        },
    )
    node.receive_event(event)

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: HUMIDIFIER_ADC_T3000_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 0

    client.async_send_command.reset_mock()

    # Test turning on when device is previously humidifying
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
                "newValue": int(HumidityControlMode.HUMIDIFY),
                "prevValue": int(HumidityControlMode.OFF),
            },
        },
    )
    node.receive_event(event)

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: HUMIDIFIER_ADC_T3000_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 0

    client.async_send_command.reset_mock()

    # Test turning on when device is previously auto
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
                "newValue": int(HumidityControlMode.AUTO),
                "prevValue": int(HumidityControlMode.OFF),
            },
        },
    )
    node.receive_event(event)

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: HUMIDIFIER_ADC_T3000_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 0

    client.async_send_command.reset_mock()

    # Test turning on when device is previously de-humidifying
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
                "prevValue": int(HumidityControlMode.OFF),
            },
        },
    )
    node.receive_event(event)

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
        "commandClass": CommandClass.HUMIDITY_CONTROL_MODE,
        "endpoint": 0,
        "property": "mode",
    }
    assert args["value"] == int(HumidityControlMode.AUTO)

    client.async_send_command.reset_mock()

    # Test turning on when device is previously off
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
                "prevValue": int(HumidityControlMode.AUTO),
            },
        },
    )
    node.receive_event(event)

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
        "commandClass": CommandClass.HUMIDITY_CONTROL_MODE,
        "endpoint": 0,
        "property": "mode",
    }
    assert args["value"] == int(HumidityControlMode.HUMIDIFY)


async def test_dehumidifier_missing_setpoint(
    hass: HomeAssistant, client, climate_adc_t3000_missing_setpoint, integration
) -> None:
    """Test a humidity control command class entity."""

    entity_id = "humidifier.adc_t3000_missing_setpoint_dehumidifier"
    state = hass.states.get(entity_id)

    assert state
    assert ATTR_HUMIDITY not in state.attributes
    assert state.attributes[ATTR_MIN_HUMIDITY] == DEFAULT_MIN_HUMIDITY
    assert state.attributes[ATTR_MAX_HUMIDITY] == DEFAULT_MAX_HUMIDITY

    client.async_send_command.reset_mock()

    # Test setting humidity
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_HUMIDITY,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_HUMIDITY: 41,
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 0

    client.async_send_command.reset_mock()


async def test_humidifier_missing_mode(
    hass: HomeAssistant, client, climate_adc_t3000_missing_mode, integration
) -> None:
    """Test a humidity control command class entity."""

    node = climate_adc_t3000_missing_mode

    # Test that de-humidifer entity does not exist but humidifier entity does
    entity_id = "humidifier.adc_t3000_missing_mode_dehumidifier"
    state = hass.states.get(entity_id)
    assert not state

    entity_id = "humidifier.adc_t3000_missing_mode_humidifier"
    state = hass.states.get(entity_id)
    assert state

    client.async_send_command.reset_mock()

    # Test turning off when device is previously auto for a device which does not have de-humidify mode
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
                "newValue": int(HumidityControlMode.AUTO),
                "prevValue": int(HumidityControlMode.OFF),
            },
        },
    )
    node.receive_event(event)

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 68
    assert args["valueId"] == {
        "commandClass": CommandClass.HUMIDITY_CONTROL_MODE,
        "endpoint": 0,
        "property": "mode",
    }
    assert args["value"] == int(HumidityControlMode.OFF)

    client.async_send_command.reset_mock()


async def test_dehumidifier(
    hass: HomeAssistant, client, climate_adc_t3000, integration
) -> None:
    """Test a humidity control command class entity."""

    node = climate_adc_t3000
    state = hass.states.get(DEHUMIDIFIER_ADC_T3000_ENTITY)

    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_DEVICE_CLASS] == HumidifierDeviceClass.DEHUMIDIFIER
    assert state.attributes[ATTR_HUMIDITY] == 60
    assert state.attributes[ATTR_MIN_HUMIDITY] == 30
    assert state.attributes[ATTR_MAX_HUMIDITY] == 90

    client.async_send_command.reset_mock()

    # Test setting humidity
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_HUMIDITY,
        {
            ATTR_ENTITY_ID: DEHUMIDIFIER_ADC_T3000_ENTITY,
            ATTR_HUMIDITY: 41,
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 68
    assert args["valueId"] == {
        "commandClass": CommandClass.HUMIDITY_CONTROL_SETPOINT,
        "endpoint": 0,
        "property": "setpoint",
        "propertyKey": 2,
    }
    assert args["value"] == 41

    client.async_send_command.reset_mock()

    # Test humidify mode update from value updated event
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
                "newValue": int(HumidityControlMode.HUMIDIFY),
                "prevValue": int(HumidityControlMode.DEHUMIDIFY),
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(DEHUMIDIFIER_ADC_T3000_ENTITY)
    assert state.state == STATE_OFF

    client.async_send_command.reset_mock()

    # Test auto mode update from value updated event
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
                "newValue": int(HumidityControlMode.AUTO),
                "prevValue": int(HumidityControlMode.DEHUMIDIFY),
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(DEHUMIDIFIER_ADC_T3000_ENTITY)
    assert state.state == STATE_ON

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
                "prevValue": int(HumidityControlMode.DEHUMIDIFY),
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(DEHUMIDIFIER_ADC_T3000_ENTITY)
    assert state.state == STATE_OFF

    client.async_send_command.reset_mock()

    # Test turning off when device is previously de-humidifying
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
                "prevValue": int(HumidityControlMode.OFF),
            },
        },
    )
    node.receive_event(event)

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: DEHUMIDIFIER_ADC_T3000_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 68
    assert args["valueId"] == {
        "commandClass": CommandClass.HUMIDITY_CONTROL_MODE,
        "endpoint": 0,
        "property": "mode",
    }
    assert args["value"] == int(HumidityControlMode.OFF)

    client.async_send_command.reset_mock()

    # Test turning off when device is previously auto
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
                "newValue": int(HumidityControlMode.AUTO),
                "prevValue": int(HumidityControlMode.OFF),
            },
        },
    )
    node.receive_event(event)

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: DEHUMIDIFIER_ADC_T3000_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 68
    assert args["valueId"] == {
        "commandClass": CommandClass.HUMIDITY_CONTROL_MODE,
        "endpoint": 0,
        "property": "mode",
    }
    assert args["value"] == int(HumidityControlMode.HUMIDIFY)

    client.async_send_command.reset_mock()

    # Test turning off when device is previously humidifying
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
                "newValue": int(HumidityControlMode.HUMIDIFY),
                "prevValue": int(HumidityControlMode.OFF),
            },
        },
    )
    node.receive_event(event)

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: DEHUMIDIFIER_ADC_T3000_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 0

    client.async_send_command.reset_mock()

    # Test turning off when device is previously off
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
                "prevValue": int(HumidityControlMode.AUTO),
            },
        },
    )
    node.receive_event(event)

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: DEHUMIDIFIER_ADC_T3000_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 0

    client.async_send_command.reset_mock()

    # Test turning on when device is previously de-humidifying
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
                "prevValue": int(HumidityControlMode.OFF),
            },
        },
    )
    node.receive_event(event)

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: DEHUMIDIFIER_ADC_T3000_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 0

    client.async_send_command.reset_mock()

    # Test turning on when device is previously auto
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
                "newValue": int(HumidityControlMode.AUTO),
                "prevValue": int(HumidityControlMode.OFF),
            },
        },
    )
    node.receive_event(event)

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: DEHUMIDIFIER_ADC_T3000_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 0

    client.async_send_command.reset_mock()

    # Test turning on when device is previously humidifying
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
                "newValue": int(HumidityControlMode.HUMIDIFY),
                "prevValue": int(HumidityControlMode.OFF),
            },
        },
    )
    node.receive_event(event)

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: DEHUMIDIFIER_ADC_T3000_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 68
    assert args["valueId"] == {
        "commandClass": CommandClass.HUMIDITY_CONTROL_MODE,
        "endpoint": 0,
        "property": "mode",
    }
    assert args["value"] == int(HumidityControlMode.AUTO)

    client.async_send_command.reset_mock()

    # Test turning on when device is previously off
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
                "prevValue": int(HumidityControlMode.AUTO),
            },
        },
    )
    node.receive_event(event)

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: DEHUMIDIFIER_ADC_T3000_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 68
    assert args["valueId"] == {
        "commandClass": CommandClass.HUMIDITY_CONTROL_MODE,
        "endpoint": 0,
        "property": "mode",
    }
    assert args["value"] == int(HumidityControlMode.DEHUMIDIFY)

    # Test setting value to None
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
                "newValue": None,
                "prevValue": int(HumidityControlMode.OFF),
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(HUMIDIFIER_ADC_T3000_ENTITY)

    assert state
    assert state.state == STATE_UNKNOWN

    client.async_send_command.reset_mock()

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: HUMIDIFIER_ADC_T3000_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 0
