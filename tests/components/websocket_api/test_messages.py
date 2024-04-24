"""Test Websocket API messages module."""
import pytest

from homeassistant.components.websocket_api.messages import (
    _cached_event_message as lru_event_cache,
    _state_diff_event,
    cached_event_message,
    message_to_json,
)
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import Context, Event, HomeAssistant, State, callback

from tests.common import async_capture_events


async def test_cached_event_message(hass: HomeAssistant) -> None:
    """Test that we cache event messages."""

    events = []

    @callback
    def _event_listener(event):
        events.append(event)

    hass.bus.async_listen(EVENT_STATE_CHANGED, _event_listener)

    hass.states.async_set("light.window", "on")
    hass.states.async_set("light.window", "off")
    await hass.async_block_till_done()

    assert len(events) == 2
    lru_event_cache.cache_clear()

    msg0 = cached_event_message(2, events[0])
    assert msg0 == cached_event_message(2, events[0])

    msg1 = cached_event_message(2, events[1])
    assert msg1 == cached_event_message(2, events[1])

    assert msg0 != msg1

    cache_info = lru_event_cache.cache_info()
    assert cache_info.hits == 2
    assert cache_info.misses == 2
    assert cache_info.currsize == 2

    cached_event_message(2, events[1])
    cache_info = lru_event_cache.cache_info()
    assert cache_info.hits == 3
    assert cache_info.misses == 2
    assert cache_info.currsize == 2


async def test_cached_event_message_with_different_idens(hass: HomeAssistant) -> None:
    """Test that we cache event messages when the subscrition idens differ."""

    events = []

    @callback
    def _event_listener(event):
        events.append(event)

    hass.bus.async_listen(EVENT_STATE_CHANGED, _event_listener)

    hass.states.async_set("light.window", "on")
    await hass.async_block_till_done()

    assert len(events) == 1

    lru_event_cache.cache_clear()

    msg0 = cached_event_message(2, events[0])
    msg1 = cached_event_message(3, events[0])
    msg2 = cached_event_message(4, events[0])

    assert msg0 != msg1
    assert msg0 != msg2

    cache_info = lru_event_cache.cache_info()
    assert cache_info.hits == 2
    assert cache_info.misses == 1
    assert cache_info.currsize == 1


async def test_state_diff_event(hass: HomeAssistant) -> None:
    """Test building state_diff_message."""
    state_change_events = async_capture_events(hass, EVENT_STATE_CHANGED)
    context = Context(user_id="user-id", parent_id="parent-id", id="id")
    hass.states.async_set("light.window", "on", context=context)
    hass.states.async_set("light.window", "off", context=context)
    await hass.async_block_till_done()

    last_state_event: Event = state_change_events[-1]
    new_state: State = last_state_event.data["new_state"]
    message = _state_diff_event(last_state_event)
    assert message == {
        "c": {
            "light.window": {
                "+": {"lc": new_state.last_changed.timestamp(), "s": "off"}
            }
        }
    }

    hass.states.async_set(
        "light.window",
        "red",
        context=Context(user_id="user-id", parent_id="new-parent-id", id="id"),
    )
    await hass.async_block_till_done()
    last_state_event: Event = state_change_events[-1]
    new_state: State = last_state_event.data["new_state"]
    message = _state_diff_event(last_state_event)

    assert message == {
        "c": {
            "light.window": {
                "+": {
                    "c": {"parent_id": "new-parent-id"},
                    "lc": new_state.last_changed.timestamp(),
                    "s": "red",
                }
            }
        }
    }

    hass.states.async_set(
        "light.window",
        "green",
        context=Context(
            user_id="new-user-id", parent_id="another-new-parent-id", id="id"
        ),
    )
    await hass.async_block_till_done()
    last_state_event: Event = state_change_events[-1]
    new_state: State = last_state_event.data["new_state"]
    message = _state_diff_event(last_state_event)

    assert message == {
        "c": {
            "light.window": {
                "+": {
                    "c": {
                        "parent_id": "another-new-parent-id",
                        "user_id": "new-user-id",
                    },
                    "lc": new_state.last_changed.timestamp(),
                    "s": "green",
                }
            }
        }
    }

    hass.states.async_set(
        "light.window",
        "blue",
        context=Context(
            user_id="another-new-user-id", parent_id="another-new-parent-id", id="id"
        ),
    )
    await hass.async_block_till_done()
    last_state_event: Event = state_change_events[-1]
    new_state: State = last_state_event.data["new_state"]
    message = _state_diff_event(last_state_event)

    assert message == {
        "c": {
            "light.window": {
                "+": {
                    "c": {"user_id": "another-new-user-id"},
                    "lc": new_state.last_changed.timestamp(),
                    "s": "blue",
                }
            }
        }
    }

    hass.states.async_set(
        "light.window",
        "yellow",
        context=Context(
            user_id="another-new-user-id",
            parent_id="another-new-parent-id",
            id="id-new",
        ),
    )
    await hass.async_block_till_done()
    last_state_event: Event = state_change_events[-1]
    new_state: State = last_state_event.data["new_state"]
    message = _state_diff_event(last_state_event)

    assert message == {
        "c": {
            "light.window": {
                "+": {
                    "c": "id-new",
                    "lc": new_state.last_changed.timestamp(),
                    "s": "yellow",
                }
            }
        }
    }

    new_context = Context()
    hass.states.async_set(
        "light.window", "purple", {"new": "attr"}, context=new_context
    )
    await hass.async_block_till_done()
    last_state_event: Event = state_change_events[-1]
    new_state: State = last_state_event.data["new_state"]
    message = _state_diff_event(last_state_event)

    assert message == {
        "c": {
            "light.window": {
                "+": {
                    "a": {"new": "attr"},
                    "c": {"id": new_context.id, "parent_id": None, "user_id": None},
                    "lc": new_state.last_changed.timestamp(),
                    "s": "purple",
                }
            }
        }
    }

    hass.states.async_set("light.window", "green", {}, context=new_context)
    await hass.async_block_till_done()
    last_state_event: Event = state_change_events[-1]
    new_state: State = last_state_event.data["new_state"]
    message = _state_diff_event(last_state_event)

    assert message == {
        "c": {
            "light.window": {
                "+": {"lc": new_state.last_changed.timestamp(), "s": "green"},
                "-": {"a": ["new"]},
            }
        }
    }


async def test_message_to_json(caplog: pytest.LogCaptureFixture) -> None:
    """Test we can serialize websocket messages."""

    json_str = message_to_json({"id": 1, "message": "xyz"})

    assert json_str == '{"id":1,"message":"xyz"}'

    json_str2 = message_to_json({"id": 1, "message": _Unserializeable()})

    assert (
        json_str2
        == '{"id":1,"type":"result","success":false,"error":{"code":"unknown_error","message":"Invalid JSON in response"}}'
    )
    assert "Unable to serialize to JSON" in caplog.text


class _Unserializeable:
    """A class that cannot be serialized."""
