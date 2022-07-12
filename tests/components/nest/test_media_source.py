"""Test for Nest Media Source.

These tests simulate recent camera events received by the subscriber exposed
as media in the media source.
"""

from collections.abc import Generator
import datetime
from http import HTTPStatus
import io
from typing import Any
from unittest.mock import patch

import aiohttp
import av
from google_nest_sdm.event import EventMessage
import numpy as np
import pytest

from homeassistant.components import media_source
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.components.media_source import const
from homeassistant.components.media_source.error import Unresolvable
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.template import DATE_STR_FORMAT
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from .common import DEVICE_ID, CreateDevice, FakeSubscriber

from tests.common import async_capture_events

DOMAIN = "nest"
DEVICE_NAME = "Front"
PLATFORM = "camera"
NEST_EVENT = "nest_event"
EVENT_ID = "1aXEvi9ajKVTdDsXdJda8fzfCa"
EVENT_SESSION_ID = "CjY5Y3VKaTZwR3o4Y19YbTVfMF"
CAMERA_DEVICE_TYPE = "sdm.devices.types.CAMERA"
CAMERA_TRAITS = {
    "sdm.devices.traits.Info": {
        "customName": DEVICE_NAME,
    },
    "sdm.devices.traits.CameraImage": {},
    "sdm.devices.traits.CameraEventImage": {},
    "sdm.devices.traits.CameraPerson": {},
    "sdm.devices.traits.CameraMotion": {},
}
BATTERY_CAMERA_TRAITS = {
    "sdm.devices.traits.Info": {
        "customName": DEVICE_NAME,
    },
    "sdm.devices.traits.CameraClipPreview": {},
    "sdm.devices.traits.CameraLiveStream": {},
    "sdm.devices.traits.CameraPerson": {},
    "sdm.devices.traits.CameraMotion": {},
}

PERSON_EVENT = "sdm.devices.events.CameraPerson.Person"
MOTION_EVENT = "sdm.devices.events.CameraMotion.Motion"

TEST_IMAGE_URL = "https://domain/sdm_event_snapshot/dGTZwR3o4Y1..."
GENERATE_IMAGE_URL_RESPONSE = {
    "results": {
        "url": TEST_IMAGE_URL,
        "token": "g.0.eventToken",
    },
}
IMAGE_BYTES_FROM_EVENT = b"test url image bytes"
IMAGE_AUTHORIZATION_HEADERS = {"Authorization": "Basic g.0.eventToken"}
NEST_EVENT = "nest_event"


def frame_image_data(frame_i, total_frames):
    """Generate image content for a frame of a video."""
    img = np.empty((480, 320, 3))
    img[:, :, 0] = 0.5 + 0.5 * np.sin(2 * np.pi * (0 / 3 + frame_i / total_frames))
    img[:, :, 1] = 0.5 + 0.5 * np.sin(2 * np.pi * (1 / 3 + frame_i / total_frames))
    img[:, :, 2] = 0.5 + 0.5 * np.sin(2 * np.pi * (2 / 3 + frame_i / total_frames))

    img = np.round(255 * img).astype(np.uint8)
    img = np.clip(img, 0, 255)
    return img


@pytest.fixture
def platforms() -> list[str]:
    """Fixture for platforms to setup."""
    return [PLATFORM]


@pytest.fixture(autouse=True)
async def setup_components(hass) -> None:
    """Fixture to initialize the integration."""
    await async_setup_component(hass, "media_source", {})


@pytest.fixture
def device_type() -> str:
    """Fixture for the type of device under test."""
    return CAMERA_DEVICE_TYPE


@pytest.fixture
def device_traits() -> dict[str, Any]:
    """Fixture for the present traits of the device under test."""
    return CAMERA_TRAITS


@pytest.fixture(autouse=True)
def device(
    device_type: str, device_traits: dict[str, Any], create_device: CreateDevice
) -> None:
    """Fixture to create a device under test."""
    return create_device.create(
        raw_data={
            "name": DEVICE_ID,
            "type": device_type,
            "traits": device_traits,
        }
    )


@pytest.fixture
def mp4() -> io.BytesIO:
    """Generate test mp4 clip."""

    total_frames = 10
    fps = 10
    output = io.BytesIO()
    output.name = "test.mp4"
    container = av.open(output, mode="w", format="mp4")

    stream = container.add_stream("libx264", rate=fps)
    stream.width = 480
    stream.height = 320
    stream.pix_fmt = "yuv420p"

    for frame_i in range(total_frames):
        img = frame_image_data(frame_i, total_frames)
        frame = av.VideoFrame.from_ndarray(img, format="rgb24")
        for packet in stream.encode(frame):
            container.mux(packet)

    # Flush stream
    for packet in stream.encode():
        container.mux(packet)

    # Close the file
    container.close()
    output.seek(0)

    return output


@pytest.fixture(autouse=True)
def enable_prefetch(subscriber: FakeSubscriber) -> None:
    """Fixture to enable media fetching for tests to exercise."""
    subscriber.cache_policy.fetch = True


@pytest.fixture
def cache_size() -> int:
    """Fixture for overrideing cache size."""
    return 100


@pytest.fixture(autouse=True)
def apply_cache_size(cache_size):
    """Fixture for patching the cache size."""
    with patch("homeassistant.components.nest.EVENT_MEDIA_CACHE_SIZE", new=cache_size):
        yield


def create_event(
    event_session_id, event_id, event_type, timestamp=None, device_id=None
):
    """Create an EventMessage for a single event type."""
    if not timestamp:
        timestamp = dt_util.now()
    event_data = {
        event_type: {
            "eventSessionId": event_session_id,
            "eventId": event_id,
        },
    }
    return create_event_message(event_data, timestamp, device_id=device_id)


