"""Test the UniFi Protect event platform."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import Mock

from uiprotect.data import Camera, Event, EventType, ModelType, SmartDetectObjectType

from homeassistant.components.unifiprotect.const import (
    ATTR_EVENT_ID,
    DEFAULT_ATTRIBUTION,
)
from homeassistant.components.unifiprotect.event import EVENT_DESCRIPTIONS
from homeassistant.const import ATTR_ATTRIBUTION, Platform
from homeassistant.core import Event as HAEvent, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from .utils import (
    MockUFPFixture,
    adopt_devices,
    assert_entity_counts,
    ids_from_device_description,
    init_entry,
    remove_entities,
)


async def test_camera_remove(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera, unadopted_camera: Camera
) -> None:
    """Test removing and re-adding a camera device."""

    ufp.api.bootstrap.nvr.system_info.ustorage = None
    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.EVENT, 1, 1)
    await remove_entities(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.EVENT, 0, 0)
    await adopt_devices(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.EVENT, 1, 1)


async def test_doorbell_ring(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
    fixed_now: datetime,
) -> None:
    """Test a doorbell ring event."""

    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.EVENT, 1, 1)
    events: list[HAEvent] = []

    @callback
    def _capture_event(event: HAEvent) -> None:
        events.append(event)

    _, entity_id = ids_from_device_description(
        Platform.EVENT, doorbell, EVENT_DESCRIPTIONS[0]
    )

    unsub = async_track_state_change_event(hass, entity_id, _capture_event)
    event = Event(
        model=ModelType.EVENT,
        id="test_event_id",
        type=EventType.RING,
        start=fixed_now - timedelta(seconds=1),
        end=None,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
        api=ufp.api,
    )

    new_camera = doorbell.copy()
    new_camera.last_ring_event_id = "test_event_id"
    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event.id: event}

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event
    ufp.ws_msg(mock_msg)

    await hass.async_block_till_done()

    assert len(events) == 1
    state = events[0].data["new_state"]
    assert state
    timestamp = state.state
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION
    assert state.attributes[ATTR_EVENT_ID] == "test_event_id"

    event = Event(
        model=ModelType.EVENT,
        id="test_event_id",
        type=EventType.RING,
        start=fixed_now - timedelta(seconds=1),
        end=fixed_now + timedelta(seconds=1),
        score=50,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
        api=ufp.api,
    )

    new_camera = doorbell.copy()
    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event.id: event}

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event
    ufp.ws_msg(mock_msg)

    await hass.async_block_till_done()

    # Event is already seen and has end, should now be off
    state = hass.states.get(entity_id)
    assert state
    assert state.state == timestamp

    # Now send an event that has an end right away
    event = Event(
        model=ModelType.EVENT,
        id="new_event_id",
        type=EventType.RING,
        start=fixed_now - timedelta(seconds=1),
        end=fixed_now + timedelta(seconds=1),
        score=80,
        smart_detect_types=[SmartDetectObjectType.PACKAGE],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
        api=ufp.api,
    )

    new_camera = doorbell.copy()
    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event.id: event}

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event

    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == timestamp
    unsub()
