"""Test for Nest events for the Smart Device Management API.

These tests fake out the subscriber/devicemanager, and are not using a real
pubsub subscriber.
"""

from __future__ import annotations

from collections.abc import Mapping
import datetime
from typing import Any
from unittest.mock import patch

from google_nest_sdm.device import Device
from google_nest_sdm.event import EventMessage

from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util.dt import utcnow

from .common import async_setup_sdm_platform

from tests.common import async_capture_events

DOMAIN = "nest"
DEVICE_ID = "some-device-id"
PLATFORM = "camera"
NEST_EVENT = "nest_event"
EVENT_SESSION_ID = "CjY5Y3VKaTZwR3o4Y19YbTVfMF..."
EVENT_ID = "FWWVQVUdGNUlTU2V4MGV2aTNXV..."

EVENT_KEYS = {"device_id", "type", "timestamp", "zones"}


def event_view(d: Mapping[str, Any]) -> Mapping[str, Any]:
    """View of an event with relevant keys for testing."""
    return {key: value for key, value in d.items() if key in EVENT_KEYS}


async def async_setup_devices(hass, device_type, traits={}, auth=None):
    """Set up the platform and prerequisites."""
    devices = {
        DEVICE_ID: Device.MakeDevice(
            {
                "name": DEVICE_ID,
                "type": device_type,
                "traits": traits,
            },
            auth=auth,
        ),
    }
    return await async_setup_sdm_platform(hass, PLATFORM, devices=devices)


def create_device_traits(event_traits=[]):
    """Create fake traits for a device."""
    result = {
        "sdm.devices.traits.Info": {
            "customName": "Front",
        },
        "sdm.devices.traits.CameraLiveStream": {
            "maxVideoResolution": {
                "width": 640,
                "height": 480,
            },
            "videoCodecs": ["H264"],
            "audioCodecs": ["AAC"],
        },
    }
    result.update({t: {} for t in event_traits})
    return result


def create_event(event_type, device_id=DEVICE_ID, timestamp=None):
    """Create an EventMessage for a single event type."""
    events = {
        event_type: {
            "eventSessionId": EVENT_SESSION_ID,
            "eventId": EVENT_ID,
        },
    }
    return create_events(events=events, device_id=device_id)


def create_events(events, device_id=DEVICE_ID, timestamp=None):
    """Create an EventMessage for events."""
    if not timestamp:
        timestamp = utcnow()
    return EventMessage(
        {
            "eventId": "some-event-id",
            "timestamp": timestamp.isoformat(timespec="seconds"),
            "resourceUpdate": {
                "name": device_id,
                "events": events,
            },
        },
        auth=None,
    )


async def test_doorbell_chime_event(hass, auth):
    """Test a pubsub message for a doorbell event."""
    events = async_capture_events(hass, NEST_EVENT)
    subscriber = await async_setup_devices(
        hass,
        "sdm.devices.types.DOORBELL",
        create_device_traits(["sdm.devices.traits.DoorbellChime"]),
        auth,
    )

    registry = er.async_get(hass)
    entry = registry.async_get("camera.front")
    assert entry is not None
    assert entry.unique_id == "some-device-id-camera"
    assert entry.original_name == "Front"
    assert entry.domain == "camera"

    device_registry = dr.async_get(hass)
    device = device_registry.async_get(entry.device_id)
    assert device.name == "Front"
    assert device.model == "Doorbell"
    assert device.identifiers == {("nest", DEVICE_ID)}

    timestamp = utcnow()
    await subscriber.async_receive_event(
        create_event("sdm.devices.events.DoorbellChime.Chime", timestamp=timestamp)
    )
    await hass.async_block_till_done()

    event_time = timestamp.replace(microsecond=0)
    assert len(events) == 1
    assert event_view(events[0].data) == {
        "device_id": entry.device_id,
        "type": "doorbell_chime",
        "timestamp": event_time,
    }


