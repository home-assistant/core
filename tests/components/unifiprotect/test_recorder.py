"""The tests for unifiprotect recorder."""

from datetime import datetime, timedelta

from uiprotect import EventChange, ProtectEvent, ProtectEventChannel
from uiprotect.data import Camera, EventType, SmartDetectObjectType

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.components.unifiprotect.const import (
    ATTR_EVENT_ID,
    ATTR_SMART_DETECT_TYPES,
)
from homeassistant.components.unifiprotect.event import EVENT_DESCRIPTIONS
from homeassistant.const import ATTR_FRIENDLY_NAME, Platform
from homeassistant.core import HomeAssistant

from .utils import (
    MockUFPFixture,
    ids_from_device_description,
    init_entry,
    setup_public_camera,
)

from tests.components.recorder.common import async_wait_recording_done


async def test_exclude_attributes(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
    fixed_now: datetime,
) -> None:
    """The smart-detect event entity excludes event_id/smart_detect_types from recording."""
    now = fixed_now
    # Smart-detect events arrive on the public events websocket; the entity's
    # availability also requires the public camera to resolve.
    setup_public_camera(ufp)
    await init_entry(hass, ufp, [doorbell, unadopted_camera])

    description = next(d for d in EVENT_DESCRIPTIONS if d.key == "smart_detection")
    _, entity_id = await ids_from_device_description(
        hass, Platform.EVENT, doorbell, description
    )

    ufp.events_msg(
        ProtectEvent(
            id="test_event_id",
            type=EventType.SMART_DETECT,
            channel=ProtectEventChannel.DETECTION,
            device_id=doorbell.id,
            device_mac=doorbell.mac,
            start=fixed_now - timedelta(seconds=1),
            end=fixed_now,
            smart_detect_types=(SmartDetectObjectType.PERSON,),
        ),
        EventChange.STARTED,
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_EVENT_ID] == "test_event_id"
    assert ATTR_SMART_DETECT_TYPES in state.attributes
    await async_wait_recording_done(hass)

    states = await hass.async_add_executor_job(
        get_significant_states, hass, now, None, hass.states.async_entity_ids()
    )
    assert len(states) >= 1
    for entity_states in states.values():
        for state in entity_states:
            assert ATTR_EVENT_ID not in state.attributes
            assert ATTR_SMART_DETECT_TYPES not in state.attributes
            assert ATTR_FRIENDLY_NAME in state.attributes
