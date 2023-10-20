"""Test the Z-Wave JS event platform."""
from datetime import timedelta

from freezegun import freeze_time
from zwave_js_server.event import Event

from homeassistant.components.event import ATTR_EVENT_TYPE
from homeassistant.components.zwave_js.const import ATTR_VALUE
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .common import BASIC_EVENT_VALUE_ENTITY


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
    assert attributes[ATTR_EVENT_TYPE] == "Basic: Event value"
    assert attributes[ATTR_VALUE] == 255