async def test_camera_motion_event(hass):
    """Test a pubsub message for a camera motion event."""
    events = async_capture_events(hass, NEST_EVENT)
    subscriber = await async_setup_devices(
        hass,
        "sdm.devices.types.CAMERA",
        create_device_traits(["sdm.devices.traits.CameraMotion"]),
    )
    registry = er.async_get(hass)
    entry = registry.async_get("camera.front")
    assert entry is not None

    timestamp = utcnow()
    await subscriber.async_receive_event(
        create_event("sdm.devices.events.CameraMotion.Motion", timestamp=timestamp)
    )
    await hass.async_block_till_done()

    event_time = timestamp.replace(microsecond=0)
    assert len(events) == 1
    assert event_view(events[0].data) == {
        "device_id": entry.device_id,
        "type": "camera_motion",
        "timestamp": event_time,
    }


async def test_camera_sound_event(hass):
    """Test a pubsub message for a camera sound event."""
    events = async_capture_events(hass, NEST_EVENT)
    subscriber = await async_setup_devices(
        hass,
        "sdm.devices.types.CAMERA",
        create_device_traits(["sdm.devices.traits.CameraSound"]),
    )
    registry = er.async_get(hass)
    entry = registry.async_get("camera.front")
    assert entry is not None

    timestamp = utcnow()
    await subscriber.async_receive_event(
        create_event("sdm.devices.events.CameraSound.Sound", timestamp=timestamp)
    )
    await hass.async_block_till_done()

    event_time = timestamp.replace(microsecond=0)
    assert len(events) == 1
    assert event_view(events[0].data) == {
        "device_id": entry.device_id,
        "type": "camera_sound",
        "timestamp": event_time,
    }


async def test_camera_person_event(hass):
    """Test a pubsub message for a camera person event."""
    events = async_capture_events(hass, NEST_EVENT)
    subscriber = await async_setup_devices(
        hass,
        "sdm.devices.types.DOORBELL",
        create_device_traits(["sdm.devices.traits.CameraPerson"]),
    )
    registry = er.async_get(hass)
    entry = registry.async_get("camera.front")
    assert entry is not None

    timestamp = utcnow()
    await subscriber.async_receive_event(
        create_event("sdm.devices.events.CameraPerson.Person", timestamp=timestamp)
    )
    await hass.async_block_till_done()

    event_time = timestamp.replace(microsecond=0)
    assert len(events) == 1
    assert event_view(events[0].data) == {
        "device_id": entry.device_id,
        "type": "camera_person",
        "timestamp": event_time,
    }


async def test_camera_multiple_event(hass):
    """Test a pubsub message for a camera person event."""
    events = async_capture_events(hass, NEST_EVENT)
    subscriber = await async_setup_devices(
        hass,
        "sdm.devices.types.DOORBELL",
        create_device_traits(
            ["sdm.devices.traits.CameraMotion", "sdm.devices.traits.CameraPerson"]
        ),
    )
    registry = er.async_get(hass)
    entry = registry.async_get("camera.front")
    assert entry is not None

    event_map = {
        "sdm.devices.events.CameraMotion.Motion": {
            "eventSessionId": EVENT_SESSION_ID,
            "eventId": EVENT_ID,
        },
        "sdm.devices.events.CameraPerson.Person": {
            "eventSessionId": EVENT_SESSION_ID,
            "eventId": EVENT_ID,
        },
    }

    timestamp = utcnow()
    await subscriber.async_receive_event(create_events(event_map, timestamp=timestamp))
    await hass.async_block_till_done()

    event_time = timestamp.replace(microsecond=0)
    assert len(events) == 2
    assert event_view(events[0].data) == {
        "device_id": entry.device_id,
        "type": "camera_motion",
        "timestamp": event_time,
    }
    assert event_view(events[1].data) == {
        "device_id": entry.device_id,
        "type": "camera_person",
        "timestamp": event_time,
    }


async def test_unknown_event(hass):
    """Test a pubsub message for an unknown event type."""
    events = async_capture_events(hass, NEST_EVENT)
    subscriber = await async_setup_devices(
        hass,
        "sdm.devices.types.DOORBELL",
        create_device_traits(["sdm.devices.traits.DoorbellChime"]),
    )
    await subscriber.async_receive_event(create_event("some-event-id"))
    await hass.async_block_till_done()

    assert len(events) == 0


