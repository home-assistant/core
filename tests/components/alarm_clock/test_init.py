"""Tests for the alarm clock component."""

from datetime import datetime, time

import pytest

from homeassistant.components.alarm_clock.const import (
    ATTR_ALARM_TIME,
    ATTR_NEXT_ALARM,
    ATTR_REPEAT_DAYS,
    CONF_ALARM_TIME,
    CONF_REPEAT_DAYS,
    DOMAIN,
    EVENT_ALARM_CLOCK_CANCELLED,
    EVENT_ALARM_CLOCK_CHANGED,
    EVENT_ALARM_CLOCK_FINISHED,
    EVENT_ALARM_CLOCK_STARTED,
)
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_ID,
    ATTR_NAME,
    CONF_ENTITY_ID,
    CONF_NAME,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.setup import async_setup_component

from tests.common import async_fire_time_changed
from tests.typing import WebSocketGenerator


@pytest.fixture
def storage_setup(hass: HomeAssistant, hass_storage):
    """Storage setup."""

    async def _storage(items=None, config=None):
        if items is None:
            hass_storage[DOMAIN] = {
                "key": DOMAIN,
                "version": 1,
                "data": {
                    "items": [
                        {
                            ATTR_ID: "alarm_from_storage",
                            ATTR_NAME: "alarm from storage",
                            ATTR_ALARM_TIME: "12:00:00",
                        }
                    ]
                },
            }
        else:
            hass_storage[DOMAIN] = {
                "key": DOMAIN,
                "version": 1,
                "data": {"items": items},
            }
        if config is None:
            config = {DOMAIN: {}}
        return await async_setup_component(hass, DOMAIN, config)

    return _storage


async def test_config(hass: HomeAssistant) -> None:
    """Test config."""
    invalid_configs = [None, 1, {}, {"name with space": None}]

    for cfg in invalid_configs:
        assert not await async_setup_component(hass, DOMAIN, {DOMAIN: cfg})


async def test_config_single(hass: HomeAssistant) -> None:
    """Test configuration for non-repeating alarm."""
    count_start = len(hass.states.async_entity_ids())

    config = {
        DOMAIN: {
            "single": {
                CONF_ALARM_TIME: "09:00:00",
            }
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    assert count_start + 1 == len(hass.states.async_entity_ids())
    await hass.async_block_till_done()

    single_state = hass.states.get("alarm_clock.single")
    assert single_state is not None
    assert single_state.state == STATE_OFF
    assert single_state.attributes.get(ATTR_ALARM_TIME) == time(9, 0)
    assert single_state.attributes.get(ATTR_REPEAT_DAYS) == []


async def test_config_repeat(hass: HomeAssistant) -> None:
    """Test configuration for repeating alarm."""
    count_start = len(hass.states.async_entity_ids())

    config = {
        DOMAIN: {
            "repeat": {
                CONF_ALARM_TIME: "09:00:00",
                CONF_REPEAT_DAYS: ["mon", "tue"],
            }
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    assert count_start + 1 == len(hass.states.async_entity_ids())
    await hass.async_block_till_done()

    repeat_state = hass.states.get("alarm_clock.repeat")
    assert repeat_state is not None
    assert repeat_state.state == STATE_OFF
    assert repeat_state.attributes.get(ATTR_ALARM_TIME) == time(9, 0)
    assert repeat_state.attributes.get(ATTR_REPEAT_DAYS) == ["mon", "tue"]


@pytest.mark.freeze_time("2024-05-20T09:00:00-07:00")
async def test_turn_single(hass: HomeAssistant) -> None:
    """Test turning on/off a non-repeating alarm."""
    config = {
        DOMAIN: {
            "test": {
                CONF_ALARM_TIME: "09:00:00",
            }
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)

    # Turn on the alarm
    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {CONF_ENTITY_ID: "alarm_clock.test"}, blocking=True
    )
    await hass.async_block_till_done()
    state = hass.states.get("alarm_clock.test")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_NEXT_ALARM] == "2024-05-21T09:00:00-07:00"

    # Change on the alarm
    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_ON,
        {CONF_ENTITY_ID: "alarm_clock.test", ATTR_ALARM_TIME: "12:00:00"},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("alarm_clock.test")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_NEXT_ALARM] == "2024-05-20T12:00:00-07:00"

    # Turn off the alarm
    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {CONF_ENTITY_ID: "alarm_clock.test"}, blocking=True
    )
    await hass.async_block_till_done()
    state = hass.states.get("alarm_clock.test")
    assert state
    assert state.state == STATE_OFF
    assert ATTR_NEXT_ALARM not in state.attributes


@pytest.mark.freeze_time("2024-05-20T09:00:00-07:00")
async def test_turn_repeating(hass: HomeAssistant) -> None:
    """Test turning on/off a repeating alarm."""
    config = {
        DOMAIN: {
            "test": {
                CONF_ALARM_TIME: "09:00:00",
                CONF_REPEAT_DAYS: ["sun", "mon"],
            }
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)

    # Turn on the alarm
    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {CONF_ENTITY_ID: "alarm_clock.test"}, blocking=True
    )
    await hass.async_block_till_done()
    state = hass.states.get("alarm_clock.test")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_NEXT_ALARM] == "2024-05-26T09:00:00-07:00"

    # Change on the alarm
    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_ON,
        {CONF_ENTITY_ID: "alarm_clock.test", ATTR_ALARM_TIME: "12:00:00"},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("alarm_clock.test")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_NEXT_ALARM] == "2024-05-20T12:00:00-07:00"

    # Turn off the alarm
    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {CONF_ENTITY_ID: "alarm_clock.test"}, blocking=True
    )
    await hass.async_block_till_done()
    state = hass.states.get("alarm_clock.test")
    assert state
    assert state.state == STATE_OFF
    assert ATTR_NEXT_ALARM not in state.attributes