def create_event_message(event_data, timestamp, device_id=None):
    """Create an EventMessage for a single event type."""
    if device_id is None:
        device_id = DEVICE_ID
    return EventMessage(
        {
            "eventId": f"{EVENT_ID}-{timestamp}",
            "timestamp": timestamp.isoformat(timespec="seconds"),
            "resourceUpdate": {
                "name": device_id,
                "events": event_data,
            },
        },
        auth=None,
    )


def create_battery_event_data(
    event_type, event_session_id=EVENT_SESSION_ID, event_id="n:2"
):
    """Return event payload data for a battery camera event."""
    return {
        event_type: {
            "eventSessionId": event_session_id,
            "eventId": event_id,
        },
        "sdm.devices.events.CameraClipPreview.ClipPreview": {
            "eventSessionId": event_session_id,
            "previewUrl": "https://127.0.0.1/example",
        },
    }


@pytest.mark.parametrize(
    "device_type,device_traits",
    [
        (
            "sdm.devices.types.THERMOSTAT",
            {
                "sdm.devices.traits.Temperature": {},
            },
        )
    ],
)
async def test_no_eligible_devices(hass, setup_platform):
    """Test a media source with no eligible camera devices."""
    await setup_platform()
    browse = await media_source.async_browse_media(hass, f"{const.URI_SCHEME}{DOMAIN}")
    assert browse.domain == DOMAIN
    assert browse.identifier == ""
    assert browse.title == "Nest"
    assert not browse.children


@pytest.mark.parametrize("device_traits", [CAMERA_TRAITS, BATTERY_CAMERA_TRAITS])
async def test_supported_device(hass, setup_platform):
    """Test a media source with a supported camera."""
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    camera = hass.states.get("camera.front")
    assert camera is not None

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device({(DOMAIN, DEVICE_ID)})
    assert device
    assert device.name == DEVICE_NAME

    browse = await media_source.async_browse_media(hass, f"{const.URI_SCHEME}{DOMAIN}")
    assert browse.domain == DOMAIN
    assert browse.title == "Nest"
    assert browse.identifier == ""
    assert browse.can_expand
    assert len(browse.children) == 1
    assert browse.children[0].domain == DOMAIN
    assert browse.children[0].identifier == device.id
    assert browse.children[0].title == "Front: Recent Events"

    browse = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{device.id}"
    )
    assert browse.domain == DOMAIN
    assert browse.identifier == device.id
    assert browse.title == "Front: Recent Events"
    assert len(browse.children) == 0


async def test_integration_unloaded(hass, auth, setup_platform):
    """Test the media player loads, but has no devices, when config unloaded."""
    await setup_platform()

    browse = await media_source.async_browse_media(hass, f"{const.URI_SCHEME}{DOMAIN}")
    assert browse.domain == DOMAIN
    assert browse.identifier == ""
    assert browse.title == "Nest"
    assert len(browse.children) == 1

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state == ConfigEntryState.NOT_LOADED

    # No devices returned
    browse = await media_source.async_browse_media(hass, f"{const.URI_SCHEME}{DOMAIN}")
    assert browse.domain == DOMAIN
    assert browse.identifier == ""
    assert browse.title == "Nest"
    assert len(browse.children) == 0


async def test_camera_event(hass, hass_client, subscriber, auth, setup_platform):
    """Test a media source and image created for an event."""
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    camera = hass.states.get("camera.front")
    assert camera is not None

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device({(DOMAIN, DEVICE_ID)})
    assert device
    assert device.name == DEVICE_NAME

    # Capture any events published
    received_events = async_capture_events(hass, NEST_EVENT)

    # Set up fake media, and publish image events
    auth.responses = [
        aiohttp.web.json_response(GENERATE_IMAGE_URL_RESPONSE),
        aiohttp.web.Response(body=IMAGE_BYTES_FROM_EVENT),
    ]
    event_timestamp = dt_util.now()
    await subscriber.async_receive_event(
        create_event(
            EVENT_SESSION_ID,
            EVENT_ID,
            PERSON_EVENT,
            timestamp=event_timestamp,
        )
    )
    await hass.async_block_till_done()

    assert len(received_events) == 1
    received_event = received_events[0]
    assert received_event.data["device_id"] == device.id
    assert received_event.data["type"] == "camera_person"
    event_identifier = received_event.data["nest_event_id"]

    # Media root directory
    browse = await media_source.async_browse_media(hass, f"{const.URI_SCHEME}{DOMAIN}")
    assert browse.title == "Nest"
    assert browse.identifier == ""
    assert browse.can_expand
    # A device is represented as a child directory
    assert len(browse.children) == 1
    assert browse.children[0].domain == DOMAIN
    assert browse.children[0].identifier == device.id
    assert browse.children[0].title == "Front: Recent Events"
    assert browse.children[0].can_expand
    assert browse.children[0].can_play
    # Expanding the root does not expand the device
    assert len(browse.children[0].children) == 0

    # Browse to the device
    browse = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{device.id}"
    )
    assert browse.domain == DOMAIN
    assert browse.identifier == device.id
    assert browse.title == "Front: Recent Events"
    assert browse.can_expand
    # The device expands recent events
    assert len(browse.children) == 1
    assert browse.children[0].domain == DOMAIN
    assert browse.children[0].identifier == f"{device.id}/{event_identifier}"
    event_timestamp_string = event_timestamp.strftime(DATE_STR_FORMAT)
    assert browse.children[0].title == f"Person @ {event_timestamp_string}"
    assert not browse.children[0].can_expand
    assert len(browse.children[0].children) == 0

    # Browse to the event
    browse = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{device.id}/{event_identifier}"
    )
    assert browse.domain == DOMAIN
    assert browse.identifier == f"{device.id}/{event_identifier}"
    assert "Person" in browse.title
    assert not browse.can_expand
    assert not browse.children
    assert not browse.can_play

    # Resolving the event links to the media
    media = await media_source.async_resolve_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{device.id}/{event_identifier}", None
    )
    assert media.url == f"/api/nest/event_media/{device.id}/{event_identifier}"
    assert media.mime_type == "image/jpeg"

    client = await hass_client()
    response = await client.get(media.url)
    assert response.status == HTTPStatus.OK, "Response not matched: %s" % response
    contents = await response.read()
    assert contents == IMAGE_BYTES_FROM_EVENT

    # Resolving the device id points to the most recent event
    media = await media_source.async_resolve_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{device.id}", None
    )
    assert media.url == f"/api/nest/event_media/{device.id}/{event_identifier}"
    assert media.mime_type == "image/jpeg"


