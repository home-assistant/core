"""Test the Z-Wave JS light platform."""

from copy import deepcopy

from zwave_js_server.event import Event

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_MAX_COLOR_TEMP_KELVIN,
    ATTR_MIN_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    ATTR_TRANSITION,
    DOMAIN as LIGHT_DOMAIN,
    LightEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import (
    AEON_SMART_SWITCH_LIGHT_ENTITY,
    BASIC_LIGHT_ENTITY,
    BULB_6_MULTI_COLOR_LIGHT_ENTITY,
    EATON_RF9640_ENTITY,
    ZEN_31_ENTITY,
)

ZDB5100_ENTITY = "light.matrix_office"
HSM200_V1_ENTITY = "light.hsm200"


async def test_light(
    hass: HomeAssistant, client, bulb_6_multi_color, integration
) -> None:
    """Test the light entity."""
    node = bulb_6_multi_color
    state = hass.states.get(BULB_6_MULTI_COLOR_LIGHT_ENTITY)

    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_MAX_COLOR_TEMP_KELVIN] == 6500
    assert state.attributes[ATTR_MIN_COLOR_TEMP_KELVIN] == 2700
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == LightEntityFeature.TRANSITION
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == ["color_temp", "hs"]

    # Test turning on
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": BULB_6_MULTI_COLOR_LIGHT_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 39
    assert args["valueId"] == {
        "commandClass": 38,
        "endpoint": 0,
        "property": "targetValue",
    }
    assert args["value"] == 255

    # Due to optimistic updates, the state should be on even though the Z-Wave state
    # hasn't been updated yet
    state = hass.states.get(BULB_6_MULTI_COLOR_LIGHT_ENTITY)

    assert state
    assert state.state == STATE_ON

    client.async_send_command.reset_mock()

    # Test turning on with transition
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": BULB_6_MULTI_COLOR_LIGHT_ENTITY, ATTR_TRANSITION: 10},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 39
    assert args["valueId"] == {
        "commandClass": 38,
        "endpoint": 0,
        "property": "targetValue",
    }
    assert args["value"] == 255
    assert args["options"]["transitionDuration"] == "10s"

    client.async_send_command.reset_mock()

    # Test brightness update from value updated event
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 39,
            "args": {
                "commandClassName": "Multilevel Switch",
                "commandClass": 38,
                "endpoint": 0,
                "property": "currentValue",
                "newValue": 99,
                "prevValue": 0,
                "propertyName": "currentValue",
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(BULB_6_MULTI_COLOR_LIGHT_ENTITY)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_COLOR_MODE] == "color_temp"
    assert state.attributes[ATTR_BRIGHTNESS] == 255
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == 2702
    assert state.attributes[ATTR_RGB_COLOR] is not None

    # Test turning on with same brightness
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": BULB_6_MULTI_COLOR_LIGHT_ENTITY, ATTR_BRIGHTNESS: 255},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1

    client.async_send_command.reset_mock()

    # Test turning on with brightness
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": BULB_6_MULTI_COLOR_LIGHT_ENTITY, ATTR_BRIGHTNESS: 129},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 39
    assert args["valueId"] == {
        "commandClass": 38,
        "endpoint": 0,
        "property": "targetValue",
    }
    assert args["value"] == 50
    assert args["options"]["transitionDuration"] == "default"

    client.async_send_command.reset_mock()

    # Test turning on with brightness and transition
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": BULB_6_MULTI_COLOR_LIGHT_ENTITY,
            ATTR_BRIGHTNESS: 129,
            ATTR_TRANSITION: 20,
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 39
    assert args["valueId"] == {
        "commandClass": 38,
        "endpoint": 0,
        "property": "targetValue",
    }
    assert args["value"] == 50
    assert args["options"]["transitionDuration"] == "20s"

    client.async_send_command.reset_mock()

    # Test turning on with rgb color
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": BULB_6_MULTI_COLOR_LIGHT_ENTITY, ATTR_RGB_COLOR: (255, 76, 255)},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 2
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 39
    assert args["valueId"]["commandClass"] == 51
    assert args["valueId"]["endpoint"] == 0
    assert args["valueId"]["property"] == "targetColor"
    assert args["value"] == {
        "blue": 255,
        "coldWhite": 0,
        "green": 76,
        "red": 255,
        "warmWhite": 0,
    }

    # Test rgb color update from value updated event
    red_event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 39,
            "args": {
                "commandClassName": "Color Switch",
                "commandClass": 51,
                "endpoint": 0,
                "property": "currentColor",
                "newValue": 255,
                "prevValue": 0,
                "propertyKey": 2,
                "propertyKeyName": "Red",
            },
        },
    )
    green_event = deepcopy(red_event)
    green_event.data["args"].update(
        {"newValue": 76, "propertyKey": 3, "propertyKeyName": "Green"}
    )
    blue_event = deepcopy(red_event)
    blue_event.data["args"]["propertyKey"] = 4
    blue_event.data["args"]["propertyKeyName"] = "Blue"
    warm_white_event = deepcopy(red_event)
    warm_white_event.data["args"].update(
        {"newValue": 0, "propertyKey": 0, "propertyKeyName": "Warm White"}
    )
    node.receive_event(warm_white_event)
    node.receive_event(red_event)
    node.receive_event(green_event)
    node.receive_event(blue_event)

    state = hass.states.get(BULB_6_MULTI_COLOR_LIGHT_ENTITY)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_COLOR_MODE] == "hs"
    assert state.attributes[ATTR_BRIGHTNESS] == 255
    assert state.attributes[ATTR_RGB_COLOR] == (255, 76, 255)
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] is None

    client.async_send_command.reset_mock()

    # Test turning on with same rgb color
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": BULB_6_MULTI_COLOR_LIGHT_ENTITY, ATTR_RGB_COLOR: (255, 76, 255)},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 2

    client.async_send_command.reset_mock()

    # Test turning on with rgb color and transition
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": BULB_6_MULTI_COLOR_LIGHT_ENTITY,
            ATTR_RGB_COLOR: (128, 76, 255),
            ATTR_TRANSITION: 20,
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 2
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["options"]["transitionDuration"] == "20s"
    client.async_send_command.reset_mock()

    # Test turning on with color temp
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": BULB_6_MULTI_COLOR_LIGHT_ENTITY, ATTR_COLOR_TEMP_KELVIN: 5881},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 2
    args = client.async_send_command.call_args_list[0][0][0]  # red 0
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 39
    assert args["valueId"]["commandClass"] == 51
    assert args["valueId"]["endpoint"] == 0
    assert args["valueId"]["property"] == "targetColor"
    assert args["value"] == {
        "blue": 0,
        "coldWhite": 235,
        "green": 0,
        "red": 0,
        "warmWhite": 20,
    }

    client.async_send_command.reset_mock()

    # Test color temp update from value updated event
    red_event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 39,
            "args": {
                "commandClassName": "Color Switch",
                "commandClass": 51,
                "endpoint": 0,
                "property": "currentColor",
                "newValue": 0,
                "prevValue": 255,
                "propertyKey": 2,
                "propertyKeyName": "Red",
            },
        },
    )
    green_event = deepcopy(red_event)
    green_event.data["args"].update(
        {"newValue": 0, "prevValue": 76, "propertyKey": 3, "propertyKeyName": "Green"}
    )
    blue_event = deepcopy(red_event)
    blue_event.data["args"]["propertyKey"] = 4
    blue_event.data["args"]["propertyKeyName"] = "Blue"
    warm_white_event = deepcopy(red_event)
    warm_white_event.data["args"].update(
        {"newValue": 20, "propertyKey": 0, "propertyKeyName": "Warm White"}
    )
    cold_white_event = deepcopy(red_event)
    cold_white_event.data["args"].update(
        {"newValue": 235, "propertyKey": 1, "propertyKeyName": "Cold White"}
    )
    node.receive_event(red_event)
    node.receive_event(green_event)
    node.receive_event(blue_event)
    node.receive_event(warm_white_event)
    node.receive_event(cold_white_event)

    state = hass.states.get(BULB_6_MULTI_COLOR_LIGHT_ENTITY)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_COLOR_MODE] == "color_temp"
    assert state.attributes[ATTR_BRIGHTNESS] == 255
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == 5881
    assert ATTR_RGB_COLOR in state.attributes

    # Test turning on with same color temp
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": BULB_6_MULTI_COLOR_LIGHT_ENTITY, ATTR_COLOR_TEMP_KELVIN: 5881},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 2

    client.async_send_command.reset_mock()

    # Test turning on with color temp and transition
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": BULB_6_MULTI_COLOR_LIGHT_ENTITY,
            ATTR_COLOR_TEMP_KELVIN: 5881,
            ATTR_TRANSITION: 35,
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 2
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["options"]["transitionDuration"] == "35s"

    client.async_send_command.reset_mock()

    # Test turning off
    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": BULB_6_MULTI_COLOR_LIGHT_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 39
    assert args["valueId"] == {
        "commandClass": 38,
        "endpoint": 0,
        "property": "targetValue",
    }
    assert args["value"] == 0

    client.async_send_command.reset_mock()

    # Test brightness update to None from value updated event
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 39,
            "args": {
                "commandClassName": "Multilevel Switch",
                "commandClass": 38,
                "endpoint": 0,
                "property": "currentValue",
                "newValue": None,
                "prevValue": 99,
                "propertyName": "currentValue",
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(BULB_6_MULTI_COLOR_LIGHT_ENTITY)
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_COLOR_MODE] is None
    assert state.attributes[ATTR_BRIGHTNESS] is None


