"""Test for Nest binary sensor platform for the Smart Device Management API.

These tests fake out the subscriber/devicemanager, and are not using a real
pubsub subscriber.
"""

import datetime

from google_nest_sdm.device import Device
from google_nest_sdm.event import EventMessage

from homeassistant.components.nest import binary_sensor_sdm
from homeassistant.util.dt import utcnow

from .common import async_setup_sdm_platform

from tests.async_mock import patch
from tests.common import async_fire_time_changed

PLATFORM = "binary_sensor"
DOMAIN = "nest"
DEVICE_TYPE = "sdm.devices.types.DOORBELL"
DEVICE_ID = "some-device-id"


async def async_setup_binary_sensor(hass, traits={}):
    """Set up the platform and prerequisites."""
    devices = {
        "some-device-id": Device.MakeDevice(
            {
                "name": DEVICE_ID,
                "type": DEVICE_TYPE,
                "traits": traits,
            },
            auth=None,
        ),
    }
    return await async_setup_sdm_platform(hass, PLATFORM, devices)


async def test_doorbell_binary_sensor(hass):
    """Test a doorbell with multiple binary sensor types."""
    await async_setup_binary_sensor(
        hass,
        {
            "sdm.devices.traits.Info": {
                "customName": "Front",
            },
            "sdm.devices.traits.DoorbellChime": {},
            "sdm.devices.traits.CameraPerson": {},
            "sdm.devices.traits.CameraSound": {},
            "sdm.devices.traits.CameraMotion": {},
        },
    )

    assert len(hass.states.async_all()) == 4

    binary_sensor = hass.states.get("binary_sensor.front_doorbell_chime")
    assert binary_sensor is not None
    assert binary_sensor.state == "off"

    registry = await hass.helpers.entity_registry.async_get_registry()
    entry = registry.async_get("binary_sensor.front_doorbell_chime")
    assert entry.unique_id == "some-device-id-sdm.devices.traits.DoorbellChime"
    assert entry.original_name == "Front Doorbell Chime"
    assert entry.domain == "binary_sensor"

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get(entry.device_id)
    assert device.name == "Front"
    assert device.model == "Doorbell"
    assert device.identifiers == {("nest", DEVICE_ID)}

    binary_sensor = hass.states.get("binary_sensor.front_camera_motion")
    assert binary_sensor is not None
    assert binary_sensor.state == "off"

    binary_sensor = hass.states.get("binary_sensor.front_camera_person")
    assert binary_sensor is not None
    assert binary_sensor.state == "off"

    binary_sensor = hass.states.get("binary_sensor.front_camera_sound")
    assert binary_sensor is not None
    assert binary_sensor.state == "off"


async def test_event_updates_sensor(hass):
    """Test a pubsub message received by subscriber to update temperature."""
    subscriber = await async_setup_binary_sensor(
        hass,
        {
            "sdm.devices.traits.Info": {
                "customName": "Front",
            },
            "sdm.devices.traits.DoorbellChime": {},
        },
    )

    assert len(hass.states.async_all()) == 1

    binary_sensor = hass.states.get("binary_sensor.front_doorbell_chime")
    assert binary_sensor is not None
    assert binary_sensor.state == "off"

    # Simulate a pubsub message received by the subscriber with a trait update
    event = EventMessage(
        {
            "eventId": "some-event-id",
            "timestamp": utcnow().isoformat(timespec="seconds"),
            "resourceUpdate": {
                "name": DEVICE_ID,
                "events": {
                    "sdm.devices.events.DoorbellChime.Chime": {
                        "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                        "eventId": "FWWVQVUdGNUlTU2V4MGV2aTNXV...",
                    },
                },
            },
        },
        auth=None,
    )
    subscriber.receive_event(event)
    await hass.async_block_till_done()

    binary_sensor = hass.states.get("binary_sensor.front_doorbell_chime")
    assert binary_sensor is not None
    assert binary_sensor.state == "on"