async def test_event_order(hass, auth, subscriber, setup_platform):
    """Test multiple events are in descending timestamp order."""
    await setup_platform()

    auth.responses = [
        aiohttp.web.json_response(GENERATE_IMAGE_URL_RESPONSE),
        aiohttp.web.Response(body=IMAGE_BYTES_FROM_EVENT),
        aiohttp.web.json_response(GENERATE_IMAGE_URL_RESPONSE),
        aiohttp.web.Response(body=IMAGE_BYTES_FROM_EVENT),
    ]
    event_session_id1 = "FWWVQVUdGNUlTU2V4MGV2aTNXV..."
    event_timestamp1 = dt_util.now()
    await subscriber.async_receive_event(
        create_event(
            event_session_id1,
            EVENT_ID + "1",
            PERSON_EVENT,
            timestamp=event_timestamp1,
        )
    )
    await hass.async_block_till_done()

    event_session_id2 = "GXXWRWVeHNUlUU3V3MGV3bUOYW..."
    event_timestamp2 = event_timestamp1 + datetime.timedelta(seconds=5)
    await subscriber.async_receive_event(
        create_event(
            event_session_id2,
            EVENT_ID + "2",
            MOTION_EVENT,
            timestamp=event_timestamp2,
        ),
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1
    camera = hass.states.get("camera.front")
    assert camera is not None

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device({(DOMAIN, DEVICE_ID)})
    assert device
    assert device.name == DEVICE_NAME

    browse = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{device.id}"
    )
    assert browse.domain == DOMAIN
    assert browse.identifier == device.id
    assert browse.title == "Front: Recent Events"
    assert browse.can_expand

    # Motion event is most recent
    assert len(browse.children) == 2
    assert browse.children[0].domain == DOMAIN
    event_timestamp_string = event_timestamp2.strftime(DATE_STR_FORMAT)
    assert browse.children[0].title == f"Motion @ {event_timestamp_string}"
    assert not browse.children[0].can_expand
    assert not browse.children[0].can_play

    # Person event is next
    assert browse.children[1].domain == DOMAIN
    event_timestamp_string = event_timestamp1.strftime(DATE_STR_FORMAT)
    assert browse.children[1].title == f"Person @ {event_timestamp_string}"
    assert not browse.children[1].can_expand
    assert not browse.children[1].can_play


async def test_multiple_image_events_in_session(
    hass, auth, hass_client, subscriber, setup_platform
):
    """Test multiple events published within the same event session."""
    await setup_platform()

    event_session_id = "FWWVQVUdGNUlTU2V4MGV2aTNXV..."
    event_timestamp1 = dt_util.now()
    event_timestamp2 = event_timestamp1 + datetime.timedelta(seconds=5)

    assert len(hass.states.async_all()) == 1
    camera = hass.states.get("camera.front")
    assert camera is not None

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device({(DOMAIN, DEVICE_ID)})
    assert device
    assert device.name == DEVICE_NAME

    # Capture any events published
    received_events = async_capture_events(hass, NEST_EVENT)

    auth.responses = [
        aiohttp.web.json_response(GENERATE_IMAGE_URL_RESPONSE),
        aiohttp.web.Response(body=IMAGE_BYTES_FROM_EVENT + b"-1"),
        aiohttp.web.json_response(GENERATE_IMAGE_URL_RESPONSE),
        aiohttp.web.Response(body=IMAGE_BYTES_FROM_EVENT + b"-2"),
    ]
    await subscriber.async_receive_event(
        # First camera sees motion then it recognizes a person
        create_event(
            event_session_id,
            EVENT_ID + "1",
            MOTION_EVENT,
            timestamp=event_timestamp1,
        )
    )
    await hass.async_block_till_done()
    await subscriber.async_receive_event(
        create_event(
            event_session_id,
            EVENT_ID + "2",
            PERSON_EVENT,
            timestamp=event_timestamp2,
        ),
    )
    await hass.async_block_till_done()

    assert len(received_events) == 2
    received_event = received_events[0]
    assert received_event.data["device_id"] == device.id
    assert received_event.data["type"] == "camera_motion"
    event_identifier1 = received_event.data["nest_event_id"]
    received_event = received_events[1]
    assert received_event.data["device_id"] == device.id
    assert received_event.data["type"] == "camera_person"
    event_identifier2 = received_event.data["nest_event_id"]

    browse = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{device.id}"
    )
    assert browse.domain == DOMAIN
    assert browse.identifier == device.id
    assert browse.title == "Front: Recent Events"
    assert browse.can_expand

    # Person event is most recent
    assert len(browse.children) == 2
    event = browse.children[0]
    assert event.domain == DOMAIN
    assert event.identifier == f"{device.id}/{event_identifier2}"
    event_timestamp_string = event_timestamp2.strftime(DATE_STR_FORMAT)
    assert event.title == f"Person @ {event_timestamp_string}"
    assert not event.can_expand
    assert not event.can_play

    # Motion event is next
    event = browse.children[1]
    assert event.domain == DOMAIN
    assert event.identifier == f"{device.id}/{event_identifier1}"
    event_timestamp_string = event_timestamp1.strftime(DATE_STR_FORMAT)
    assert event.title == f"Motion @ {event_timestamp_string}"
    assert not event.can_expand
    assert not event.can_play

    # Resolve the most recent event
    media = await media_source.async_resolve_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{device.id}/{event_identifier2}", None
    )
    assert media.url == f"/api/nest/event_media/{device.id}/{event_identifier2}"
    assert media.mime_type == "image/jpeg"

    client = await hass_client()
    response = await client.get(media.url)
    assert response.status == HTTPStatus.OK, "Response not matched: %s" % response
    contents = await response.read()
    assert contents == IMAGE_BYTES_FROM_EVENT + b"-2"

    # Resolving the event links to the media
    media = await media_source.async_resolve_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{device.id}/{event_identifier1}", None
    )
    assert media.url == f"/api/nest/event_media/{device.id}/{event_identifier1}"
    assert media.mime_type == "image/jpeg"

    client = await hass_client()
    response = await client.get(media.url)
    assert response.status == HTTPStatus.OK, "Response not matched: %s" % response
    contents = await response.read()
    assert contents == IMAGE_BYTES_FROM_EVENT + b"-1"


