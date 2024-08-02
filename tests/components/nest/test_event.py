"""Test for Nest event platform."""

from typing import Any

from google_nest_sdm.event import EventMessage, EventType
from google_nest_sdm.traits import TraitType
import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from .common import DEVICE_ID, CreateDevice
from .conftest import FakeSubscriber, PlatformSetup

EVENT_SESSION_ID = "CjY5Y3VKaTZwR3o4Y19YbTVfMF..."
EVENT_ID = "FWWVQVUdGNUlTU2V4MGV2aTNXV..."
ENCODED_EVENT_ID = "WyJDalk1WTNWS2FUWndSM280WTE5WWJUVmZNRi4uLiIsICJGV1dWUVZVZEdOVWxUVTJWNE1HVjJhVE5YVi4uLiJd"


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture for platforms to setup."""
    return [Platform.EVENT]


@pytest.fixture
def device_type() -> str:
    """Fixture for the type of device under test."""
    return "sdm.devices.types.DOORBELL"


@pytest.fixture
async def device_traits() -> dict[str, Any]:
    """Fixture to set default device traits used when creating devices."""
    return {
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


def create_events(events: str) -> EventMessage:
    """Create an EventMessage for events."""
    return EventMessage.create_event(
        {
            "eventId": "some-event-id",
            "timestamp": utcnow().isoformat(timespec="seconds"),
            "resourceUpdate": {
                "name": DEVICE_ID,
                "events": {
                    event: {
                        "eventSessionId": EVENT_SESSION_ID,
                        "eventId": EVENT_ID,
                    }
                    for event in events
                },
            },
        },
        auth=None,
    )


@pytest.mark.parametrize(
    (
        "trait_types",
        "entity_id",
        "expected_attributes",
        "api_event_type",
        "expected_event_type",
    ),
    [
        (
            [TraitType.DOORBELL_CHIME, TraitType.CAMERA_MOTION],
            "event.front_chime",
            {
                "device_class": "doorbell",
                "event_types": ["doorbell_chime"],
                "friendly_name": "Front Chime",
            },
            EventType.DOORBELL_CHIME,
            "doorbell_chime",
        ),
        (
            [TraitType.CAMERA_MOTION, TraitType.CAMERA_PERSON, TraitType.CAMERA_SOUND],
            "event.front_motion",
            {
                "device_class": "motion",
                "event_types": ["camera_motion", "camera_person", "camera_sound"],
                "friendly_name": "Front Motion",
            },
            EventType.CAMERA_MOTION,
            "camera_motion",
        ),
        (
            [TraitType.CAMERA_MOTION, TraitType.CAMERA_PERSON, TraitType.CAMERA_SOUND],
            "event.front_motion",
            {
                "device_class": "motion",
                "event_types": ["camera_motion", "camera_person", "camera_sound"],
                "friendly_name": "Front Motion",
            },
            EventType.CAMERA_PERSON,
            "camera_person",
        ),
        (
            [TraitType.CAMERA_MOTION, TraitType.CAMERA_PERSON, TraitType.CAMERA_SOUND],
            "event.front_motion",
            {
                "device_class": "motion",
                "event_types": ["camera_motion", "camera_person", "camera_sound"],
                "friendly_name": "Front Motion",
            },
            EventType.CAMERA_SOUND,
            "camera_sound",
        ),
    ],
)
async def test_receive_events(
    hass: HomeAssistant,
    subscriber: FakeSubscriber,
    setup_platform: PlatformSetup,
    create_device: CreateDevice,
    trait_types: list[TraitType],
    entity_id: str,
    expected_attributes: dict[str, str],
    api_event_type: EventType,
    expected_event_type: str,
) -> None:
    """Test a pubsub message for a camera person event."""
    create_device.create(
        raw_traits={
            **{trait_type: {} for trait_type in trait_types},
            api_event_type: {},
        }
    )
    await setup_platform()

    state = hass.states.get(entity_id)
    assert state.state == "unknown"
    assert state.attributes == {
        **expected_attributes,
        "event_type": None,
    }

    await subscriber.async_receive_event(create_events([api_event_type]))
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state != "unknown"
    assert state.attributes == {
        **expected_attributes,
        "event_type": expected_event_type,
        "nest_event_id": ENCODED_EVENT_ID,
    }


@pytest.mark.parametrize(("trait_type"), [(TraitType.DOORBELL_CHIME)])
async def test_ignore_unrelated_event(
    hass: HomeAssistant,
    subscriber: FakeSubscriber,
    setup_platform: PlatformSetup,
    create_device: CreateDevice,
    trait_type: TraitType,
) -> None:
    """Test a pubsub message for a camera person event."""
    create_device.create(
        raw_traits={
            trait_type: {},
        }
    )
    await setup_platform()

    # Device does not have traits matching this event type
    await subscriber.async_receive_event(create_events([EventType.CAMERA_MOTION]))
    await hass.async_block_till_done()

    state = hass.states.get("event.front_chime")
    assert state.state == "unknown"
    assert state.attributes == {
        "device_class": "doorbell",
        "event_type": None,
        "event_types": ["doorbell_chime"],
        "friendly_name": "Front Chime",
    }
