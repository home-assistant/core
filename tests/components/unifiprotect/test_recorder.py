"""The tests for unifiprotect recorder."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import Mock

from uiprotect.data import Camera, Event, EventType, ModelType

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.components.unifiprotect.binary_sensor import EVENT_SENSORS
from homeassistant.components.unifiprotect.const import (
    ATTR_EVENT_ID,
    ATTR_EVENT_SCORE,
    DEFAULT_ATTRIBUTION,
)
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_FRIENDLY_NAME, STATE_ON, Platform
from homeassistant.core import HomeAssistant

from .utils import MockUFPFixture, ids_from_device_description, init_entry

from tests.components.recorder.common import async_wait_recording_done


async def test_exclude_attributes(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
    fixed_now: datetime,
) -> None:
    """Test binary_sensor has event_id and event_score excluded from recording."""
    now = fixed_now
    await init_entry(hass, ufp, [doorbell, unadopted_camera])

    _, entity_id = ids_from_device_description(
        Platform.BINARY_SENSOR, doorbell, EVENT_SENSORS[1]
    )

    event = Event(
        model=ModelType.EVENT,
        id="test_event_id",
        type=EventType.MOTION,
        start=fixed_now - timedelta(seconds=1),
        end=None,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
    )

    new_camera = doorbell.copy()
    new_camera.is_motion_detected = True
    new_camera.last_motion_event_id = event.id

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_camera

    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.api.bootstrap.events = {event.id: event}
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION
    assert state.attributes[ATTR_EVENT_SCORE] == 100
    await async_wait_recording_done(hass)

    states = await hass.async_add_executor_job(
        get_significant_states, hass, now, None, hass.states.async_entity_ids()
    )
    assert len(states) >= 1
    for entity_states in states.values():
        for state in entity_states:
            assert ATTR_EVENT_SCORE not in state.attributes
            assert ATTR_EVENT_ID not in state.attributes
            assert ATTR_FRIENDLY_NAME in state.attributes
