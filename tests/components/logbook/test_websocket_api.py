"""The tests for the logbook component."""
import asyncio
from unittest.mock import ANY, patch

import pytest

from homeassistant import core
from homeassistant.components.automation import EVENT_AUTOMATION_TRIGGERED
from homeassistant.components.script import EVENT_SCRIPT_STARTED
from homeassistant.components.websocket_api.const import TYPE_RESULT
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_NAME,
    EVENT_HOMEASSISTANT_START,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import State
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.components.recorder.common import (
    async_recorder_block_till_done,
    async_wait_recording_done,
)


@pytest.fixture()
def set_utc(hass):
    """Set timezone to UTC."""
    hass.config.set_time_zone("UTC")


@patch("homeassistant.components.logbook.websocket_api.EVENT_COALESCE_TIME", 0)
async def test_subscribe_unsubscribe_logbook_stream(hass, hass_ws_client):
    """Test subscribe/unsubscribe logbook stream."""
    now = dt_util.utcnow()
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "logbook", "automation", "script")
        ]
    )

    await hass.async_block_till_done()
    init_count = sum(hass.bus.async_listeners().values())

    hass.states.async_set("binary_sensor.is_light", STATE_ON)
    hass.states.async_set("binary_sensor.is_light", STATE_OFF)
    state: State = hass.states.get("binary_sensor.is_light")
    await hass.async_block_till_done()

    await async_wait_recording_done(hass)
    websocket_client = await hass_ws_client()
    await websocket_client.send_json(
        {"id": 7, "type": "logbook/event_stream", "start_time": now.isoformat()}
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == 7
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    msg = await websocket_client.receive_json()
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"] == [
        {
            "entity_id": "binary_sensor.is_light",
            "state": "off",
            "when": state.last_updated.timestamp(),
        }
    ]

    hass.states.async_set("light.alpha", "on")
    hass.states.async_set("light.alpha", "off")
    alpha_off_state: State = hass.states.get("light.alpha")
    hass.states.async_set("light.zulu", "on", {"color": "blue"})
    hass.states.async_set("light.zulu", "off", {"effect": "help"})
    zulu_off_state: State = hass.states.get("light.zulu")
    hass.states.async_set(
        "light.zulu", "on", {"effect": "help", "color": ["blue", "green"]}
    )
    zulu_on_state: State = hass.states.get("light.zulu")
    await hass.async_block_till_done()

    hass.states.async_remove("light.zulu")
    await hass.async_block_till_done()

    hass.states.async_set("light.zulu", "on", {"effect": "help", "color": "blue"})

    msg = await websocket_client.receive_json()
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"] == [
        {
            "entity_id": "light.alpha",
            "state": "off",
            "when": alpha_off_state.last_updated.timestamp(),
        },
        {
            "entity_id": "light.zulu",
            "state": "off",
            "when": zulu_off_state.last_updated.timestamp(),
        },
        {
            "entity_id": "light.zulu",
            "state": "on",
            "when": zulu_on_state.last_updated.timestamp(),
        },
    ]

    hass.bus.async_fire(
        EVENT_AUTOMATION_TRIGGERED,
        {ATTR_NAME: "Mock automation", ATTR_ENTITY_ID: "automation.mock_automation"},
    )
    hass.bus.async_fire(
        EVENT_SCRIPT_STARTED,
        {ATTR_NAME: "Mock script", ATTR_ENTITY_ID: "script.mock_script"},
    )
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    msg = await websocket_client.receive_json()
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"] == [
        {
            "context_id": ANY,
            "domain": "automation",
            "entity_id": "automation.mock_automation",
            "message": "triggered",
            "name": "Mock automation",
            "source": None,
            "when": ANY,
        },
        {
            "context_id": ANY,
            "domain": "script",
            "entity_id": "script.mock_script",
            "message": "started",
            "name": "Mock script",
            "when": ANY,
        },
        {
            "domain": "homeassistant",
            "icon": "mdi:home-assistant",
            "message": "started",
            "name": "Home Assistant",
            "when": ANY,
        },
    ]

    context = core.Context(
        id="ac5bd62de45711eaaeb351041eec8dd9",
        user_id="b400facee45711eaa9308bfd3d19e474",
    )
    with patch.object(
        core, "_LOGGER"
    ):  # the logger will hold a reference to the event since its logged
        # An Automation
        automation_entity_id_test = "automation.alarm"
        hass.bus.async_fire(
            EVENT_AUTOMATION_TRIGGERED,
            {ATTR_NAME: "Mock automation", ATTR_ENTITY_ID: automation_entity_id_test},
            context=context,
        )
        hass.bus.async_fire(
            EVENT_SCRIPT_STARTED,
            {ATTR_NAME: "Mock script", ATTR_ENTITY_ID: "script.mock_script"},
            context=context,
        )
        hass.states.async_set(
            automation_entity_id_test,
            STATE_ON,
            {ATTR_FRIENDLY_NAME: "Alarm Automation"},
            context=context,
        )
        entity_id_test = "alarm_control_panel.area_001"
        hass.states.async_set(entity_id_test, STATE_OFF, context=context)
        hass.states.async_set(entity_id_test, STATE_ON, context=context)
        entity_id_second = "alarm_control_panel.area_002"
        hass.states.async_set(entity_id_second, STATE_OFF, context=context)
        hass.states.async_set(entity_id_second, STATE_ON, context=context)

    await hass.async_block_till_done()

    msg = await websocket_client.receive_json()
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"] == [
        {
            "context_id": "ac5bd62de45711eaaeb351041eec8dd9",
            "context_user_id": "b400facee45711eaa9308bfd3d19e474",
            "domain": "automation",
            "entity_id": "automation.alarm",
            "message": "triggered",
            "name": "Mock automation",
            "source": None,
            "when": ANY,
        },
        {
            "context_domain": "automation",
            "context_entity_id": "automation.alarm",
            "context_event_type": "automation_triggered",
            "context_id": "ac5bd62de45711eaaeb351041eec8dd9",
            "context_message": "triggered",
            "context_name": "Mock automation",
            "context_user_id": "b400facee45711eaa9308bfd3d19e474",
            "domain": "script",
            "entity_id": "script.mock_script",
            "message": "started",
            "name": "Mock script",
            "when": ANY,
        },
        {
            "context_domain": "automation",
            "context_entity_id": "automation.alarm",
            "context_event_type": "automation_triggered",
            "context_message": "triggered",
            "context_name": "Mock automation",
            "context_user_id": "b400facee45711eaa9308bfd3d19e474",
            "entity_id": "alarm_control_panel.area_001",
            "state": "on",
            "when": ANY,
        },
        {
            "context_domain": "automation",
            "context_entity_id": "automation.alarm",
            "context_event_type": "automation_triggered",
            "context_message": "triggered",
            "context_name": "Mock automation",
            "context_user_id": "b400facee45711eaa9308bfd3d19e474",
            "entity_id": "alarm_control_panel.area_002",
            "state": "on",
            "when": ANY,
        },
    ]
    with patch.object(
        core, "_LOGGER"
    ):  # the logger will hold a reference to the event since its logged
        hass.bus.async_fire(
            EVENT_AUTOMATION_TRIGGERED,
            {ATTR_NAME: "Mock automation 2", ATTR_ENTITY_ID: automation_entity_id_test},
            context=context,
        )

    await hass.async_block_till_done()

    msg = await websocket_client.receive_json()
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"] == [
        {
            "context_domain": "automation",
            "context_entity_id": "automation.alarm",
            "context_event_type": "automation_triggered",
            "context_id": "ac5bd62de45711eaaeb351041eec8dd9",
            "context_message": "triggered",
            "context_name": "Mock automation",
            "context_user_id": "b400facee45711eaa9308bfd3d19e474",
            "domain": "automation",
            "entity_id": "automation.alarm",
            "message": "triggered",
            "name": "Mock automation 2",
            "source": None,
            "when": ANY,
        }
    ]

    await async_wait_recording_done(hass)
    with patch.object(
        core, "_LOGGER"
    ):  # the logger will hold a reference to the event since its logged
        hass.bus.async_fire(
            EVENT_AUTOMATION_TRIGGERED,
            {ATTR_NAME: "Mock automation 3", ATTR_ENTITY_ID: automation_entity_id_test},
            context=context,
        )

    await hass.async_block_till_done()
    msg = await websocket_client.receive_json()
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"] == [
        {
            "context_domain": "automation",
            "context_entity_id": "automation.alarm",
            "context_event_type": "automation_triggered",
            "context_id": "ac5bd62de45711eaaeb351041eec8dd9",
            "context_message": "triggered",
            "context_name": "Mock automation",
            "context_user_id": "b400facee45711eaa9308bfd3d19e474",
            "domain": "automation",
            "entity_id": "automation.alarm",
            "message": "triggered",
            "name": "Mock automation 3",
            "source": None,
            "when": ANY,
        }
    ]

    await websocket_client.send_json(
        {"id": 8, "type": "unsubscribe_events", "subscription": 7}
    )
    msg = await websocket_client.receive_json()

    assert msg["id"] == 8
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    # Check our listener got unsubscribed
    assert sum(hass.bus.async_listeners().values()) == init_count


