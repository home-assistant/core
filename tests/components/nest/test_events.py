"""Test for Nest events for the Smart Device Management API.

These tests fake out the subscriber/devicemanager, and are not using a real
pubsub subscriber.
"""

from __future__ import annotations

from collections.abc import Mapping
import datetime
from typing import Any
from unittest.mock import AsyncMock

import aiohttp
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util.dt import utcnow

from .common import (
    DEVICE_ID,
    TEST_CLIP_URL,
    TEST_IMAGE_URL,
    CreateDevice,
    PlatformSetup,
    create_nest_event,
)

from tests.common import async_capture_events

DOMAIN = "nest"
PLATFORM = "camera"
NEST_EVENT = "nest_event"
EVENT_SESSION_ID = "CjY5Y3VKaTZwR3o4Y19YbTVfMF..."
EVENT_ID = "FWWVQVUdGNUlTU2V4MGV2aTNXV..."
GENERATE_IMAGE_URL_RESPONSE = {
    "results": {
        "url": TEST_IMAGE_URL,
        "token": "g.0.eventToken",
    },
}
IMAGE_BYTES_FROM_EVENT = b"test url image bytes"

EVENT_KEYS = {"device_id", "type", "timestamp", "zones"}


@pytest.fixture
def platforms() -> list[str]:
    """Fixture for platforms to setup."""
    return [PLATFORM]


@pytest.fixture
def device_type() -> str:
    """Fixture for the type of device under test."""
    return "sdm.devices.types.DOORBELL"


@pytest.fixture
def device_traits() -> list[str]:
    """Fixture for the present traits of the device under test."""
    return ["sdm.devices.traits.DoorbellChime"]


@pytest.fixture(autouse=True)
def device(
    device_type: str, device_traits: list[str], create_device: CreateDevice
) -> None:
    """Fixture to create a device under test."""
    return create_device.create(
        raw_data={
            "name": DEVICE_ID,
            "type": device_type,
            "traits": create_device_traits(device_traits),
        }
    )


def event_view(d: Mapping[str, Any]) -> Mapping[str, Any]:
    """View of an event with relevant keys for testing."""
    return {key: value for key, value in d.items() if key in EVENT_KEYS}


def create_device_traits(event_traits: list[str]) -> dict[str, Any]:
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
    return create_nest_event(
        {
            "eventId": "some-event-id",
            "timestamp": timestamp.isoformat(timespec="seconds"),
            "resourceUpdate": {
                "name": device_id,
                "events": events,
            },
        },
    )


@pytest.mark.parametrize(
    ("device_type", "device_traits", "event_trait", "expected_model", "expected_type"),
    [
        (
            "sdm.devices.types.DOORBELL",
            ["sdm.devices.traits.DoorbellChime", "sdm.devices.traits.CameraEventImage"],
            "sdm.devices.events.DoorbellChime.Chime",
            "Doorbell",
            "doorbell_chime",
        ),
        (
            "sdm.devices.types.CAMERA",
            ["sdm.devices.traits.CameraMotion", "sdm.devices.traits.CameraEventImage"],
            "sdm.devices.events.CameraMotion.Motion",
            "Camera",
            "camera_motion",
        ),
        (
            "sdm.devices.types.CAMERA",
            ["sdm.devices.traits.CameraPerson", "sdm.devices.traits.CameraEventImage"],
            "sdm.devices.events.CameraPerson.Person",
            "Camera",
            "camera_person",
        ),
        (
            "sdm.devices.types.CAMERA",
            ["sdm.devices.traits.CameraSound", "sdm.devices.traits.CameraEventImage"],
            "sdm.devices.events.CameraSound.Sound",
            "Camera",
            "camera_sound",
        ),
    ],
)
async def test_event(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    auth,
    setup_platform,
    subscriber,
    event_trait,
    expected_model,
    expected_type,
) -> None:
    """Test a pubsub message for a doorbell event."""
    events = async_capture_events(hass, NEST_EVENT)
    await setup_platform()

    entry = entity_registry.async_get("camera.front")
    assert entry is not None
    assert entry.unique_id == f"{DEVICE_ID}-camera"
    assert entry.domain == "camera"

    device = device_registry.async_get(entry.device_id)
    assert device.name == "Front"
    assert device.model == expected_model
    assert device.identifiers == {("nest", DEVICE_ID)}

    auth.responses = [
        aiohttp.web.json_response(GENERATE_IMAGE_URL_RESPONSE),
        aiohttp.web.Response(body=IMAGE_BYTES_FROM_EVENT),
    ]

    timestamp = utcnow()
    await subscriber.async_receive_event(create_event(event_trait, timestamp=timestamp))
    await hass.async_block_till_done()

    event_time = timestamp.replace(microsecond=0)
    assert len(events) == 1
    assert event_view(events[0].data) == {
        "device_id": entry.device_id,
        "type": expected_type,
        "timestamp": event_time,
    }
    assert "image" in events[0].data["attachment"]
    assert "video" not in events[0].data["attachment"]


@pytest.mark.parametrize(
    "device_traits",
    [
        ["sdm.devices.traits.CameraMotion", "sdm.devices.traits.CameraPerson"],
    ],
)
async def test_camera_multiple_event(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, subscriber, setup_platform
) -> None:
    """Test a pubsub message for a camera person event."""
    events = async_capture_events(hass, NEST_EVENT)
    await setup_platform()
    entry = entity_registry.async_get("camera.front")
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


