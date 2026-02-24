"""Test Lutron event platform."""

from unittest.mock import MagicMock, patch

from pylutron import Button
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_capture_events, snapshot_platform


async def test_event_setup(
    hass: HomeAssistant,
    mock_lutron: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test event setup."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.lutron.PLATFORMS", [Platform.EVENT]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_event_single_press(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test single press event."""
    mock_config_entry.add_to_hass(hass)

    button = mock_lutron.areas[0].keypads[0].buttons[0]
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
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

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
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
