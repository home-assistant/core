"""Define tests for SimpliSafe event entities."""

from unittest.mock import Mock

from simplipy.websocket import (
    EVENT_CAMERA_MOTION_DETECTED,
    EVENT_DOORBELL_DETECTED,
    EVENT_SECRET_ALERT_TRIGGERED,
    WebsocketEvent,
)

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

CAMERA_SERIAL = "1234567890"
SYSTEM_EVENT_ENTITY_ID = "event.alarm_control_panel_system_events"
CAMERA_EVENT_ENTITY_ID = "event.camera_camera_camera_events"


async def test_system_event_entity_created(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
) -> None:
    """Test that a system event entity is created."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(SYSTEM_EVENT_ENTITY_ID)
    assert state is not None
    # System events should NOT include camera-specific events:
    event_types = state.attributes["event_types"]
    assert EVENT_CAMERA_MOTION_DETECTED not in event_types
    assert EVENT_DOORBELL_DETECTED not in event_types
    # But should include other websocket events like secret_alert_triggered:
    assert EVENT_SECRET_ALERT_TRIGGERED in event_types


async def test_camera_event_entity_created(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
) -> None:
    """Test that camera event entities are created for V3 systems with cameras."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(CAMERA_EVENT_ENTITY_ID)
    assert state is not None
    assert state.attributes["event_types"] == [EVENT_CAMERA_MOTION_DETECTED]


async def test_camera_event_triggers_on_matching_serial(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
    websocket: Mock,
) -> None:
    """Test that camera event entity triggers for events with matching serial."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    event_callback = websocket.add_event_callback.call_args[0][0]

    # Fire a camera motion event for the camera's serial:
    event_callback(
        WebsocketEvent(
            event_cid=1170,
            info="Camera motion detected",
            system_id=12345,
            _raw_timestamp=0,
            _video=None,
            _vid=None,
            sensor_serial=CAMERA_SERIAL,
        )
    )
    await hass.async_block_till_done()

    state = hass.states.get(CAMERA_EVENT_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("event_type") == EVENT_CAMERA_MOTION_DETECTED


async def test_camera_event_ignores_mismatched_serial(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_simplisafe_api,
    websocket: Mock,
) -> None:
    """Test that camera event entity ignores events for a different serial."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    event_callback = websocket.add_event_callback.call_args[0][0]

    # Fire a camera motion event for a DIFFERENT serial:
    event_callback(
        WebsocketEvent(
            event_cid=1170,
            info="Camera motion detected",
            system_id=12345,
            _raw_timestamp=0,
            _video=None,
            _vid=None,
            sensor_serial="different_serial",
        )
    )
    await hass.async_block_till_done()

    state = hass.states.get(CAMERA_EVENT_ENTITY_ID)
    assert state is not None
    # State should remain unknown and no event should have been triggered:
    assert state.state == "unknown"
    assert state.attributes.get("event_type") is None