@pytest.mark.parametrize(
    "device_traits",
    [(["sdm.devices.traits.CameraMotion"])],
)
async def test_media_not_supported(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, subscriber, setup_platform
) -> None:
    """Test a pubsub message for a camera person event."""
    events = async_capture_events(hass, NEST_EVENT)
    await setup_platform()
    entry = entity_registry.async_get("camera.front")
    assert entry is not None

    event_map = {
        "sdm.devices.events.CameraMotion.Motion": {
            "eventSessionId": EVENT_SESSION_ID,
            "eventId": EVENT_ID,
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
    }
    # Media fetching not supported by this device
    assert "attachment" not in events[0].data


async def test_unknown_event(hass: HomeAssistant, subscriber, setup_platform) -> None:
    """Test a pubsub message for an unknown event type."""
    events = async_capture_events(hass, NEST_EVENT)
    await setup_platform()
    await subscriber.async_receive_event(create_event("some-event-id"))
    await hass.async_block_till_done()

    assert len(events) == 0


async def test_unknown_device_id(
    hass: HomeAssistant, subscriber, setup_platform
) -> None:
    """Test a pubsub message for an unknown event type."""
    events = async_capture_events(hass, NEST_EVENT)
    await setup_platform()
    await subscriber.async_receive_event(
        create_event("sdm.devices.events.DoorbellChime.Chime", "invalid-device-id")
    )
    await hass.async_block_till_done()

    assert len(events) == 0


async def test_event_message_without_device_event(
    hass: HomeAssistant, subscriber, setup_platform
) -> None:
    """Test a pubsub message for an unknown event type."""
    events = async_capture_events(hass, NEST_EVENT)
    await setup_platform()
    timestamp = utcnow()
    event = create_nest_event(
        {
            "eventId": "some-event-id",
            "timestamp": timestamp.isoformat(timespec="seconds"),
        },
    )
    await subscriber.async_receive_event(event)
    await hass.async_block_till_done()

    assert len(events) == 0


@pytest.mark.parametrize(
    "device_traits",
    [
        ["sdm.devices.traits.CameraClipPreview", "sdm.devices.traits.CameraPerson"],
    ],
)
async def test_doorbell_event_thread(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, subscriber, setup_platform
) -> None:
    """Test a series of pubsub messages in the same thread."""
    events = async_capture_events(hass, NEST_EVENT)
    await setup_platform()
    entry = entity_registry.async_get("camera.front")
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
                    "previewUrl": TEST_CLIP_URL,
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
    await subscriber.async_receive_event(create_nest_event(message_data_1))

    # Publish message #2 that sends a no-op update to end the event thread
    timestamp2 = timestamp1 + datetime.timedelta(seconds=1)
    message_data_2 = event_message_data.copy()
    message_data_2.update(
        {
            "timestamp": timestamp2.isoformat(timespec="seconds"),
            "eventThreadState": "ENDED",
        }
    )
    await subscriber.async_receive_event(create_nest_event(message_data_2))
    await hass.async_block_till_done()

    # The event is only published once
    assert len(events) == 1
    assert event_view(events[0].data) == {
        "device_id": entry.device_id,
        "type": "camera_motion",
        "timestamp": timestamp1.replace(microsecond=0),
    }
    assert "image" in events[0].data["attachment"]
    assert "video" in events[0].data["attachment"]


@pytest.mark.parametrize(
    "device_traits",
    [
        [
            "sdm.devices.traits.CameraClipPreview",
            "sdm.devices.traits.CameraPerson",
            "sdm.devices.traits.CameraMotion",
        ],
    ],
)
async def test_doorbell_event_session_update(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, subscriber, setup_platform
) -> None:
    """Test a pubsub message with updates to an existing session."""
    events = async_capture_events(hass, NEST_EVENT)
    await setup_platform()
    entry = entity_registry.async_get("camera.front")
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
                    "previewUrl": TEST_CLIP_URL,
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
                    "previewUrl": TEST_CLIP_URL,
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


async def test_structure_update_event(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    subscriber: AsyncMock,
    setup_platform: PlatformSetup,
    create_device: CreateDevice,
) -> None:
    """Test a pubsub message for a new device being added."""
    events = async_capture_events(hass, NEST_EVENT)
    await setup_platform()

    # Entity for first device is registered
    assert entity_registry.async_get("camera.front")

    create_device.create(
        raw_data={
            "name": "device-id-2",
            "type": "sdm.devices.types.CAMERA",
            "traits": {
                "sdm.devices.traits.Info": {
                    "customName": "Back",
                },
                "sdm.devices.traits.CameraLiveStream": {},
            },
        },
    )

    # Entity for new devie has not yet been loaded
    assert not entity_registry.async_get("camera.back")

    # Send a message that triggers the device to be loaded
    message = create_nest_event(
        {
            "eventId": "some-event-id",
            "timestamp": utcnow().isoformat(timespec="seconds"),
            "relationUpdate": {
                "type": "CREATED",
                "subject": "enterprise/example/foo",
                "object": "enterprise/example/devices/some-device-id2",
            },
        },
    )

    await subscriber.async_receive_event(message)
    await hass.async_block_till_done()

    # No home assistant events published
    assert not events

    assert entity_registry.async_get("camera.front")
    # Currently need a manual reload to detect the new entity
    assert not entity_registry.async_get("camera.back")


@pytest.mark.parametrize(
    "device_traits",
    [
        ["sdm.devices.traits.CameraMotion"],
    ],
)
async def test_event_zones(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, subscriber, setup_platform
) -> None:
    """Test events published with zone information."""
    events = async_capture_events(hass, NEST_EVENT)
    await setup_platform()
    entry = entity_registry.async_get("camera.front")
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