async def test_v4_dimmer_light(
    hass: HomeAssistant, client, eaton_rf9640_dimmer, integration
) -> None:
    """Test a light that supports MultiLevelSwitch CommandClass version 4."""
    state = hass.states.get(EATON_RF9640_ENTITY)

    assert state
    assert state.state == STATE_ON
    # the light should pick currentvalue which has zwave value 22
    assert state.attributes[ATTR_BRIGHTNESS] == 57


async def test_optional_light(
    hass: HomeAssistant, client, aeon_smart_switch_6, integration
) -> None:
    """Test a device that has an additional light endpoint being identified as light."""
    state = hass.states.get(AEON_SMART_SWITCH_LIGHT_ENTITY)
    assert state.state == STATE_ON


async def test_rgbw_light(hass: HomeAssistant, client, zen_31, integration) -> None:
    """Test the light entity."""
    state = hass.states.get(ZEN_31_ENTITY)

    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == LightEntityFeature.TRANSITION

    # Test turning on
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": ZEN_31_ENTITY, ATTR_RGBW_COLOR: (0, 0, 0, 128)},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 2
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 94
    assert args["valueId"] == {
        "commandClass": 51,
        "endpoint": 1,
        "property": "targetColor",
    }
    assert args["value"] == {"blue": 0, "green": 0, "red": 0, "warmWhite": 128}

    args = client.async_send_command.call_args_list[1][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 94
    assert args["valueId"] == {
        "commandClass": 38,
        "endpoint": 1,
        "property": "targetValue",
    }
    assert args["value"] == 255

    client.async_send_command.reset_mock()


async def test_light_none_color_value(
    hass: HomeAssistant, light_color_null_values, integration
) -> None:
    """Test the light entity can handle None value in current color Value."""
    entity_id = "light.repeater"
    state = hass.states.get(entity_id)

    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == LightEntityFeature.TRANSITION
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == ["hs"]


async def test_light_on_off_color(
    hass: HomeAssistant, client, logic_group_zdb5100, integration
) -> None:
    """Test the light entity for RGB lights without dimming support."""
    node = logic_group_zdb5100
    state = hass.states.get(ZDB5100_ENTITY)
    assert state.state == STATE_OFF

    async def update_color(red: int, green: int, blue: int) -> None:
        event = Event(
            type="value updated",
            data={
                "source": "node",
                "event": "value updated",
                "nodeId": node.node_id,
                "args": {
                    "commandClassName": "Color Switch",
                    "commandClass": 51,
                    "endpoint": 1,
                    "property": "currentColor",
                    "propertyKey": 2,  # red
                    "newValue": red,
                    "prevValue": None,
                    "propertyName": "currentColor",
                    "propertyKeyName": "red",
                },
            },
        )
        node.receive_event(event)
        await hass.async_block_till_done()

        event = Event(
            type="value updated",
            data={
                "source": "node",
                "event": "value updated",
                "nodeId": node.node_id,
                "args": {
                    "commandClassName": "Color Switch",
                    "commandClass": 51,
                    "endpoint": 1,
                    "property": "currentColor",
                    "propertyKey": 3,  # green
                    "newValue": green,
                    "prevValue": None,
                    "propertyName": "currentColor",
                    "propertyKeyName": "green",
                },
            },
        )
        node.receive_event(event)
        await hass.async_block_till_done()

        event = Event(
            type="value updated",
            data={
                "source": "node",
                "event": "value updated",
                "nodeId": node.node_id,
                "args": {
                    "commandClassName": "Color Switch",
                    "commandClass": 51,
                    "endpoint": 1,
                    "property": "currentColor",
                    "propertyKey": 4,  # blue
                    "newValue": blue,
                    "prevValue": None,
                    "propertyName": "currentColor",
                    "propertyKeyName": "blue",
                },
            },
        )
        node.receive_event(event)
        await hass.async_block_till_done()

        event = Event(
            type="value updated",
            data={
                "source": "node",
                "event": "value updated",
                "nodeId": node.node_id,
                "args": {
                    "commandClassName": "Color Switch",
                    "commandClass": 51,
                    "endpoint": 1,
                    "property": "currentColor",
                    "newValue": {
                        "red": red,
                        "green": green,
                        "blue": blue,
                    },
                    "prevValue": None,
                    "propertyName": "currentColor",
                },
            },
        )
        node.receive_event(event)
        await hass.async_block_till_done()

    async def update_switch_state(state: bool) -> None:
        event = Event(
            type="value updated",
            data={
                "source": "node",
                "event": "value updated",
                "nodeId": node.node_id,
                "args": {
                    "commandClassName": "Binary Switch",
                    "commandClass": 37,
                    "endpoint": 1,
                    "property": "currentValue",
                    "newValue": state,
                    "prevValue": None,
                    "propertyName": "currentValue",
                },
            },
        )
        node.receive_event(event)
        await hass.async_block_till_done()

    # Turn on the light. Since this is the first call, the light should default to white
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ZDB5100_ENTITY},
        blocking=True,
    )
    assert len(client.async_send_command.call_args_list) == 2
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == node.node_id
    assert args["valueId"] == {
        "commandClass": 51,
        "endpoint": 1,
        "property": "targetColor",
    }
    assert args["value"] == {
        "red": 255,
        "green": 255,
        "blue": 255,
    }

    args = client.async_send_command.call_args_list[1][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == node.node_id
    assert args["valueId"] == {
        "commandClass": 37,
        "endpoint": 1,
        "property": "targetValue",
    }
    assert args["value"] is True

    # Force the light to turn off
    await update_switch_state(False)

    state = hass.states.get(ZDB5100_ENTITY)
    assert state.state == STATE_OFF

    # Force the light to turn on (green)
    await update_color(0, 255, 0)
    await update_switch_state(True)

    state = hass.states.get(ZDB5100_ENTITY)
    assert state.state == STATE_ON

    client.async_send_command.reset_mock()

    # Set the brightness to 128. This should be encoded in the color value
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ZDB5100_ENTITY, ATTR_BRIGHTNESS: 128},
        blocking=True,
    )
    assert len(client.async_send_command.call_args_list) == 2
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == node.node_id
    assert args["valueId"] == {
        "commandClass": 51,
        "endpoint": 1,
        "property": "targetColor",
    }
    assert args["value"] == {
        "red": 0,
        "green": 128,
        "blue": 0,
    }

    args = client.async_send_command.call_args_list[1][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == node.node_id
    assert args["valueId"] == {
        "commandClass": 37,
        "endpoint": 1,
        "property": "targetValue",
    }
    assert args["value"] is True

    client.async_send_command.reset_mock()

    # Force the light to turn on (green, 50%)
    await update_color(0, 128, 0)

    # Set the color to red. This should preserve the previous brightness value
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ZDB5100_ENTITY, ATTR_HS_COLOR: (0, 100)},
        blocking=True,
    )
    assert len(client.async_send_command.call_args_list) == 2
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == node.node_id
    assert args["valueId"] == {
        "commandClass": 51,
        "endpoint": 1,
        "property": "targetColor",
    }
    assert args["value"] == {
        "red": 128,
        "green": 0,
        "blue": 0,
    }

    args = client.async_send_command.call_args_list[1][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == node.node_id
    assert args["valueId"] == {
        "commandClass": 37,
        "endpoint": 1,
        "property": "targetValue",
    }
    assert args["value"] is True

    client.async_send_command.reset_mock()

    # Force the light to turn on (red, 50%)
    await update_color(128, 0, 0)

    # Turn the device off. This should only affect the binary switch, not the color
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ZDB5100_ENTITY},
        blocking=True,
    )
    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == node.node_id
    assert args["valueId"] == {
        "commandClass": 37,
        "endpoint": 1,
        "property": "targetValue",
    }
    assert args["value"] is False

    client.async_send_command.reset_mock()

    # Force the light to turn off
    await update_switch_state(False)

    # Turn the device on again. This should only affect the binary switch, not the color
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ZDB5100_ENTITY},
        blocking=True,
    )
    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == node.node_id
    assert args["valueId"] == {
        "commandClass": 37,
        "endpoint": 1,
        "property": "targetValue",
    }
    assert args["value"] is True