@pytest.mark.parametrize("device_traits", [BATTERY_CAMERA_TRAITS])
async def test_multiple_clip_preview_events_in_session(
    hass,
    auth,
    hass_client,
    subscriber,
    setup_platform,
):
    """Test multiple events published within the same event session."""
    await setup_platform()

    event_timestamp1 = dt_util.now()
    event_timestamp2 = event_timestamp1 + datetime.timedelta(seconds=5)

    assert len(hass.states.async_all()) == 1
    camera = hass.states.get("camera.front")
    assert camera is not None

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device({(DOMAIN, DEVICE_ID)})
    assert device
    assert device.name == DEVICE_NAME

    # Capture any events published
    received_events = async_capture_events(hass, NEST_EVENT)

    # Publish two events: First motion, then a person is recognized. Both
    # events share a single clip.
    auth.responses = [
        aiohttp.web.Response(body=IMAGE_BYTES_FROM_EVENT),
    ]
    await subscriber.async_receive_event(
        create_event_message(
            create_battery_event_data(MOTION_EVENT),
            timestamp=event_timestamp1,
        )
    )
    await hass.async_block_till_done()
    await subscriber.async_receive_event(
        create_event_message(
            create_battery_event_data(PERSON_EVENT),
            timestamp=event_timestamp2,
        )
    )
    await hass.async_block_till_done()

    assert len(received_events) == 2
    received_event = received_events[0]
    assert received_event.data["device_id"] == device.id
    assert received_event.data["type"] == "camera_motion"
    event_identifier1 = received_event.data["nest_event_id"]
    received_event = received_events[1]
    assert received_event.data["device_id"] == device.id
    assert received_event.data["type"] == "camera_person"
    event_identifier2 = received_event.data["nest_event_id"]

    browse = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{device.id}"
    )
    assert browse.domain == DOMAIN
    assert browse.identifier == device.id
    assert browse.title == "Front: Recent Events"
    assert browse.can_expand

    # The two distinct events are combined in a single clip preview
    assert len(browse.children) == 1
    event = browse.children[0]
    assert event.domain == DOMAIN
    event_timestamp_string = event_timestamp1.strftime(DATE_STR_FORMAT)
    assert event.identifier == f"{device.id}/{event_identifier2}"
    assert event.title == f"Motion, Person @ {event_timestamp_string}"
    assert not event.can_expand
    assert event.can_play

    # Resolve media for each event that was published and they will resolve
    # to the same clip preview media clip object.
    # Resolve media for the first event
    media = await media_source.async_resolve_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{device.id}/{event_identifier1}", None
    )
    assert media.url == f"/api/nest/event_media/{device.id}/{event_identifier1}"
    assert media.mime_type == "video/mp4"

    client = await hass_client()
    response = await client.get(media.url)
    assert response.status == HTTPStatus.OK, "Response not matched: %s" % response
    contents = await response.read()
    assert contents == IMAGE_BYTES_FROM_EVENT

    # Resolve media for the second event
    media = await media_source.async_resolve_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{device.id}/{event_identifier1}", None
    )
    assert media.url == f"/api/nest/event_media/{device.id}/{event_identifier1}"
    assert media.mime_type == "video/mp4"

    response = await client.get(media.url)
    assert response.status == HTTPStatus.OK, "Response not matched: %s" % response
    contents = await response.read()
    assert contents == IMAGE_BYTES_FROM_EVENT


async def test_browse_invalid_device_id(hass, auth, setup_platform):
    """Test a media source request for an invalid device id."""
    await setup_platform()

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device({(DOMAIN, DEVICE_ID)})
    assert device
    assert device.name == DEVICE_NAME

    with pytest.raises(BrowseError):
        await media_source.async_browse_media(
            hass, f"{const.URI_SCHEME}{DOMAIN}/invalid-device-id"
        )

    with pytest.raises(BrowseError):
        await media_source.async_browse_media(
            hass, f"{const.URI_SCHEME}{DOMAIN}/invalid-device-id/invalid-event-id"
        )


