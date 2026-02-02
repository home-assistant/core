"""Test Lutron event platform."""

from unittest.mock import MagicMock

from pylutron import Button

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, async_capture_events


async def test_event_setup(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test event setup."""
    mock_config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, "lutron", {})
    await hass.async_block_till_done()

    # The event entity name is derived from the keypad and button
    state = hass.states.get("event.test_keypad_test_button")
    assert state is not None


async def test_event_single_press(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test single press event."""
    mock_config_entry.add_to_hass(hass)

    button = mock_lutron.areas[0].keypads[0].buttons[0]
    assert await async_setup_component(hass, "lutron", {})
    await hass.async_block_till_done()

    # Subscribe to events
    events = async_capture_events(hass, "lutron_event")

    # Simulate button press
    for call in button.subscribe.call_args_list:
        callback = call[0][0]
        callback(button, None, Button.Event.PRESSED, None)
    await hass.async_block_till_done()

    # Check bus event
    assert len(events) == 1
    assert events[0].data["action"] == "single"
    assert events[0].data["uuid"] == "button_uuid"


async def test_event_press_release(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test press and release events."""
    mock_config_entry.add_to_hass(hass)

    button = mock_lutron.areas[0].keypads[0].buttons[0]
    button.button_type = "MasterRaiseLower"

    assert await async_setup_component(hass, "lutron", {})
    await hass.async_block_till_done()

    # Subscribe to events
    events = async_capture_events(hass, "lutron_event")

    # Simulate button press
    for call in button.subscribe.call_args_list:
        callback = call[0][0]
        callback(button, None, Button.Event.PRESSED, None)
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["action"] == "pressed"

    # Simulate button release
    for call in button.subscribe.call_args_list:
        callback = call[0][0]
        callback(button, None, Button.Event.RELEASED, None)
    await hass.async_block_till_done()

    assert len(events) == 2
    assert events[1].data["action"] == "released"
