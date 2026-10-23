"""Test ESPHome Events."""

import math

from aioesphomeapi import (
    APIClient,
    Event,
    EventInfo,
    EventVariable,
    EventVariableType,
    EventVariableValue,
)
import pytest

from homeassistant.components.event import (
    ATTR_EVENT_TYPE,
    ATTR_EVENT_TYPES,
    EventDeviceClass,
)
from homeassistant.const import ATTR_FRIENDLY_NAME, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .conftest import MockESPHomeDeviceType


@pytest.mark.freeze_time("2024-04-24 00:00:00+00:00")
async def test_generic_event_entity(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device,
) -> None:
    """Test a generic event entity and its availability behavior."""
    entity_info = [
        EventInfo(
            object_id="myevent",
            key=1,
            name="my event",
            event_types=["type1", "type2"],
            device_class=EventDeviceClass.BUTTON,
        )
    ]
    states = [Event(key=1, event_type="type1")]
    user_service = []
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    await hass.async_block_till_done()

    # Test initial state
    state = hass.states.get("event.test_my_event")
    assert state is not None
    assert state.state == "2024-04-24T00:00:00.000+00:00"
    assert state.attributes["event_type"] == "type1"

    # Test device becomes unavailable
    await device.mock_disconnect(True)
    await hass.async_block_till_done()
    state = hass.states.get("event.test_my_event")
    assert state.state == STATE_UNAVAILABLE

    # Test device becomes available again
    await device.mock_connect()
    await hass.async_block_till_done()

    # Event entity should be available immediately without waiting for data
    state = hass.states.get("event.test_my_event")
    assert state.state == "2024-04-24T00:00:00.001+00:00"
    assert state.attributes["event_type"] == "type1"


async def test_event_entity_values_per_event_type(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test each event type passes only its own values as attributes."""
    entity_info = [
        EventInfo(
            object_id="dimmer",
            key=1,
            name="dimmer",
            event_types=["press", "rotate_left"],
            variables=[
                EventVariable(name="number_of_presses", type=EventVariableType.INT),
                EventVariable(name="steps", type=EventVariableType.INT),
            ],
        )
    ]
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        # pressed twice, index 0 is number_of_presses
        states=[
            Event(
                key=1,
                event_type="press",
                values=[EventVariableValue(index=0, int_=2)],
            )
        ],
    )
    await hass.async_block_till_done()
    state = hass.states.get("event.test_dimmer")
    assert state.attributes[ATTR_EVENT_TYPE] == "press"
    assert state.attributes["number_of_presses"] == 2
    assert "steps" not in state.attributes

    # three steps to the left, index 1 is steps
    device.set_state(
        Event(
            key=1,
            event_type="rotate_left",
            values=[EventVariableValue(index=1, int_=3)],
        )
    )
    await hass.async_block_till_done()
    state = hass.states.get("event.test_dimmer")
    assert state.attributes[ATTR_EVENT_TYPE] == "rotate_left"
    assert state.attributes["steps"] == 3
    assert "number_of_presses" not in state.attributes


async def test_event_entity_several_values(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test an event passes all of its values as attributes."""
    entity_info = [
        EventInfo(
            object_id="tap_dial",
            key=1,
            name="tap dial",
            event_types=["clock_wise", "counter_clock_wise"],
            variables=[
                EventVariable(name="steps", type=EventVariableType.INT),
                EventVariable(name="duration", type=EventVariableType.INT),
                EventVariable(name="action", type=EventVariableType.STRING),
            ],
        )
    ]
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        # the dial starts turning: three steps clockwise within 250 ms
        states=[
            Event(
                key=1,
                event_type="clock_wise",
                values=[
                    EventVariableValue(index=0, int_=3),
                    EventVariableValue(index=1, int_=250),
                    EventVariableValue(index=2, string_="start"),
                ],
            )
        ],
    )
    await hass.async_block_till_done()
    state = hass.states.get("event.test_tap_dial")
    assert state.attributes[ATTR_EVENT_TYPE] == "clock_wise"
    assert state.attributes["steps"] == 3
    assert state.attributes["duration"] == 250
    assert state.attributes["action"] == "start"


@pytest.mark.parametrize(
    ("variable_type", "value", "expected"),
    [
        pytest.param(
            EventVariableType.BOOL, EventVariableValue(bool_=True), True, id="bool"
        ),
        pytest.param(EventVariableType.INT, EventVariableValue(int_=-3), -3, id="int"),
        pytest.param(
            EventVariableType.FLOAT, EventVariableValue(float_=1.5), 1.5, id="float"
        ),
        # a sensor without a reading yet reports NaN
        pytest.param(
            EventVariableType.FLOAT,
            EventVariableValue(float_=math.nan),
            None,
            id="float_nan",
        ),
        pytest.param(
            EventVariableType.STRING,
            EventVariableValue(string_="start"),
            "start",
            id="string",
        ),
    ],
)
async def test_event_entity_value_types(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    variable_type: EventVariableType,
    value: EventVariableValue,
    expected: bool | float | str | None,
) -> None:
    """Test each variable type arrives as its native Python type."""
    entity_info = [
        EventInfo(
            object_id="dial",
            key=1,
            name="dial",
            event_types=["turn"],
            variables=[EventVariable(name="value", type=variable_type)],
        )
    ]
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        states=[Event(key=1, event_type="turn", values=[value])],
    )
    await hass.async_block_till_done()
    attribute = hass.states.get("event.test_dial").attributes["value"]
    assert attribute == expected
    # True == 1 and 1.0 == 1, so compare the types as well
    assert type(attribute) is type(expected)


@pytest.mark.parametrize(
    "value",
    [
        # index 0 is a variable of a type from newer firmware
        pytest.param(EventVariableValue(index=0, int_=5), id="unknown_type"),
        # there is no variable with index 2
        pytest.param(EventVariableValue(index=2, int_=5), id="unknown_index"),
    ],
)
async def test_event_entity_skips_unknown_values(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    value: EventVariableValue,
) -> None:
    """Test a value without a known variable adds no attribute."""
    entity_info = [
        EventInfo(
            object_id="dial",
            key=1,
            name="dial",
            event_types=["turn"],
            variables=[
                # 9 stands for a type that newer firmware could add
                EventVariable(name="color", type=9),
                EventVariable(name="steps", type=EventVariableType.INT),
            ],
        )
    ]
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        states=[
            Event(
                key=1,
                event_type="turn",
                values=[value, EventVariableValue(index=1, int_=3)],
            )
        ],
    )
    await hass.async_block_till_done()
    state = hass.states.get("event.test_dial")
    assert state.attributes["steps"] == 3
    assert set(state.attributes) == {
        ATTR_EVENT_TYPE,
        ATTR_EVENT_TYPES,
        ATTR_FRIENDLY_NAME,
        "steps",
    }


async def test_event_entity_without_variables(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test an event entity without variables adds no attributes."""
    entity_info = [
        EventInfo(object_id="doorbell", key=1, name="doorbell", event_types=["ring"])
    ]
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        states=[Event(key=1, event_type="ring")],
    )
    await hass.async_block_till_done()
    state = hass.states.get("event.test_doorbell")
    assert state.attributes[ATTR_EVENT_TYPE] == "ring"
    assert set(state.attributes) == {
        ATTR_EVENT_TYPE,
        ATTR_EVENT_TYPES,
        ATTR_FRIENDLY_NAME,
    }