async def test_browse_invalid_event_id(hass, auth, setup_platform):
    """Test a media source browsing for an invalid event id."""
    await setup_platform()

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device({(DOMAIN, DEVICE_ID)})
    assert device
    assert device.name == DEVICE_NAME

    browse = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{device.id}"
    )
    assert browse.domain == DOMAIN
    assert browse.identifier == device.id
    assert browse.title == "Front: Recent Events"

    with pytest.raises(BrowseError):
        await media_source.async_browse_media(
            hass,
            f"{const.URI_SCHEME}{DOMAIN}/{device.id}/GXXWRWVeHNUlUU3V3MGV3bUOYW...",
        )


async def test_resolve_missing_event_id(hass, auth, setup_platform):
    """Test a media source request missing an event id."""
    await setup_platform()

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device({(DOMAIN, DEVICE_ID)})
    assert device
    assert device.name == DEVICE_NAME

    with pytest.raises(Unresolvable):
        await media_source.async_resolve_media(
            hass,
            f"{const.URI_SCHEME}{DOMAIN}/{device.id}",
            None,
        )


async def test_resolve_invalid_device_id(hass, auth, setup_platform):
    """Test resolving media for an invalid event id."""
    await setup_platform()
    with pytest.raises(Unresolvable):
        await media_source.async_resolve_media(
            hass,
            f"{const.URI_SCHEME}{DOMAIN}/invalid-device-id/GXXWRWVeHNUlUU3V3MGV3bUOYW...",
            None,
        )


async def test_resolve_invalid_event_id(hass, auth, setup_platform):
    """Test resolving media for an invalid event id."""
    await setup_platform()

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device({(DOMAIN, DEVICE_ID)})
    assert device
    assert device.name == DEVICE_NAME

    # Assume any event ID can be resolved to a media url. Fetching the actual media may fail
    # if the ID is not valid. Content type is inferred based on the capabilities of the device.
    media = await media_source.async_resolve_media(
        hass,
        f"{const.URI_SCHEME}{DOMAIN}/{device.id}/GXXWRWVeHNUlUU3V3MGV3bUOYW...",
        None,
    )
    assert (
        media.url == f"/api/nest/event_media/{device.id}/GXXWRWVeHNUlUU3V3MGV3bUOYW..."
    )
    assert media.mime_type == "image/jpeg"


@pytest.mark.parametrize("device_traits", [BATTERY_CAMERA_TRAITS])
async def test_camera_event_clip_preview(
    hass, auth, hass_client, mp4, subscriber, setup_platform
):
    """Test an event for a battery camera video clip."""
    # Capture any events published
    received_events = async_capture_events(hass, NEST_EVENT)
    await setup_platform()

    auth.responses = [
        aiohttp.web.Response(body=mp4.getvalue()),
    ]
    event_timestamp = dt_util.now()
    await subscriber.async_receive_event(
        create_event_message(
            create_battery_event_data(MOTION_EVENT),
            timestamp=event_timestamp,
        )
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1
    camera = hass.states.get("camera.front")
    assert camera is not None

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device({(DOMAIN, DEVICE_ID)})
    assert device
    assert device.name == DEVICE_NAME

    # Verify events are published correctly
    assert len(received_events) == 1
    received_event = received_events[0]
    assert received_event.data["device_id"] == device.id
    assert received_event.data["type"] == "camera_motion"
    event_identifier = received_event.data["nest_event_id"]

    # List devices
    browse = await media_source.async_browse_media(hass, f"{const.URI_SCHEME}{DOMAIN}")
    assert browse.domain == DOMAIN
    assert len(browse.children) == 1
    assert browse.children[0].domain == DOMAIN
    assert browse.children[0].identifier == device.id
    assert browse.children[0].title == "Front: Recent Events"
    assert (
        browse.children[0].thumbnail
        == f"/api/nest/event_media/{device.id}/{event_identifier}/thumbnail"
    )
    assert browse.children[0].can_play
    # Browse to the device
    browse = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{device.id}"
    )
    assert browse.domain == DOMAIN
    assert browse.identifier == device.id
    assert browse.title == "Front: Recent Events"
    assert browse.can_expand
    assert not browse.thumbnail
    # The device expands recent events
    assert len(browse.children) == 1
    assert browse.children[0].domain == DOMAIN
    assert browse.children[0].identifier == f"{device.id}/{event_identifier}"
    event_timestamp_string = event_timestamp.strftime(DATE_STR_FORMAT)
    assert browse.children[0].title == f"Motion @ {event_timestamp_string}"
    assert not browse.children[0].can_expand
    assert len(browse.children[0].children) == 0
    assert browse.children[0].can_play
    assert (
        browse.children[0].thumbnail
        == f"/api/nest/event_media/{device.id}/{event_identifier}/thumbnail"
    )

    # Verify received event and media ids match
    assert browse.children[0].identifier == f"{device.id}/{event_identifier}"

    # Browse to the event
    browse = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{device.id}/{event_identifier}"
    )
    assert browse.domain == DOMAIN
    event_timestamp_string = event_timestamp.strftime(DATE_STR_FORMAT)
    assert browse.title == f"Motion @ {event_timestamp_string}"
    assert not browse.can_expand
    assert len(browse.children) == 0
    assert browse.can_play

    # Resolving the event links to the media
    media = await media_source.async_resolve_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{device.id}/{event_identifier}", None
    )
    assert media.url == f"/api/nest/event_media/{device.id}/{event_identifier}"
    assert media.mime_type == "video/mp4"

    client = await hass_client()
    response = await client.get(media.url)
    assert response.status == HTTPStatus.OK, "Response not matched: %s" % response
    contents = await response.read()
    assert contents == mp4.getvalue()

    # Verify thumbnail for mp4 clip
    response = await client.get(
        f"/api/nest/event_media/{device.id}/{event_identifier}/thumbnail"
    )
    assert response.status == HTTPStatus.OK, "Response not matched: %s" % response
    await response.read()  # Animated gif format not tested


