"""Test for Nest binary sensor platform for the Smart Device Management API.

These tests fake out the subscriber/devicemanager, and are not using a real
pubsub subscriber.
"""

from google_nest_sdm.device import Device
from google_nest_sdm.event import EventMessage

from homeassistant.util.dt import utcnow

from .common import async_setup_sdm_platform

from tests.common import async_capture_events

DOMAIN = "nest"
DEVICE_ID = "some-device-id"
PLATFORM = "camera"
NEST_EVENT = "nest_event"
EVENT_SESSION_ID = "CjY5Y3VKaTZwR3o4Y19YbTVfMF..."
EVENT_ID = "FWWVQVUdGNUlTU2V4MGV2aTNXV..."


async def async_setup_devices(hass, device_type, traits={}):
    """Set up the platform and prerequisites."""
    devices = {
        DEVICE_ID: Device.MakeDevice(
            {
                "name": DEVICE_ID,
                "type": device_type,
                "traits": traits,
            },
            auth=None,
        ),
    }
    return await async_setup_sdm_platform(hass, PLATFORM, devices=devices)


def create_device_traits(event_trait):
    """Create fake traits for a device."""
    return {
        "sdm.devices.traits.Info": {
            "customName": "Front",
        },
        event_trait: {},
        "sdm.devices.traits.CameraLiveStream": {
            "maxVideoResolution": {
                "width": 640,
                "height": 480,
            },
            "videoCodecs": ["H264"],
            "audioCodecs": ["AAC"],
        },
    }


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


async def test_doorbell_chime_event(hass):
    """Test a pubsub message for a doorbell event."""
    events = async_capture_events(hass, NEST_EVENT)
    subscriber = await async_setup_devices(
        hass,
        "sdm.devices.types.DOORBELL",
        create_device_traits("sdm.devices.traits.DoorbellChime"),
    )

    registry = await hass.helpers.entity_registry.async_get_registry()
    entry = registry.async_get("camera.front")
    assert entry is not None
    assert entry.unique_id == "some-device-id-camera"
    assert entry.original_name == "Front"
    assert entry.domain == "camera"

    device_registry = await hass.helpers.device_registry.async_get_registry()
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
    assert events[0].data == {
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
        create_device_traits("sdm.devices.traits.CameraMotion"),
    )
    registry = await hass.helpers.entity_registry.async_get_registry()
    entry = registry.async_get("camera.front")
    assert entry is not None

    timestamp = utcnow()
    await subscriber.async_receive_event(
        create_event("sdm.devices.events.CameraMotion.Motion", timestamp=timestamp)
    )
    await hass.async_block_till_done()

    event_time = timestamp.replace(microsecond=0)
    assert len(events) == 1
    assert events[0].data == {
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
        create_device_traits("sdm.devices.traits.CameraSound"),
    )
    registry = await hass.helpers.entity_registry.async_get_registry()
    entry = registry.async_get("camera.front")
    assert entry is not None

    timestamp = utcnow()
    await subscriber.async_receive_event(
        create_event("sdm.devices.events.CameraSound.Sound", timestamp=timestamp)
    )
    await hass.async_block_till_done()

    event_time = timestamp.replace(microsecond=0)
    assert len(events) == 1
    assert events[0].data == {
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
        create_device_traits("sdm.devices.traits.CameraEventImage"),
    )
    registry = await hass.helpers.entity_registry.async_get_registry()
    entry = registry.async_get("camera.front")
    assert entry is not None

    timestamp = utcnow()
    await subscriber.async_receive_event(
        create_event("sdm.devices.events.CameraPerson.Person", timestamp=timestamp)
    )
    await hass.async_block_till_done()

    event_time = timestamp.replace(microsecond=0)
    assert len(events) == 1
    assert events[0].data == {
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
        create_device_traits("sdm.devices.traits.CameraEventImage"),
    )
    registry = await hass.helpers.entity_registry.async_get_registry()
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
    assert events[0].data == {
        "device_id": entry.device_id,
        "type": "camera_motion",
        "timestamp": event_time,
    }
    assert events[1].data == {
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
        create_device_traits("sdm.devices.traits.DoorbellChime"),
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
        create_device_traits("sdm.devices.traits.DoorbellChime"),
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
        create_device_traits("sdm.devices.traits.DoorbellChime"),
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
