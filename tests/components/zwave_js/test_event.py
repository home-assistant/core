"""Test the Z-Wave JS event platform."""

from datetime import timedelta

from freezegun import freeze_time
from zwave_js_server.event import Event

from homeassistant.components.event import ATTR_EVENT_TYPE
from homeassistant.components.zwave_js.const import ATTR_VALUE
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

BASIC_EVENT_VALUE_ENTITY = "event.honeywell_in_wall_smart_fan_control_event_value"
CENTRAL_SCENE_ENTITY = "event.node_51_scene_002"


async def test_basic(
    hass: HomeAssistant, client, fan_honeywell_39358, integration
) -> None:
    """Test the Basic CC event entity."""
    dt_util.now()
    fut = dt_util.now() + timedelta(minutes=1)
    node = fan_honeywell_39358
    state = hass.states.get(BASIC_EVENT_VALUE_ENTITY)

    assert state
    assert state.state == STATE_UNKNOWN

    event = Event(
        type="value notification",
        data={
            "source": "node",
            "event": "value notification",
            "nodeId": node.node_id,
            "args": {
                "commandClassName": "Basic",
                "commandClass": 32,
                "endpoint": 0,
                "property": "event",
                "propertyName": "event",
                "value": 255,
                "metadata": {
                    "type": "number",
                    "readable": True,
                    "writeable": False,
                    "min": 0,
                    "max": 255,
                    "label": "Event value",
                },
                "ccVersion": 1,
            },
        },
    )
    with freeze_time(fut):
        node.receive_event(event)

    state = hass.states.get(BASIC_EVENT_VALUE_ENTITY)

    assert state
    assert state.state == dt_util.as_utc(fut).isoformat(timespec="milliseconds")
    attributes = state.attributes
    assert attributes[ATTR_EVENT_TYPE] == "Basic event value"
    assert attributes[ATTR_VALUE] == 255


async def test_central_scene(
    hass: HomeAssistant, client, central_scene_node, integration
) -> None:
    """Test the Central Scene CC event entity."""
    dt_util.now()
    fut = dt_util.now() + timedelta(minutes=1)
    node = central_scene_node
    state = hass.states.get(CENTRAL_SCENE_ENTITY)

    assert state
    assert state.state == STATE_UNKNOWN

    event = Event(
        type="value notification",
        data={
            "source": "node",
            "event": "value notification",
            "nodeId": node.node_id,
            "args": {
                "endpoint": 0,
                "commandClass": 91,
                "commandClassName": "Central Scene",
                "property": "scene",
                "propertyKey": "002",
                "propertyName": "scene",
                "propertyKeyName": "002",
                "ccVersion": 3,
                "metadata": {
                    "type": "number",
                    "readable": True,
                    "writeable": False,
                    "label": "Scene 002",
                    "min": 0,
                    "max": 255,
                    "states": {
                        "0": "KeyPressed",
                        "1": "KeyReleased",
                        "2": "KeyHeldDown",
                        "3": "KeyPressed2x",
                        "4": "KeyPressed3x",
                        "5": "KeyPressed4x",
                        "6": "KeyPressed5x",
                    },
                    "stateful": False,
                    "secret": False,
                },
                "value": 1,
            },
        },
    )
    with freeze_time(fut):
        node.receive_event(event)

    state = hass.states.get(CENTRAL_SCENE_ENTITY)

    assert state
    assert state.state == dt_util.as_utc(fut).isoformat(timespec="milliseconds")
    attributes = state.attributes
    assert attributes[ATTR_EVENT_TYPE] == "KeyReleased"
    assert attributes[ATTR_VALUE] == 1

    # Try invalid value
    event = Event(
        type="value notification",
        data={
            "source": "node",
            "event": "value notification",
            "nodeId": node.node_id,
            "args": {
                "endpoint": 0,
                "commandClass": 91,
                "commandClassName": "Central Scene",
                "property": "scene",
                "propertyKey": "002",
                "propertyName": "scene",
                "propertyKeyName": "002",
                "ccVersion": 3,
                "metadata": {
                    "type": "number",
                    "readable": True,
                    "writeable": False,
                    "label": "Scene 002",
                    "min": 0,
                    "max": 255,
                    "states": {
                        "0": "KeyPressed",
                        "1": "KeyReleased",
                        "2": "KeyHeldDown",
                        "3": "KeyPressed2x",
                        "4": "KeyPressed3x",
                        "5": "KeyPressed4x",
                        "6": "KeyPressed5x",
                    },
                    "stateful": False,
                    "secret": False,
                },
            },
        },
    )
    with freeze_time(fut + timedelta(minutes=10)):
        node.receive_event(event)

    # Nothing should have changed even though the time has changed
    state = hass.states.get(CENTRAL_SCENE_ENTITY)

    assert state
    assert state.state == dt_util.as_utc(fut).isoformat(timespec="milliseconds")
    attributes = state.attributes
    assert attributes[ATTR_EVENT_TYPE] == "KeyReleased"
    assert attributes[ATTR_VALUE] == 1