async def test_event_media_render_invalid_device_id(
    hass, auth, hass_client, setup_platform
):
    """Test event media API called with an invalid device id."""
    await setup_platform()
    client = await hass_client()
    response = await client.get("/api/nest/event_media/invalid-device-id")
    assert response.status == HTTPStatus.NOT_FOUND, (
        "Response not matched: %s" % response
    )


async def test_event_media_render_invalid_event_id(
    hass, auth, hass_client, setup_platform
):
    """Test event media API called with an invalid device id."""
    await setup_platform()
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device({(DOMAIN, DEVICE_ID)})
    assert device
    assert device.name == DEVICE_NAME

    client = await hass_client()
    response = await client.get(f"/api/nest/event_media/{device.id}/invalid-event-id")
    assert response.status == HTTPStatus.NOT_FOUND, (
        "Response not matched: %s" % response
    )


async def test_event_media_failure(hass, auth, hass_client, subscriber, setup_platform):
    """Test event media fetch sees a failure from the server."""
    received_events = async_capture_events(hass, NEST_EVENT)

    await setup_platform()
    # Failure from server when fetching media
    auth.responses = [
        aiohttp.web.Response(status=HTTPStatus.INTERNAL_SERVER_ERROR),
    ]
    event_timestamp = dt_util.now()
    await subscriber.async_receive_event(
        create_event(
            EVENT_SESSION_ID,
            EVENT_ID,
            PERSON_EVENT,
            timestamp=event_timestamp,
        ),
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1
    camera = hass.states.get("camera.front")
    assert camera is not None

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device({(DOMAIN, DEVICE_ID)})
    assert device
    assert device.name == DEVICE_NAME

    # Verify events are published correctly
    assert len(received_events) == 1
    received_event = received_events[0]
    assert received_event.data["device_id"] == device.id
    assert received_event.data["type"] == "camera_person"
    event_identifier = received_event.data["nest_event_id"]

    # Resolving the event links to the media
    media = await media_source.async_resolve_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{device.id}/{event_identifier}", None
    )
    assert media.url == f"/api/nest/event_media/{device.id}/{event_identifier}"
    assert media.mime_type == "image/jpeg"

    # Media is not available to be fetched
    client = await hass_client()
    response = await client.get(media.url)
    assert response.status == HTTPStatus.NOT_FOUND, (
        "Response not matched: %s" % response
    )


async def test_media_permission_unauthorized(
    hass, auth, hass_client, hass_admin_user, setup_platform
):
    """Test case where user does not have permissions to view media."""
    await setup_platform()
    assert len(hass.states.async_all()) == 1
    camera = hass.states.get("camera.front")
    assert camera is not None

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device({(DOMAIN, DEVICE_ID)})
    assert device
    assert device.name == DEVICE_NAME

    media_url = f"/api/nest/event_media/{device.id}/some-event-id"

    # Empty policy with no access to the entity
    hass_admin_user.mock_policy({})

    client = await hass_client()
    response = await client.get(media_url)
    assert response.status == HTTPStatus.UNAUTHORIZED, (
        "Response not matched: %s" % response
    )


async def test_multiple_devices(
    hass, auth, hass_client, create_device, subscriber, setup_platform
):
    """Test events received for multiple devices."""
    device_id2 = f"{DEVICE_ID}-2"
    create_device.create(
        raw_data={
            "name": device_id2,
            "type": CAMERA_DEVICE_TYPE,
            "traits": CAMERA_TRAITS,
        }
    )
    await setup_platform()

    device_registry = dr.async_get(hass)
    device1 = device_registry.async_get_device({(DOMAIN, DEVICE_ID)})
    assert device1
    device2 = device_registry.async_get_device({(DOMAIN, device_id2)})
    assert device2

    # Very no events have been received yet
    browse = await media_source.async_browse_media(hass, f"{const.URI_SCHEME}{DOMAIN}")
    assert len(browse.children) == 2
    assert not browse.children[0].can_play
    assert not browse.children[1].can_play
    browse = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{device1.id}"
    )
    assert len(browse.children) == 0
    browse = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{device2.id}"
    )
    assert len(browse.children) == 0

    # Send events for device #1
    for i in range(0, 5):
        auth.responses = [
            aiohttp.web.json_response(GENERATE_IMAGE_URL_RESPONSE),
            aiohttp.web.Response(body=IMAGE_BYTES_FROM_EVENT),
        ]
        await subscriber.async_receive_event(
            create_event(
                f"event-session-id-{i}",
                f"event-id-{i}",
                PERSON_EVENT,
                device_id=DEVICE_ID,
            )
        )
        await hass.async_block_till_done()

    browse = await media_source.async_browse_media(hass, f"{const.URI_SCHEME}{DOMAIN}")
    assert len(browse.children) == 2
    assert browse.children[0].can_play
    assert not browse.children[1].can_play
    browse = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{device1.id}"
    )
    assert len(browse.children) == 5
    browse = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{device2.id}"
    )
    assert len(browse.children) == 0

    # Send events for device #2
    for i in range(0, 3):
        auth.responses = [
            aiohttp.web.json_response(GENERATE_IMAGE_URL_RESPONSE),
            aiohttp.web.Response(body=IMAGE_BYTES_FROM_EVENT),
        ]
        await subscriber.async_receive_event(
            create_event(
                f"other-id-{i}", f"event-id{i}", PERSON_EVENT, device_id=device_id2
            )
        )
        await hass.async_block_till_done()

    browse = await media_source.async_browse_media(hass, f"{const.URI_SCHEME}{DOMAIN}")
    assert len(browse.children) == 2
    assert browse.children[0].can_play
    assert browse.children[1].can_play
    browse = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{device1.id}"
    )
    assert len(browse.children) == 5
    browse = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{device2.id}"
    )
    assert len(browse.children) == 3


