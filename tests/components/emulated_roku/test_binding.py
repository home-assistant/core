"""Tests for emulated_roku library bindings."""
from homeassistant.components.emulated_roku.binding import (
    ATTR_APP_ID,
    ATTR_COMMAND_TYPE,
    ATTR_KEY,
    ATTR_SOURCE_NAME,
    EVENT_ROKU_COMMAND,
    ROKU_COMMAND_KEYDOWN,
    ROKU_COMMAND_KEYPRESS,
    ROKU_COMMAND_KEYUP,
    ROKU_COMMAND_LAUNCH,
    EmulatedRoku,
)

from tests.async_mock import AsyncMock, Mock, patch


async def test_events_fired_properly(hass):
    """Test that events are fired correctly."""
    binding = EmulatedRoku(
        hass, "Test Emulated Roku", "1.2.3.4", 8060, None, None, None
    )

    events = []
    roku_event_handler = None

    def instantiate(
        loop,
        handler,
        roku_usn,
        host_ip,
        listen_port,
        advertise_ip=None,
        advertise_port=None,
        bind_multicast=None,
    ):
        nonlocal roku_event_handler
        roku_event_handler = handler

        return Mock(start=AsyncMock(), close=AsyncMock())

    def listener(event):
        events.append(event)

    with patch(
        "homeassistant.components.emulated_roku.binding.EmulatedRokuServer", instantiate
    ):
        hass.bus.async_listen(EVENT_ROKU_COMMAND, listener)

        assert await binding.setup() is True

        assert roku_event_handler is not None

        roku_event_handler.on_keydown("Test Emulated Roku", "A")
        roku_event_handler.on_keyup("Test Emulated Roku", "A")
        roku_event_handler.on_keypress("Test Emulated Roku", "C")
        roku_event_handler.launch("Test Emulated Roku", "1")

    await hass.async_block_till_done()

    assert len(events) == 4

    assert events[0].event_type == EVENT_ROKU_COMMAND
    assert events[0].data[ATTR_COMMAND_TYPE] == ROKU_COMMAND_KEYDOWN
    assert events[0].data[ATTR_SOURCE_NAME] == "Test Emulated Roku"
    assert events[0].data[ATTR_KEY] == "A"

    assert events[1].event_type == EVENT_ROKU_COMMAND
    assert events[1].data[ATTR_COMMAND_TYPE] == ROKU_COMMAND_KEYUP
    assert events[1].data[ATTR_SOURCE_NAME] == "Test Emulated Roku"
    assert events[1].data[ATTR_KEY] == "A"

    assert events[2].event_type == EVENT_ROKU_COMMAND
    assert events[2].data[ATTR_COMMAND_TYPE] == ROKU_COMMAND_KEYPRESS
    assert events[2].data[ATTR_SOURCE_NAME] == "Test Emulated Roku"
    assert events[2].data[ATTR_KEY] == "C"

    assert events[3].event_type == EVENT_ROKU_COMMAND
    assert events[3].data[ATTR_COMMAND_TYPE] == ROKU_COMMAND_LAUNCH
    assert events[3].data[ATTR_SOURCE_NAME] == "Test Emulated Roku"
    assert events[3].data[ATTR_APP_ID] == "1"
