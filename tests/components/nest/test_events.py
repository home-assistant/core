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
PLATFORM = "sensor"
NEST_EVENT = "nest_event"


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
    return await async_setup_sdm_platform(hass, PLATFORM, devices=devices)


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

    count = 0

    def handle_event(event):
        nonlocal count
        count += 1
        assert "CjY5Y3VKaTZwR3o4Y19YbTVfMF..." == event.data.event_session_id
        assert "FWWVQVUdGNUlTU2V4MGV2aTNXV..." == event.data.event_id

    hass.bus.async_listen("nest_event", handle_event)

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