async def test_light_color_only(
    hass: HomeAssistant, client, express_controls_ezmultipli, integration
) -> None:
    """Test the light entity for RGB lights with Color Switch CC only."""
    node = express_controls_ezmultipli
    state = hass.states.get(HSM200_V1_ENTITY)
    assert state.state == STATE_ON

    async def update_color(red: int, green: int, blue: int) -> None:
        event = Event(
            type="value updated",
            data={
                "source": "node",
                "event": "value updated",
                "nodeId": node.node_id,
                "args": {
                    "commandClassName": "Color Switch",
                    "commandClass": 51,
                    "endpoint": 0,
                    "property": "currentColor",
                    "propertyKey": 2,  # red
                    "newValue": red,
                    "prevValue": None,
                    "propertyName": "currentColor",
                    "propertyKeyName": "red",
                },
            },
        )
        node.receive_event(event)
        await hass.async_block_till_done()

        event = Event(
            type="value updated",
            data={
                "source": "node",
                "event": "value updated",
                "nodeId": node.node_id,
                "args": {
                    "commandClassName": "Color Switch",
                    "commandClass": 51,
                    "endpoint": 0,
                    "property": "currentColor",
                    "propertyKey": 3,  # green
                    "newValue": green,
                    "prevValue": None,
                    "propertyName": "currentColor",
                    "propertyKeyName": "green",
                },
            },
        )
        node.receive_event(event)
        await hass.async_block_till_done()

        event = Event(
            type="value updated",
            data={
                "source": "node",
                "event": "value updated",
                "nodeId": node.node_id,
                "args": {
                    "commandClassName": "Color Switch",
                    "commandClass": 51,
                    "endpoint": 0,
                    "property": "currentColor",
                    "propertyKey": 4,  # blue
                    "newValue": blue,
                    "prevValue": None,
                    "propertyName": "currentColor",
                    "propertyKeyName": "blue",
                },
            },
        )
        node.receive_event(event)
        await hass.async_block_till_done()

        event = Event(
            type="value updated",
            data={
                "source": "node",
                "event": "value updated",
                "nodeId": node.node_id,
                "args": {
                    "commandClassName": "Color Switch",
                    "commandClass": 51,
                    "endpoint": 0,
                    "property": "currentColor",
                    "newValue": {
                        "red": red,
                        "green": green,
                        "blue": blue,
                    },
                    "prevValue": None,
                    "propertyName": "currentColor",
                },
            },
        )
        node.receive_event(event)
        await hass.async_block_till_done()

    # Attempt to turn on the light and ensure it defaults to white
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: HSM200_V1_ENTITY},
        blocking=True,
    )
    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == node.node_id
    assert args["valueId"] == {
        "commandClass": 51,
        "endpoint": 0,
        "property": "targetColor",
    }
    assert args["value"] == {"red": 255, "green": 255, "blue": 255}

    client.async_send_command.reset_mock()

    # Force the light to turn off
    await update_color(0, 0, 0)

    state = hass.states.get(HSM200_V1_ENTITY)
    assert state.state == STATE_OFF

    # Force the light to turn on (50% green)
    await update_color(0, 128, 0)

    state = hass.states.get(HSM200_V1_ENTITY)
    assert state.state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: HSM200_V1_ENTITY},
        blocking=True,
    )
    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == node.node_id
    assert args["valueId"] == {
        "commandClass": 51,
        "endpoint": 0,
        "property": "targetColor",
    }
    assert args["value"] == {"red": 0, "green": 0, "blue": 0}

    client.async_send_command.reset_mock()

    # Force the light to turn off
    await update_color(0, 0, 0)

    # Assert that the last color is restored
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: HSM200_V1_ENTITY},
        blocking=True,
    )
    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == node.node_id
    assert args["valueId"] == {
        "commandClass": 51,
        "endpoint": 0,
        "property": "targetColor",
    }
    assert args["value"] == {"red": 0, "green": 128, "blue": 0}

    client.async_send_command.reset_mock()

    # Force the light to turn on (50% green)
    await update_color(0, 128, 0)

    state = hass.states.get(HSM200_V1_ENTITY)
    assert state.state == STATE_ON

    client.async_send_command.reset_mock()

    # Assert that the brightness is preserved when changing colors
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: HSM200_V1_ENTITY, ATTR_RGB_COLOR: (255, 0, 0)},
        blocking=True,
    )
    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == node.node_id
    assert args["valueId"] == {
        "commandClass": 51,
        "endpoint": 0,
        "property": "targetColor",
    }
    assert args["value"] == {"red": 128, "green": 0, "blue": 0}

    client.async_send_command.reset_mock()

    # Force the light to turn on (50% red)
    await update_color(128, 0, 0)

    state = hass.states.get(HSM200_V1_ENTITY)
    assert state.state == STATE_ON

    # Assert that the color is preserved when changing brightness
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: HSM200_V1_ENTITY, ATTR_BRIGHTNESS: 69},
        blocking=True,
    )
    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == node.node_id
    assert args["valueId"] == {
        "commandClass": 51,
        "endpoint": 0,
        "property": "targetColor",
    }
    assert args["value"] == {"red": 69, "green": 0, "blue": 0}

    client.async_send_command.reset_mock()

    await update_color(69, 0, 0)

    # Turn off again
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: HSM200_V1_ENTITY},
        blocking=True,
    )
    await update_color(0, 0, 0)

    client.async_send_command.reset_mock()

    # Assert that the color is preserved when turning on with brightness
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: HSM200_V1_ENTITY, ATTR_BRIGHTNESS: 123},
        blocking=True,
    )
    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == node.node_id
    assert args["valueId"] == {
        "commandClass": 51,
        "endpoint": 0,
        "property": "targetColor",
    }
    assert args["value"] == {"red": 123, "green": 0, "blue": 0}

    client.async_send_command.reset_mock()

    await update_color(123, 0, 0)

    # Turn off again
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: HSM200_V1_ENTITY},
        blocking=True,
    )
    await update_color(0, 0, 0)

    client.async_send_command.reset_mock()

    # Assert that the brightness is preserved when turning on with color
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: HSM200_V1_ENTITY, ATTR_HS_COLOR: (240, 100)},
        blocking=True,
    )
    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == node.node_id
    assert args["valueId"] == {
        "commandClass": 51,
        "endpoint": 0,
        "property": "targetColor",
    }
    assert args["value"] == {"red": 0, "green": 0, "blue": 123}

    client.async_send_command.reset_mock()

    # Clear the color value to trigger an unknown state
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": node.node_id,
            "args": {
                "commandClassName": "Color Switch",
                "commandClass": 51,
                "endpoint": 0,
                "property": "currentColor",
                "newValue": None,
                "prevValue": None,
                "propertyName": "currentColor",
            },
        },
    )
    node.receive_event(event)
    await hass.async_block_till_done()

    state = hass.states.get(HSM200_V1_ENTITY)
    assert state.state == STATE_UNKNOWN

    client.async_send_command.reset_mock()

    # Assert that call fails if attribute is added to service call
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: HSM200_V1_ENTITY, ATTR_RGBW_COLOR: (255, 76, 255, 0)},
        blocking=True,
    )
    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == node.node_id
    assert args["valueId"] == {
        "commandClass": 51,
        "endpoint": 0,
        "property": "targetColor",
    }
    assert args["value"] == {"red": 255, "green": 76, "blue": 255}


