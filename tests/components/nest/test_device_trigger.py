"""The tests for Nest device triggers."""

from typing import Any

from google_nest_sdm.event import EventMessage
import pytest
from pytest_unordered import unordered

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.nest import DOMAIN
from homeassistant.components.nest.events import NEST_EVENT
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from .common import DEVICE_ID, CreateDevice, FakeSubscriber, PlatformSetup

from tests.common import async_get_device_automations

DEVICE_NAME = "My Camera"
DATA_MESSAGE = {"message": "service-called"}


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to setup the platforms to test."""
    return ["camera"]


def make_camera(
    device_id, name: str = DEVICE_NAME, *, traits: dict[str, Any]
) -> dict[str, Any]:
    """Create a nest camera."""
    traits = traits.copy()
    traits.update(
        {
            "sdm.devices.traits.Info": {
                "customName": name,
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
    )
    return {
        "name": device_id,
        "type": "sdm.devices.types.CAMERA",
        "traits": traits,
    }


async def setup_automation(
    hass: HomeAssistant, device_id: str, trigger_type: str
) -> bool:
    """Set up an automation trigger for testing triggering."""
    return await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_id,
                        "type": trigger_type,
                    },
                    "action": {
                        "service": "test.automation",
                        "data": DATA_MESSAGE,
                    },
                },
            ]
        },
    )


async def test_get_triggers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    create_device: CreateDevice,
    setup_platform: PlatformSetup,
) -> None:
    """Test we get the expected triggers from a nest."""
    create_device.create(
        raw_data=make_camera(
            device_id=DEVICE_ID,
            traits={
                "sdm.devices.traits.CameraMotion": {},
                "sdm.devices.traits.CameraPerson": {},
            },
        )
    )
    await setup_platform()

    device_entry = device_registry.async_get_device(identifiers={("nest", DEVICE_ID)})

    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "camera_motion",
            "device_id": device_entry.id,
            "metadata": {},
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "camera_person",
            "device_id": device_entry.id,
            "metadata": {},
        },
    ]
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert triggers == unordered(expected_triggers)


async def test_multiple_devices(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    create_device: CreateDevice,
    setup_platform: PlatformSetup,
) -> None:
    """Test we get the expected triggers from a nest."""
    create_device.create(
        raw_data=make_camera(
            device_id="device-id-1",
            name="Camera 1",
            traits={
                "sdm.devices.traits.CameraSound": {},
            },
        )
    )
    create_device.create(
        raw_data=make_camera(
            device_id="device-id-2",
            name="Camera 2",
            traits={
                "sdm.devices.traits.DoorbellChime": {},
            },
        )
    )
    await setup_platform()

    entry1 = entity_registry.async_get("camera.camera_1")
    assert entry1.unique_id == "device-id-1-camera"
    entry2 = entity_registry.async_get("camera.camera_2")
    assert entry2.unique_id == "device-id-2-camera"

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, entry1.device_id
    )
    assert len(triggers) == 1
    assert triggers[0] == {
        "platform": "device",
        "domain": DOMAIN,
        "type": "camera_sound",
        "device_id": entry1.device_id,
        "metadata": {},
    }

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, entry2.device_id
    )
    assert len(triggers) == 1
    assert triggers[0] == {
        "platform": "device",
        "domain": DOMAIN,
        "type": "doorbell_chime",
        "device_id": entry2.device_id,
        "metadata": {},
    }


async def test_triggers_for_invalid_device_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    create_device: CreateDevice,
    setup_platform: PlatformSetup,
) -> None:
    """Get triggers for a device not found in the API."""
    create_device.create(
        raw_data=make_camera(
            device_id=DEVICE_ID,
            traits={
                "sdm.devices.traits.CameraMotion": {},
                "sdm.devices.traits.CameraPerson": {},
            },
        )
    )
    await setup_platform()

    device_entry = device_registry.async_get_device(identifiers={("nest", DEVICE_ID)})
    assert device_entry is not None

    # Create an additional device that does not exist.  Fetching supported
    # triggers for an unknown device will fail.
    assert len(device_entry.config_entries) == 1
    config_entry_id = next(iter(device_entry.config_entries))
    device_entry_2 = device_registry.async_get_or_create(
        config_entry_id=config_entry_id, identifiers={(DOMAIN, "some-unknown-nest-id")}
    )
    assert device_entry_2 is not None

    with pytest.raises(InvalidDeviceAutomationConfig):
        await async_get_device_automations(
            hass, DeviceAutomationType.TRIGGER, device_entry_2.id
        )


async def test_no_triggers(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    create_device: CreateDevice,
    setup_platform: PlatformSetup,
) -> None:
    """Test we get the expected triggers from a nest."""
    create_device.create(raw_data=make_camera(device_id=DEVICE_ID, traits={}))
    await setup_platform()

    entry = entity_registry.async_get("camera.my_camera")
    assert entry.unique_id == f"{DEVICE_ID}-camera"

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, entry.device_id
    )
    assert triggers == []


async def test_fires_on_camera_motion(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    create_device: CreateDevice,
    setup_platform: PlatformSetup,
    service_calls: list[ServiceCall],
) -> None:
    """Test camera_motion triggers firing."""
    create_device.create(
        raw_data=make_camera(
            device_id=DEVICE_ID,
            traits={
                "sdm.devices.traits.CameraMotion": {},
                "sdm.devices.traits.CameraPerson": {},
            },
        )
    )
    await setup_platform()

    device_entry = device_registry.async_get_device(identifiers={("nest", DEVICE_ID)})

    assert await setup_automation(hass, device_entry.id, "camera_motion")

    message = {
        "device_id": device_entry.id,
        "type": "camera_motion",
        "timestamp": utcnow(),
    }
    hass.bus.async_fire(NEST_EVENT, message)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data == DATA_MESSAGE


async def test_fires_on_camera_person(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    create_device: CreateDevice,
    setup_platform: PlatformSetup,
    service_calls: list[ServiceCall],
) -> None:
    """Test camera_person triggers firing."""
    create_device.create(
        raw_data=make_camera(
            device_id=DEVICE_ID,
            traits={
                "sdm.devices.traits.CameraMotion": {},
                "sdm.devices.traits.CameraPerson": {},
            },
        )
    )
    await setup_platform()

    device_entry = device_registry.async_get_device(identifiers={("nest", DEVICE_ID)})

    assert await setup_automation(hass, device_entry.id, "camera_person")

    message = {
        "device_id": device_entry.id,
        "type": "camera_person",
        "timestamp": utcnow(),
    }
    hass.bus.async_fire(NEST_EVENT, message)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data == DATA_MESSAGE


async def test_fires_on_camera_sound(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    create_device: CreateDevice,
    setup_platform: PlatformSetup,
    service_calls: list[ServiceCall],
) -> None:
    """Test camera_sound triggers firing."""
    create_device.create(
        raw_data=make_camera(
            device_id=DEVICE_ID,
            traits={
                "sdm.devices.traits.CameraMotion": {},
                "sdm.devices.traits.CameraSound": {},
            },
        )
    )
    await setup_platform()

    device_entry = device_registry.async_get_device(identifiers={("nest", DEVICE_ID)})

    assert await setup_automation(hass, device_entry.id, "camera_sound")

    message = {
        "device_id": device_entry.id,
        "type": "camera_sound",
        "timestamp": utcnow(),
    }
    hass.bus.async_fire(NEST_EVENT, message)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data == DATA_MESSAGE


async def test_fires_on_doorbell_chime(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    create_device: CreateDevice,
    setup_platform: PlatformSetup,
    service_calls: list[ServiceCall],
) -> None:
    """Test doorbell_chime triggers firing."""
    create_device.create(
        raw_data=make_camera(
            device_id=DEVICE_ID,
            traits={
                "sdm.devices.traits.CameraMotion": {},
                "sdm.devices.traits.DoorbellChime": {},
            },
        )
    )
    await setup_platform()

    device_entry = device_registry.async_get_device(identifiers={("nest", DEVICE_ID)})

    assert await setup_automation(hass, device_entry.id, "doorbell_chime")

    message = {
        "device_id": device_entry.id,
        "type": "doorbell_chime",
        "timestamp": utcnow(),
    }
    hass.bus.async_fire(NEST_EVENT, message)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data == DATA_MESSAGE


async def test_trigger_for_wrong_device_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    create_device: CreateDevice,
    setup_platform: PlatformSetup,
    service_calls: list[ServiceCall],
) -> None:
    """Test messages for the wrong device are ignored."""
    create_device.create(
        raw_data=make_camera(
            device_id=DEVICE_ID,
            traits={
                "sdm.devices.traits.CameraMotion": {},
                "sdm.devices.traits.CameraPerson": {},
            },
        )
    )
    await setup_platform()

    device_entry = device_registry.async_get_device(identifiers={("nest", DEVICE_ID)})

    assert await setup_automation(hass, device_entry.id, "camera_motion")

    message = {
        "device_id": "wrong-device-id",
        "type": "camera_motion",
        "timestamp": utcnow(),
    }
    hass.bus.async_fire(NEST_EVENT, message)
    await hass.async_block_till_done()
    assert len(service_calls) == 0


async def test_trigger_for_wrong_event_type(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    create_device: CreateDevice,
    setup_platform: PlatformSetup,
    service_calls: list[ServiceCall],
) -> None:
    """Test that messages for the wrong event type are ignored."""
    create_device.create(
        raw_data=make_camera(
            device_id=DEVICE_ID,
            traits={
                "sdm.devices.traits.CameraMotion": {},
                "sdm.devices.traits.CameraPerson": {},
            },
        )
    )
    await setup_platform()

    device_entry = device_registry.async_get_device(identifiers={("nest", DEVICE_ID)})

    assert await setup_automation(hass, device_entry.id, "camera_motion")

    message = {
        "device_id": device_entry.id,
        "type": "wrong-event-type",
        "timestamp": utcnow(),
    }
    hass.bus.async_fire(NEST_EVENT, message)
    await hass.async_block_till_done()
    assert len(service_calls) == 0


async def test_subscriber_automation(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
    create_device: CreateDevice,
    setup_platform: PlatformSetup,
    subscriber: FakeSubscriber,
) -> None:
    """Test end to end subscriber triggers automation."""
    create_device.create(
        raw_data=make_camera(
            device_id=DEVICE_ID,
            traits={
                "sdm.devices.traits.CameraMotion": {},
            },
        )
    )
    await setup_platform()

    device_entry = device_registry.async_get_device(identifiers={("nest", DEVICE_ID)})

    assert await setup_automation(hass, device_entry.id, "camera_motion")

    # Simulate a pubsub message received by the subscriber with a motion event
    event = EventMessage.create_event(
        {
            "eventId": "some-event-id",
            "timestamp": "2019-01-01T00:00:01Z",
            "resourceUpdate": {
                "name": DEVICE_ID,
                "events": {
                    "sdm.devices.events.CameraMotion.Motion": {
                        "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                        "eventId": "FWWVQVUdGNUlTU2V4MGV2aTNXV...",
                    },
                },
            },
        },
        auth=None,
    )
    await subscriber.async_receive_event(event)
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data == DATA_MESSAGE