@pytest.fixture
def event_store() -> Generator[None, None, None]:
    """Persist changes to event store immediately."""
    with patch(
        "homeassistant.components.nest.media_source.STORAGE_SAVE_DELAY_SECONDS",
        new=0,
    ):
        yield


@pytest.mark.parametrize("device_traits", [BATTERY_CAMERA_TRAITS])
async def test_media_store_persistence(
    hass,
    auth,
    hass_client,
    event_store,
    subscriber,
    setup_platform,
    config_entry,
):
    """Test the disk backed media store persistence."""
    await setup_platform()

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device({(DOMAIN, DEVICE_ID)})
    assert device
    assert device.name == DEVICE_NAME

    auth.responses = [
        aiohttp.web.Response(body=IMAGE_BYTES_FROM_EVENT),
    ]
    event_timestamp = dt_util.now()
    await subscriber.async_receive_event(
        create_event_message(
            create_battery_event_data(MOTION_EVENT), timestamp=event_timestamp
        )
    )
    await hass.async_block_till_done()

    # Browse to event
    browse = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{device.id}"
    )
    assert len(browse.children) == 1
    assert browse.children[0].domain == DOMAIN
    event_timestamp_string = event_timestamp.strftime(DATE_STR_FORMAT)
    assert browse.children[0].title == f"Motion @ {event_timestamp_string}"
    assert not browse.children[0].can_expand
    assert browse.children[0].can_play
    event_identifier = browse.children[0].identifier

    media = await media_source.async_resolve_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{event_identifier}", None
    )
    assert media.url == f"/api/nest/event_media/{event_identifier}"
    assert media.mime_type == "video/mp4"

    # Fetch event media
    client = await hass_client()
    response = await client.get(media.url)
    assert response.status == HTTPStatus.OK, "Response not matched: %s" % response
    contents = await response.read()
    assert contents == IMAGE_BYTES_FROM_EVENT

    # Ensure event media store persists to disk
    await hass.async_block_till_done()

    # Unload the integration.
    assert config_entry.state == ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state == ConfigEntryState.NOT_LOADED

    # Now rebuild the entire integration and verify that all persisted storage
    # can be re-loaded from disk.
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device({(DOMAIN, DEVICE_ID)})
    assert device
    assert device.name == DEVICE_NAME

    # Verify event metadata exists
    browse = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{device.id}"
    )
    assert len(browse.children) == 1
    assert browse.children[0].domain == DOMAIN
    event_timestamp_string = event_timestamp.strftime(DATE_STR_FORMAT)
    assert browse.children[0].title == f"Motion @ {event_timestamp_string}"
    assert not browse.children[0].can_expand
    assert browse.children[0].can_play
    event_identifier = browse.children[0].identifier

    media = await media_source.async_resolve_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{event_identifier}", None
    )
    assert media.url == f"/api/nest/event_media/{event_identifier}"
    assert media.mime_type == "video/mp4"

    # Verify media exists
    response = await client.get(media.url)
    assert response.status == HTTPStatus.OK, "Response not matched: %s" % response
    contents = await response.read()
    assert contents == IMAGE_BYTES_FROM_EVENT


@pytest.mark.parametrize("device_traits", [BATTERY_CAMERA_TRAITS])
async def test_media_store_save_filesystem_error(
    hass, auth, hass_client, subscriber, setup_platform
):
    """Test a filesystem error writing event media."""
    await setup_platform()

    auth.responses = [
        aiohttp.web.Response(body=IMAGE_BYTES_FROM_EVENT),
    ]
    event_timestamp = dt_util.now()
    # The client fetches the media from the server, but has a failure when
    # persisting the media to disk.
    client = await hass_client()
    with patch("homeassistant.components.nest.media_source.open", side_effect=OSError):
        await subscriber.async_receive_event(
            create_event_message(
                create_battery_event_data(MOTION_EVENT),
                timestamp=event_timestamp,
            )
        )
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1
    camera = hass.states.get("camera.front")
    assert camera is not None

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device({(DOMAIN, DEVICE_ID)})
    assert device
    assert device.name == DEVICE_NAME

    browse = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{device.id}"
    )
    assert browse.domain == DOMAIN
    assert browse.identifier == device.id
    assert len(browse.children) == 1
    event = browse.children[0]

    media = await media_source.async_resolve_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{event.identifier}", None
    )
    assert media.url == f"/api/nest/event_media/{event.identifier}"
    assert media.mime_type == "video/mp4"

    # We fail to retrieve the media from the server since the origin filesystem op failed
    client = await hass_client()
    response = await client.get(media.url)
    assert response.status == HTTPStatus.NOT_FOUND, (
        "Response not matched: %s" % response
    )


async def test_media_store_load_filesystem_error(
    hass, auth, hass_client, subscriber, setup_platform
):
    """Test a filesystem error reading event media."""
    await setup_platform()

    assert len(hass.states.async_all()) == 1
    camera = hass.states.get("camera.front")
    assert camera is not None

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device({(DOMAIN, DEVICE_ID)})
    assert device
    assert device.name == DEVICE_NAME

    # Capture any events published
    received_events = async_capture_events(hass, NEST_EVENT)

    auth.responses = [
        aiohttp.web.Response(body=IMAGE_BYTES_FROM_EVENT),
    ]
    event_timestamp = dt_util.now()
    await subscriber.async_receive_event(
        create_event_message(
            create_battery_event_data(MOTION_EVENT),
            timestamp=event_timestamp,
        )
    )
    await hass.async_block_till_done()

    assert len(received_events) == 1
    received_event = received_events[0]
    assert received_event.data["device_id"] == device.id
    assert received_event.data["type"] == "camera_motion"
    event_identifier = received_event.data["nest_event_id"]

    client = await hass_client()

    # Fetch the media from the server, and simluate a failure reading from disk
    client = await hass_client()
    with patch("homeassistant.components.nest.media_source.open", side_effect=OSError):
        response = await client.get(
            f"/api/nest/event_media/{device.id}/{event_identifier}"
        )
        assert response.status == HTTPStatus.NOT_FOUND, (
            "Response not matched: %s" % response
        )


