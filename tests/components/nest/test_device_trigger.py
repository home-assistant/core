"""The tests for Nest device triggers."""
from google_nest_sdm.device import Device
from google_nest_sdm.event import EventMessage
import pytest

import homeassistant.components.automation as automation
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.nest import DOMAIN
from homeassistant.components.nest.events import NEST_EVENT
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from .common import async_setup_sdm_platform

from tests.common import (
    assert_lists_same,
    async_get_device_automations,
    async_mock_service,
)

DEVICE_ID = "some-device-id"
DEVICE_NAME = "My Camera"
DATA_MESSAGE = {"message": "service-called"}


def make_camera(device_id, name=DEVICE_NAME, traits={}):
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
    return Device.MakeDevice(
        {
            "name": device_id,
            "type": "sdm.devices.types.CAMERA",
            "traits": traits,
        },
        auth=None,
    )


async def async_setup_camera(hass, devices=None):
    """Set up the platform and prerequisites for testing available triggers."""
    if not devices:
        devices = {DEVICE_ID: make_camera(device_id=DEVICE_ID)}
    return await async_setup_sdm_platform(hass, "camera", devices)


async def setup_automation(hass, device_id, trigger_type):
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


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_get_triggers(hass):
    """Test we get the expected triggers from a nest."""
    camera = make_camera(
        device_id=DEVICE_ID,
        traits={
            "sdm.devices.traits.CameraMotion": {},
            "sdm.devices.traits.CameraPerson": {},
        },
    )
    await async_setup_camera(hass, {DEVICE_ID: camera})

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device_entry = device_registry.async_get_device(
        {("nest", DEVICE_ID)}, connections={}
    )

    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "camera_motion",
            "device_id": device_entry.id,
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "camera_person",
            "device_id": device_entry.id,
        },
    ]
    triggers = await async_get_device_automations(hass, "trigger", device_entry.id)
    assert_lists_same(triggers, expected_triggers)


async def test_multiple_devices(hass):
    """Test we get the expected triggers from a nest."""
    camera1 = make_camera(
        device_id="device-id-1",
        name="Camera 1",
        traits={
            "sdm.devices.traits.CameraSound": {},
        },
    )
    camera2 = make_camera(
        device_id="device-id-2",
        name="Camera 2",
        traits={
            "sdm.devices.traits.DoorbellChime": {},
        },
    )
    await async_setup_camera(hass, {"device-id-1": camera1, "device-id-2": camera2})

    registry = await hass.helpers.entity_registry.async_get_registry()
    entry1 = registry.async_get("camera.camera_1")
    assert entry1.unique_id == "device-id-1-camera"
    entry2 = registry.async_get("camera.camera_2")
    assert entry2.unique_id == "device-id-2-camera"

    triggers = await async_get_device_automations(hass, "trigger", entry1.device_id)
    assert len(triggers) == 1
    assert triggers[0] == {
        "platform": "device",
        "domain": DOMAIN,
        "type": "camera_sound",
        "device_id": entry1.device_id,
    }

    triggers = await async_get_device_automations(hass, "trigger", entry2.device_id)
    assert len(triggers) == 1
    assert triggers[0] == {
        "platform": "device",
        "domain": DOMAIN,
        "type": "doorbell_chime",
        "device_id": entry2.device_id,
    }


async def test_triggers_for_invalid_device_id(hass):
    """Get triggers for a device not found in the API."""
    camera = make_camera(
        device_id=DEVICE_ID,
        traits={
            "sdm.devices.traits.CameraMotion": {},
            "sdm.devices.traits.CameraPerson": {},
        },
    )
    await async_setup_camera(hass, {DEVICE_ID: camera})

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device_entry = device_registry.async_get_device(
        {("nest", DEVICE_ID)}, connections={}
    )
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
        await async_get_device_automations(hass, "trigger", device_entry_2.id)


async def test_no_triggers(hass):
    """Test we get the expected triggers from a nest."""
    camera = make_camera(device_id=DEVICE_ID, traits={})
    await async_setup_camera(hass, {DEVICE_ID: camera})

    registry = await hass.helpers.entity_registry.async_get_registry()
    entry = registry.async_get("camera.my_camera")
    assert entry.unique_id == "some-device-id-camera"

    triggers = await async_get_device_automations(hass, "trigger", entry.device_id)
    assert triggers == []


async def test_fires_on_camera_motion(hass, calls):
    """Test camera_motion triggers firing."""
    assert await setup_automation(hass, DEVICE_ID, "camera_motion")

    message = {"device_id": DEVICE_ID, "type": "camera_motion", "timestamp": utcnow()}
    hass.bus.async_fire(NEST_EVENT, message)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data == DATA_MESSAGE


async def test_fires_on_camera_person(hass, calls):
    """Test camera_person triggers firing."""
    assert await setup_automation(hass, DEVICE_ID, "camera_person")

    message = {"device_id": DEVICE_ID, "type": "camera_person", "timestamp": utcnow()}
    hass.bus.async_fire(NEST_EVENT, message)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data == DATA_MESSAGE


async def test_fires_on_camera_sound(hass, calls):
    """Test camera_person triggers firing."""
    assert await setup_automation(hass, DEVICE_ID, "camera_sound")

    message = {"device_id": DEVICE_ID, "type": "camera_sound", "timestamp": utcnow()}
    hass.bus.async_fire(NEST_EVENT, message)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data == DATA_MESSAGE


async def test_fires_on_doorbell_chime(hass, calls):
    """Test doorbell_chime triggers firing."""
    assert await setup_automation(hass, DEVICE_ID, "doorbell_chime")

    message = {"device_id": DEVICE_ID, "type": "doorbell_chime", "timestamp": utcnow()}
    hass.bus.async_fire(NEST_EVENT, message)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data == DATA_MESSAGE


async def test_trigger_for_wrong_device_id(hass, calls):
    """Test for turn_on and turn_off triggers firing."""
    assert await setup_automation(hass, DEVICE_ID, "camera_motion")

    message = {
        "device_id": "wrong-device-id",
        "type": "camera_motion",
        "timestamp": utcnow(),
    }
    hass.bus.async_fire(NEST_EVENT, message)
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_trigger_for_wrong_event_type(hass, calls):
    """Test for turn_on and turn_off triggers firing."""
    assert await setup_automation(hass, DEVICE_ID, "camera_motion")

    message = {
        "device_id": DEVICE_ID,
        "type": "wrong-event-type",
        "timestamp": utcnow(),
    }
    hass.bus.async_fire(NEST_EVENT, message)
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_subscriber_automation(hass, calls):
    """Test end to end subscriber triggers automation."""
    camera = make_camera(
        device_id=DEVICE_ID,
        traits={
            "sdm.devices.traits.CameraMotion": {},
        },
    )
    subscriber = await async_setup_camera(hass, {DEVICE_ID: camera})

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device_entry = device_registry.async_get_device(
        {("nest", DEVICE_ID)}, connections={}
    )

    assert await setup_automation(hass, device_entry.id, "camera_motion")

    # Simulate a pubsub message received by the subscriber with a motion event
    event = EventMessage(
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

    assert len(calls) == 1
    assert calls[0].data == DATA_MESSAGE