async def test_basic_cc_light(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    client,
    ge_in_wall_dimmer_switch,
    integration,
) -> None:
    """Test light is created from Basic CC."""
    node = ge_in_wall_dimmer_switch

    entity_entry = entity_registry.async_get(BASIC_LIGHT_ENTITY)

    assert entity_entry
    assert not entity_entry.disabled

    state = hass.states.get(BASIC_LIGHT_ENTITY)
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes["supported_features"] == 0

    # Send value to 0
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 2,
            "args": {
                "commandClassName": "Basic",
                "commandClass": 32,
                "endpoint": 0,
                "property": "currentValue",
                "newValue": 0,
                "prevValue": None,
                "propertyName": "currentValue",
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(BASIC_LIGHT_ENTITY)
    assert state
    assert state.state == STATE_OFF

    # Turn on light
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": BASIC_LIGHT_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 2
    assert args["valueId"] == {
        "commandClass": 32,
        "endpoint": 0,
        "property": "targetValue",
    }
    assert args["value"] == 255

    # Due to optimistic updates, the state should be on even though the Z-Wave state
    # hasn't been updated yet
    state = hass.states.get(BASIC_LIGHT_ENTITY)

    assert state
    assert state.state == STATE_ON

    client.async_send_command.reset_mock()

    # Send value to 0
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 2,
            "args": {
                "commandClassName": "Basic",
                "commandClass": 32,
                "endpoint": 0,
                "property": "currentValue",
                "newValue": 0,
                "prevValue": None,
                "propertyName": "currentValue",
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(BASIC_LIGHT_ENTITY)
    assert state
    assert state.state == STATE_OFF

    # Turn on light with brightness
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": BASIC_LIGHT_ENTITY, ATTR_BRIGHTNESS: 128},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 2
    assert args["valueId"] == {
        "commandClass": 32,
        "endpoint": 0,
        "property": "targetValue",
    }
    assert args["value"] == 50

    # Since we specified a brightness, there is no optimistic update so the state
    # should be off
    state = hass.states.get(BASIC_LIGHT_ENTITY)

    assert state
    assert state.state == STATE_OFF

    client.async_send_command.reset_mock()

    # Turn off light
    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": BASIC_LIGHT_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 2
    assert args["valueId"] == {
        "commandClass": 32,
        "endpoint": 0,
        "property": "targetValue",
    }
    assert args["value"] == 0