async def test_event_filter_skips_update(hass):
    """Test an update for a different trait is ignored."""
    subscriber = await async_setup_binary_sensor(
        hass,
        {
            "sdm.devices.traits.Info": {
                "customName": "Front",
            },
            "sdm.devices.traits.DoorbellChime": {},
        },
    )

    assert len(hass.states.async_all()) == 1

    binary_sensor = hass.states.get("binary_sensor.front_doorbell_chime")
    assert binary_sensor is not None
    assert binary_sensor.state == "off"

    event = EventMessage(
        {
            "eventId": "some-event-id",
            "timestamp": utcnow().isoformat(timespec="seconds"),
            "resourceUpdate": {
                "name": DEVICE_ID,
                "events": {
                    "sdm.devices.events.CameraSound.Sound": {
                        "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                        "eventId": "FWWVQVUdGNUlTU2V4MGV2aTNXV...",
                    },
                },
            },
        },
        auth=None,
    )
    subscriber.receive_event(event)
    await hass.async_block_till_done()

    binary_sensor = hass.states.get("binary_sensor.front_doorbell_chime")
    assert binary_sensor is not None
    assert binary_sensor.state == "off"


async def test_event_on_off(hass):
    """Test an event that fires, then turns off."""
    subscriber = await async_setup_binary_sensor(
        hass,
        {
            "sdm.devices.traits.Info": {
                "customName": "Front",
            },
            "sdm.devices.traits.DoorbellChime": {},
        },
    )

    assert len(hass.states.async_all()) == 1

    binary_sensor = hass.states.get("binary_sensor.front_doorbell_chime")
    assert binary_sensor is not None
    assert binary_sensor.state == "off"

    now = utcnow()
    event = EventMessage(
        {
            "eventId": "some-event-id",
            "timestamp": now.isoformat(timespec="seconds"),
            "resourceUpdate": {
                "name": DEVICE_ID,
                "events": {
                    "sdm.devices.events.DoorbellChime.Chime": {
                        "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                        "eventId": "FWWVQVUdGNUlTU2V4MGV2aTNXV...",
                    },
                },
            },
        },
        auth=None,
    )
    with patch.object(binary_sensor_sdm, "EVENT_DURATION_SECS", 5):
        subscriber.receive_event(event)
        await hass.async_block_till_done()

    binary_sensor = hass.states.get("binary_sensor.front_doorbell_chime")
    assert binary_sensor is not None
    assert binary_sensor.state == "on"

    # An alarm is registered to turn off the sensor after EVENT_DURATION_SECS
    async_fire_time_changed(hass, utcnow() + datetime.timedelta(seconds=6))
    await hass.async_block_till_done()

    binary_sensor = hass.states.get("binary_sensor.front_doorbell_chime")
    assert binary_sensor is not None
    assert binary_sensor.state == "off"


async def test_remove(hass):
    """Test case where entities are removed."""
    subscriber = await async_setup_binary_sensor(
        hass,
        {
            "sdm.devices.traits.Info": {
                "customName": "Front",
            },
            "sdm.devices.traits.DoorbellChime": {},
        },
    )
    # Turn on the sensor, since it creates more callbacks that need to be
    # removed when the entity is removed
    event = EventMessage(
        {
            "eventId": "some-event-id",
            "timestamp": utcnow().isoformat(timespec="seconds"),
            "resourceUpdate": {
                "name": DEVICE_ID,
                "events": {
                    "sdm.devices.events.DoorbellChime.Chime": {
                        "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                        "eventId": "FWWVQVUdGNUlTU2V4MGV2aTNXV...",
                    },
                },
            },
        },
        auth=None,
    )
    subscriber.receive_event(event)
    await hass.async_block_till_done()

    binary_sensor = hass.states.get("binary_sensor.front_doorbell_chime")
    assert binary_sensor is not None
    assert binary_sensor.state == "on"

    for config_entry in hass.config_entries.async_entries(DOMAIN):
        await hass.config_entries.async_remove(config_entry.entry_id)
    assert len(hass.states.async_all()) == 0