@patch("homeassistant.components.logbook.websocket_api.EVENT_COALESCE_TIME", 0)
async def test_subscribe_unsubscribe_logbook_stream_entities(hass, hass_ws_client):
    """Test subscribe/unsubscribe logbook stream with specific entities."""
    now = dt_util.utcnow()
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "logbook", "automation", "script")
        ]
    )

    await hass.async_block_till_done()
    init_count = sum(hass.bus.async_listeners().values())
    hass.states.async_set("light.small", STATE_ON)
    hass.states.async_set("binary_sensor.is_light", STATE_ON)
    hass.states.async_set("binary_sensor.is_light", STATE_OFF)
    state: State = hass.states.get("binary_sensor.is_light")
    await hass.async_block_till_done()

    await async_wait_recording_done(hass)
    websocket_client = await hass_ws_client()
    await websocket_client.send_json(
        {
            "id": 7,
            "type": "logbook/event_stream",
            "start_time": now.isoformat(),
            "entity_ids": ["light.small", "binary_sensor.is_light"],
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == 7
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    msg = await websocket_client.receive_json()
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"] == [
        {
            "entity_id": "binary_sensor.is_light",
            "state": "off",
            "when": state.last_updated.timestamp(),
        }
    ]

    hass.states.async_set("light.alpha", STATE_ON)
    hass.states.async_set("light.alpha", STATE_OFF)
    hass.states.async_set("light.small", STATE_OFF, {"effect": "help", "color": "blue"})

    await hass.async_block_till_done()

    msg = await websocket_client.receive_json()
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"] == [
        {
            "entity_id": "light.small",
            "state": "off",
            "when": ANY,
        },
    ]

    await websocket_client.send_json(
        {"id": 8, "type": "unsubscribe_events", "subscription": 7}
    )
    msg = await websocket_client.receive_json()

    assert msg["id"] == 8
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    # Check our listener got unsubscribed
    assert sum(hass.bus.async_listeners().values()) == init_count


async def test_event_stream_bad_start_time(hass, hass_ws_client, recorder_mock):
    """Test event_stream bad start time."""
    await async_setup_component(hass, "logbook", {})
    await async_recorder_block_till_done(hass)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "logbook/event_stream",
            "start_time": "cats",
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "invalid_start_time"