async def test_unknown_device_id(hass):
    """Test a pubsub message for an unknown event type."""
    events = async_capture_events(hass, NEST_EVENT)
    subscriber = await async_setup_devices(
        hass,
        "sdm.devices.types.DOORBELL",
        create_device_traits(["sdm.devices.traits.DoorbellChime"]),
    )
    await subscriber.async_receive_event(
        create_event("sdm.devices.events.DoorbellChime.Chime", "invalid-device-id")
    )
    await hass.async_block_till_done()

    assert len(events) == 0


async def test_event_message_without_device_event(hass):
    """Test a pubsub message for an unknown event type."""
    events = async_capture_events(hass, NEST_EVENT)
    subscriber = await async_setup_devices(
        hass,
        "sdm.devices.types.DOORBELL",
        create_device_traits(["sdm.devices.traits.DoorbellChime"]),
    )
    timestamp = utcnow()
    event = EventMessage(
        {
            "eventId": "some-event-id",
            "timestamp": timestamp.isoformat(timespec="seconds"),
        },
        auth=None,
    )
    await subscriber.async_receive_event(event)
    await hass.async_block_till_done()

    assert len(events) == 0


async def test_doorbell_event_thread(hass, auth):
    """Test a series of pubsub messages in the same thread."""
    events = async_capture_events(hass, NEST_EVENT)
    subscriber = await async_setup_devices(
        hass,
        "sdm.devices.types.DOORBELL",
        create_device_traits(
            [
                "sdm.devices.traits.CameraClipPreview",
                "sdm.devices.traits.CameraPerson",
            ]
        ),
        auth,
    )
    registry = er.async_get(hass)
    entry = registry.async_get("camera.front")
    assert entry is not None

    event_message_data = {
        "eventId": "some-event-id-ignored",
        "resourceUpdate": {
            "name": DEVICE_ID,
            "events": {
                "sdm.devices.events.CameraMotion.Motion": {
                    "eventSessionId": EVENT_SESSION_ID,
                    "eventId": "n:1",
                },
                "sdm.devices.events.CameraClipPreview.ClipPreview": {
                    "eventSessionId": EVENT_SESSION_ID,
                    "previewUrl": "image-url-1",
                },
            },
        },
        "eventThreadId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
        "resourcegroup": [DEVICE_ID],
    }

    # Publish message #1 that starts the event thread
    timestamp1 = utcnow()
    message_data_1 = event_message_data.copy()
    message_data_1.update(
        {
            "timestamp": timestamp1.isoformat(timespec="seconds"),
            "eventThreadState": "STARTED",
        }
    )
    await subscriber.async_receive_event(EventMessage(message_data_1, auth=None))

    # Publish message #2 that sends a no-op update to end the event thread
    timestamp2 = timestamp1 + datetime.timedelta(seconds=1)
    message_data_2 = event_message_data.copy()
    message_data_2.update(
        {
            "timestamp": timestamp2.isoformat(timespec="seconds"),
            "eventThreadState": "ENDED",
        }
    )
    await subscriber.async_receive_event(EventMessage(message_data_2, auth=None))
    await hass.async_block_till_done()

    # The event is only published once
    assert len(events) == 1
    assert event_view(events[0].data) == {
        "device_id": entry.device_id,
        "type": "camera_motion",
        "timestamp": timestamp1.replace(microsecond=0),
    }