@pytest.mark.freeze_time("2024-05-20T22:00:00-07:00")
async def test_events(hass: HomeAssistant) -> None:
    """Test for alarm clock events."""
    hass.set_state(CoreState.starting)

    config = {
        DOMAIN: {
            "test": {
                CONF_ALARM_TIME: "09:00:00",
            }
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)

    results = []

    @callback
    def fake_event_listener(event):
        """Fake event listener for trigger."""
        results.append(event)

    hass.bus.async_listen(EVENT_ALARM_CLOCK_STARTED, fake_event_listener)
    hass.bus.async_listen(EVENT_ALARM_CLOCK_CHANGED, fake_event_listener)
    hass.bus.async_listen(EVENT_ALARM_CLOCK_FINISHED, fake_event_listener)
    hass.bus.async_listen(EVENT_ALARM_CLOCK_CANCELLED, fake_event_listener)

    # Turn on the alarm
    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {CONF_ENTITY_ID: "alarm_clock.test"}, blocking=True
    )
    await hass.async_block_till_done()

    assert len(results) == 1
    assert results[-1].event_type == EVENT_ALARM_CLOCK_STARTED

    # Change on the alarm
    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_ON,
        {CONF_ENTITY_ID: "alarm_clock.test", ATTR_ALARM_TIME: "12:00:00"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert len(results) == 2
    assert results[-1].event_type == EVENT_ALARM_CLOCK_CHANGED

    # Let time pass
    async_fire_time_changed(
        hass, datetime.strptime("2024-05-21T12:00:00-07:00", "%Y-%m-%dT%H:%M:%S%z")
    )
    await hass.async_block_till_done()

    assert len(results) == 3
    assert results[-1].event_type == EVENT_ALARM_CLOCK_FINISHED


async def test_load_from_storage(hass: HomeAssistant, storage_setup) -> None:
    """Test set up from storage."""
    assert await storage_setup()
    state = hass.states.get(f"{DOMAIN}.alarm_from_storage")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "alarm from storage"
    assert state.attributes.get(ATTR_ALARM_TIME) == time(12, 0)


async def test_update_while_off(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, storage_setup
) -> None:
    """Test updating alarm clock while off."""
    assert await storage_setup()

    alarm_clock_id = "alarm_from_storage"
    alarm_entity_id = f"{DOMAIN}.{alarm_clock_id}"

    state = hass.states.get(alarm_entity_id)
    assert state

    client = await hass_ws_client(hass)

    updated_settings = {
        CONF_NAME: "alarm updated",
        CONF_ALARM_TIME: "18:00:00",
        CONF_REPEAT_DAYS: ["wed"],
    }
    await client.send_json(
        {
            "id": 6,
            "type": f"{DOMAIN}/update",
            f"{DOMAIN}_id": alarm_clock_id,
            **updated_settings,
        }
    )
    resp = await client.receive_json()
    assert resp["success"]

    state = hass.states.get(alarm_entity_id)
    assert state.state == STATE_OFF
    assert ATTR_NEXT_ALARM not in state.attributes


@pytest.mark.freeze_time("2024-05-20T09:00:00-07:00")
async def test_update_while_on(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, storage_setup
) -> None:
    """Test updating alarm clock while on."""
    assert await storage_setup(
        items=[
            {
                ATTR_ID: "alarm_from_storage",
                ATTR_NAME: "alarm from storage",
                ATTR_ALARM_TIME: "12:00:00",
            }
        ]
    )

    alarm_clock_id = "alarm_from_storage"
    alarm_entity_id = f"{DOMAIN}.{alarm_clock_id}"

    # Turn on the alarm
    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {CONF_ENTITY_ID: alarm_entity_id}, blocking=True
    )
    await hass.async_block_till_done()

    # Assert initial state
    state = hass.states.get(alarm_entity_id)
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_NEXT_ALARM] == "2024-05-20T12:00:00-07:00"

    # Update settings
    client = await hass_ws_client(hass)

    updated_settings = {
        CONF_NAME: "alarm updated",
        CONF_ALARM_TIME: "18:00:00",
        CONF_REPEAT_DAYS: ["wed"],
    }
    await client.send_json(
        {
            "id": 6,
            "type": f"{DOMAIN}/update",
            f"{DOMAIN}_id": alarm_clock_id,
            **updated_settings,
        }
    )
    resp = await client.receive_json()
    assert resp["success"]

    state = hass.states.get(alarm_entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_NEXT_ALARM] == "2024-05-22T18:00:00-07:00"
