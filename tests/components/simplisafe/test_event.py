"""Define tests for SimpliSafe event entities."""

from unittest.mock import Mock, patch

import pytest
from simplipy.websocket import EVENT_CAMERA_MOTION_DETECTED, WebsocketEvent
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

CAMERA_SERIAL = "1234567890"
CAMERA_EVENT_ENTITY_ID = "event.camera_camera_motion"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_event_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    patch_simplisafe_api,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that all event entities are created."""
    with patch("homeassistant.components.simplisafe.PLATFORMS", [Platform.EVENT]):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


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
