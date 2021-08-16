"""Test Websocket API messages module."""

from homeassistant.components.websocket_api.messages import (
    _cached_event_message as lru_event_cache,
    cached_event_message,
    message_to_json,
)
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import callback


async def test_cached_event_message(hass):
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


async def test_cached_event_message_with_different_idens(hass):
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


async def test_message_to_json(caplog):
    """Test we can serialize websocket messages."""

    json_str = message_to_json({"id": 1, "message": "xyz"})

    assert json_str == '{"id": 1, "message": "xyz"}'

    json_str2 = message_to_json({"id": 1, "message": _Unserializeable()})

    assert (
        json_str2
        == '{"id": 1, "type": "result", "success": false, "error": {"code": "unknown_error", "message": "Invalid JSON in response"}}'
    )
    assert "Unable to serialize to JSON" in caplog.text


class _Unserializeable:
    """A class that cannot be serialized."""
