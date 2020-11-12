"""Test for Nest binary sensor platform for the Smart Device Management API.

These tests fake out the subscriber/devicemanager, and are not using a real
pubsub subscriber.
"""

from google_nest_sdm.device import Device
from google_nest_sdm.event import EventMessage

from homeassistant.util.dt import utcnow

from .common import async_setup_sdm_platform

DOMAIN = "nest"
DEVICE_TYPE = "sdm.devices.types.DOORBELL"
DEVICE_ID = "some-device-id"


async def async_setup_devices(hass, traits={}):
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
    return await async_setup_sdm_platform(hass, devices=devices)


async def test_event_update_event(hass):
    """Test a pubsub message received by subscriber to update temperature."""
    subscriber = await async_setup_devices(
        hass,
        {
            "sdm.devices.traits.Info": {
                "customName": "Front",
            },
            "sdm.devices.traits.DoorbellChime": {},
        },
    )

    assert len(hass.states.async_all()) == 1

    count = 0

    def handle_event(event):
        nonlocal count
        count += 1
        assert event.data.get("def") == "abc"

    hass.bus.listen("nest_event", handle_event)

    assert count == 0

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

    assert count == 1


async def test_event_filter_skips_update(hass):
    """Test an update for a different trait is ignored."""
    subscriber = await async_setup_devices(
        hass,
        {
            "sdm.devices.traits.Info": {
                "customName": "Front",
            },
            "sdm.devices.traits.DoorbellChime": {},
        },
    )

    count = 0

    def handle_event(event):
        nonlocal count
        count += 1

    hass.bus.listen("nest_event", handle_event)

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

    assert count == 0


async def test_remove(hass):
    """Test case where entities are removed."""
    subscriber = await async_setup_devices(
        hass,
        {
            "sdm.devices.traits.Info": {
                "customName": "Front",
            },
            "sdm.devices.traits.DoorbellChime": {},
        },
    )

    count = 0

    def handle_event(event):
        nonlocal count
        count += 1

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

    assert count == 0

    for config_entry in hass.config_entries.async_entries(DOMAIN):
        await hass.config_entries.async_remove(config_entry.entry_id)
    assert len(hass.states.async_all()) == 0