async def test_doorbell_event_session_update(hass, auth):
    """Test a pubsub message with updates to an existing session."""
    events = async_capture_events(hass, NEST_EVENT)
    subscriber = await async_setup_devices(
        hass,
        "sdm.devices.types.DOORBELL",
        create_device_traits(
            [
                "sdm.devices.traits.CameraClipPreview",
                "sdm.devices.traits.CameraPerson",
                "sdm.devices.traits.CameraMotion",
            ]
        ),
        auth,
    )
    registry = er.async_get(hass)
    entry = registry.async_get("camera.front")
    assert entry is not None

    # Message #1 has a motion event
    timestamp1 = utcnow()
    await subscriber.async_receive_event(
        create_events(
            {
                "sdm.devices.events.CameraMotion.Motion": {
                    "eventSessionId": EVENT_SESSION_ID,
                    "eventId": "n:1",
                },
                "sdm.devices.events.CameraClipPreview.ClipPreview": {
                    "eventSessionId": EVENT_SESSION_ID,
                    "previewUrl": "image-url-1",
                },
            },
            timestamp=timestamp1,
        )
    )

    # Message #2 has an extra person event
    timestamp2 = utcnow()
    await subscriber.async_receive_event(
        create_events(
            {
                "sdm.devices.events.CameraMotion.Motion": {
                    "eventSessionId": EVENT_SESSION_ID,
                    "eventId": "n:1",
                },
                "sdm.devices.events.CameraPerson.Person": {
                    "eventSessionId": EVENT_SESSION_ID,
                    "eventId": "n:2",
                },
                "sdm.devices.events.CameraClipPreview.ClipPreview": {
                    "eventSessionId": EVENT_SESSION_ID,
                    "previewUrl": "image-url-1",
                },
            },
            timestamp=timestamp2,
        )
    )
    await hass.async_block_till_done()

    assert len(events) == 2
    assert event_view(events[0].data) == {
        "device_id": entry.device_id,
        "type": "camera_motion",
        "timestamp": timestamp1.replace(microsecond=0),
    }
    assert event_view(events[1].data) == {
        "device_id": entry.device_id,
        "type": "camera_person",
        "timestamp": timestamp2.replace(microsecond=0),
    }


async def test_structure_update_event(hass):
    """Test a pubsub message for a new device being added."""
    events = async_capture_events(hass, NEST_EVENT)
    subscriber = await async_setup_devices(
        hass,
        "sdm.devices.types.DOORBELL",
        create_device_traits(["sdm.devices.traits.DoorbellChime"]),
    )

    # Entity for first device is registered
    registry = er.async_get(hass)
    assert registry.async_get("camera.front")

    new_device = Device.MakeDevice(
        {
            "name": "device-id-2",
            "type": "sdm.devices.types.CAMERA",
            "traits": {
                "sdm.devices.traits.Info": {
                    "customName": "Back",
                },
                "sdm.devices.traits.CameraLiveStream": {},
            },
        },
        auth=None,
    )
    device_manager = await subscriber.async_get_device_manager()
    device_manager.add_device(new_device)

    # Entity for new devie has not yet been loaded
    assert not registry.async_get("camera.back")

    # Send a message that triggers the device to be loaded
    message = EventMessage(
        {
            "eventId": "some-event-id",
            "timestamp": utcnow().isoformat(timespec="seconds"),
            "relationUpdate": {
                "type": "CREATED",
                "subject": "enterprise/example/foo",
                "object": "enterprise/example/devices/some-device-id2",
            },
        },
        auth=None,
    )
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation"
    ), patch("homeassistant.components.nest.PLATFORMS", [PLATFORM]), patch(
        "homeassistant.components.nest.api.GoogleNestSubscriber",
        return_value=subscriber,
    ):
        await subscriber.async_receive_event(message)
        await hass.async_block_till_done()

    # No home assistant events published
    assert not events

    assert registry.async_get("camera.front")
    # Currently need a manual reload to detect the new entity
    assert not registry.async_get("camera.back")


async def test_event_zones(hass):
    """Test events published with zone information."""
    events = async_capture_events(hass, NEST_EVENT)
    subscriber = await async_setup_devices(
        hass,
        "sdm.devices.types.DOORBELL",
        create_device_traits(["sdm.devices.traits.CameraMotion"]),
    )
    registry = er.async_get(hass)
    entry = registry.async_get("camera.front")
    assert entry is not None

    event_map = {
        "sdm.devices.events.CameraMotion.Motion": {
            "eventSessionId": EVENT_SESSION_ID,
            "eventId": EVENT_ID,
            "zones": ["Zone 1"],
        },
    }

    timestamp = utcnow()
    await subscriber.async_receive_event(create_events(event_map, timestamp=timestamp))
    await hass.async_block_till_done()

    event_time = timestamp.replace(microsecond=0)
    assert len(events) == 1
    assert event_view(events[0].data) == {
        "device_id": entry.device_id,
        "type": "camera_motion",
        "timestamp": event_time,
        "zones": ["Zone 1"],
    }