@pytest.mark.parametrize("device_traits,cache_size", [(BATTERY_CAMERA_TRAITS, 5)])
async def test_camera_event_media_eviction(
    hass, auth, hass_client, subscriber, setup_platform
):
    """Test media files getting evicted from the cache."""
    await setup_platform()

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device({(DOMAIN, DEVICE_ID)})
    assert device
    assert device.name == DEVICE_NAME

    # Browse to the device
    browse = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{device.id}"
    )
    assert browse.domain == DOMAIN
    assert browse.identifier == device.id
    assert browse.title == "Front: Recent Events"
    assert browse.can_expand

    # No events published yet
    assert len(browse.children) == 0

    event_timestamp = dt_util.now()
    for i in range(0, 7):
        auth.responses = [aiohttp.web.Response(body=f"image-bytes-{i}".encode())]
        ts = event_timestamp + datetime.timedelta(seconds=i)
        await subscriber.async_receive_event(
            create_event_message(
                create_battery_event_data(
                    MOTION_EVENT, event_session_id=f"event-session-{i}"
                ),
                timestamp=ts,
            )
        )
    await hass.async_block_till_done()

    # Cache is limited to 5 events removing media as the cache is filled
    browse = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{device.id}"
    )
    assert len(browse.children) == 5

    auth.responses = [
        aiohttp.web.Response(body=b"image-bytes-7"),
    ]
    ts = event_timestamp + datetime.timedelta(seconds=8)
    # Simulate a failure case removing the media on cache eviction
    with patch(
        "homeassistant.components.nest.media_source.os.remove", side_effect=OSError
    ) as mock_remove:
        await subscriber.async_receive_event(
            create_event_message(
                create_battery_event_data(
                    MOTION_EVENT, event_session_id="event-session-7"
                ),
                timestamp=ts,
            )
        )
        await hass.async_block_till_done()
        assert mock_remove.called

    browse = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{device.id}"
    )
    assert len(browse.children) == 5
    child_events = iter(browse.children)

    # Verify all other content is still persisted correctly
    client = await hass_client()
    for i in reversed(range(3, 8)):
        child_event = next(child_events)
        response = await client.get(f"/api/nest/event_media/{child_event.identifier}")
        assert response.status == HTTPStatus.OK, "Response not matched: %s" % response
        contents = await response.read()
        assert contents == f"image-bytes-{i}".encode()
        await hass.async_block_till_done()


async def test_camera_image_resize(hass, auth, hass_client, subscriber, setup_platform):
    """Test scaling a thumbnail for an event image."""
    await setup_platform()

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device({(DOMAIN, DEVICE_ID)})
    assert device
    assert device.name == DEVICE_NAME

    # Capture any events published
    received_events = async_capture_events(hass, NEST_EVENT)

    auth.responses = [
        aiohttp.web.json_response(GENERATE_IMAGE_URL_RESPONSE),
        aiohttp.web.Response(body=IMAGE_BYTES_FROM_EVENT),
    ]
    event_timestamp = dt_util.now()
    await subscriber.async_receive_event(
        create_event(
            EVENT_SESSION_ID,
            EVENT_ID,
            PERSON_EVENT,
            timestamp=event_timestamp,
        )
    )
    await hass.async_block_till_done()

    assert len(received_events) == 1
    received_event = received_events[0]
    assert received_event.data["device_id"] == device.id
    assert received_event.data["type"] == "camera_person"
    event_identifier = received_event.data["nest_event_id"]

    browse = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{device.id}/{event_identifier}"
    )
    assert browse.domain == DOMAIN
    assert browse.identifier == f"{device.id}/{event_identifier}"
    assert "Person" in browse.title
    assert not browse.can_expand
    assert not browse.children
    assert (
        browse.thumbnail
        == f"/api/nest/event_media/{device.id}/{event_identifier}/thumbnail"
    )

    client = await hass_client()
    response = await client.get(browse.thumbnail)
    assert response.status == HTTPStatus.OK, "Response not matched: %s" % response
    contents = await response.read()
    assert contents == IMAGE_BYTES_FROM_EVENT

    # The event thumbnail is used for the device thumbnail
    browse = await media_source.async_browse_media(hass, f"{const.URI_SCHEME}{DOMAIN}")
    assert browse.domain == DOMAIN
    assert len(browse.children) == 1
    assert browse.children[0].identifier == device.id
    assert browse.children[0].title == "Front: Recent Events"
    assert (
        browse.children[0].thumbnail
        == f"/api/nest/event_media/{device.id}/{event_identifier}/thumbnail"
    )
    assert browse.children[0].can_play

    # Browse to device. No thumbnail is needed for the device on the device page
    browse = await media_source.async_browse_media(
        hass, f"{const.URI_SCHEME}{DOMAIN}/{device.id}"
    )
    assert browse.domain == DOMAIN
    assert browse.identifier == device.id
    assert browse.title == "Front: Recent Events"
    assert not browse.thumbnail
    assert len(browse.children) == 1
