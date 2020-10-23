"""
Test for Nest sensors platform for the Smart Device Management API.

These tests fake out the subscriber/devicemanager, and are not using a real
pubsub subscriber.
"""

import time

from google_nest_sdm.device import Device
from google_nest_sdm.device_manager import DeviceManager
from google_nest_sdm.event import EventCallback, EventMessage
from google_nest_sdm.google_nest_subscriber import GoogleNestSubscriber

from homeassistant.components.nest import DOMAIN
from homeassistant.setup import async_setup_component

from tests.async_mock import patch
from tests.common import MockConfigEntry

PLATFORM = "sensor"

CONFIG = {
    "nest": {
        "client_id": "some-client-id",
        "client_secret": "some-client-secret",
        # Required fields for using SDM API
        "project_id": "some-project-id",
        "subscriber_id": "some-subscriber-id",
    },
}

CONFIG_ENTRY_DATA = {
    "sdm": {},  # Indicates new SDM API, not legacy API
    "auth_implementation": "local",
    "token": {
        "expires_at": time.time() + 86400,
        "access_token": {
            "token": "some-token",
        },
    },
}


class FakeDeviceManager(DeviceManager):
    """Fake DeviceManager that can supply a list of devices and structures."""

    def __init__(self, devices: dict, structures: dict):
        """Initialize FakeDeviceManager."""
        super().__init__()
        self._devices = devices

    @property
    def structures(self) -> dict:
        """Override structures with fake result."""
        return self._structures

    @property
    def devices(self) -> dict:
        """Override devices with fake result."""
        return self._devices


class FakeSubscriber(GoogleNestSubscriber):
    """Fake subscriber that supplies a FakeDeviceManager."""

    def __init__(self, device_manager: FakeDeviceManager):
        """Initialize Fake Subscriber."""
        self._device_manager = device_manager
        self._callback = None

    def set_update_callback(self, callback: EventCallback):
        """Capture the callback set by Home Assistant."""
        self._callback = callback

    async def start_async(self) -> DeviceManager:
        """Return the fake device manager."""
        return self._device_manager

    @property
    async def async_device_manager(self) -> DeviceManager:
        """Return the fake device manager."""
        return self._device_manager

    def stop_async(self):
        """No-op to stop the subscriber."""
        return None

    def receive_event(self, event_message: EventMessage):
        """Simulate a received pubsub message, invoked by tests."""
        # Update device state, then invoke HomeAssistant to refresh
        self._device_manager.handle_event(event_message)
        self._callback.handle_event(event_message)


async def setup_sensor(hass, devices={}, structures={}):
    """Set up the platform and prerequisites."""
    MockConfigEntry(domain=DOMAIN, data=CONFIG_ENTRY_DATA).add_to_hass(hass)
    device_manager = FakeDeviceManager(devices=devices, structures=structures)
    subscriber = FakeSubscriber(device_manager)
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation"
    ), patch("homeassistant.components.nest.PLATFORMS", [PLATFORM]), patch(
        "homeassistant.components.nest.GoogleNestSubscriber", return_value=subscriber
    ):
        assert await async_setup_component(hass, DOMAIN, CONFIG)
    await hass.async_block_till_done()
    return subscriber


async def test_thermostat_device(hass):
    """Test a thermostat with temperature and humidity sensors."""
    devices = {
        "some-device-id": Device.MakeDevice(
            {
                "name": "some-device-id",
                "type": "sdm.devices.types.Thermostat",
                "traits": {
                    "sdm.devices.traits.Info": {
                        "customName": "My Sensor",
                    },
                    "sdm.devices.traits.Temperature": {
                        "ambientTemperatureCelsius": 25.1,
                    },
                    "sdm.devices.traits.Humidity": {
                        "ambientHumidityPercent": 35.0,
                    },
                },
            },
            auth=None,
        )
    }
    await setup_sensor(hass, devices)

    temperature = hass.states.get("sensor.my_sensor_temperature")
    assert temperature is not None
    assert temperature.state == "25.1"

    humidity = hass.states.get("sensor.my_sensor_humidity")
    assert humidity is not None
    assert humidity.state == "35.0"


async def test_no_devices(hass):
    """Test no devices returned by the api."""
    await setup_sensor(hass)

    temperature = hass.states.get("sensor.my_sensor_temperature")
    assert temperature is None

    humidity = hass.states.get("sensor.my_sensor_humidity")
    assert humidity is None


async def test_device_no_sensor_traits(hass):
    """Test a device with applicable sensor traits."""
    devices = {
        "some-device-id": Device.MakeDevice(
            {
                "name": "some-device-id",
                "type": "sdm.devices.types.Thermostat",
                "traits": {},
            },
            auth=None,
        )
    }
    await setup_sensor(hass, devices)

    temperature = hass.states.get("sensor.my_sensor_temperature")
    assert temperature is None

    humidity = hass.states.get("sensor.my_sensor_humidity")
    assert humidity is None


async def test_device_name_from_structure(hass):
    """Test a device without a custom name, inferring name from structure."""
    devices = {
        "some-device-id": Device.MakeDevice(
            {
                "name": "some-device-id",
                "type": "sdm.devices.types.Thermostat",
                "traits": {
                    "sdm.devices.traits.Temperature": {
                        "ambientTemperatureCelsius": 25.2,
                    },
                },
                "parentRelations": [
                    {"parent": "some-structure-id", "displayName": "Some Room"}
                ],
            },
            auth=None,
        )
    }
    await setup_sensor(hass, devices)

    temperature = hass.states.get("sensor.some_room_temperature")
    assert temperature is not None
    assert temperature.state == "25.2"


async def test_event_updates_sensor(hass):
    """Test a pubsub message received by subscriber to update temperature."""
    devices = {
        "some-device-id": Device.MakeDevice(
            {
                "name": "some-device-id",
                "type": "sdm.devices.types.Thermostat",
                "traits": {
                    "sdm.devices.traits.Info": {
                        "customName": "My Sensor",
                    },
                    "sdm.devices.traits.Temperature": {
                        "ambientTemperatureCelsius": 25.1,
                    },
                },
            },
            auth=None,
        )
    }
    subscriber = await setup_sensor(hass, devices)

    temperature = hass.states.get("sensor.my_sensor_temperature")
    assert temperature is not None
    assert temperature.state == "25.1"

    # Simulate a pubsub message received by the subscriber with a trait update
    event = EventMessage(
        {
            "eventId": "some-event-id",
            "timestamp": "2019-01-01T00:00:01Z",
            "resourceUpdate": {
                "name": "some-device-id",
                "traits": {
                    "sdm.devices.traits.Temperature": {
                        "ambientTemperatureCelsius": 26.2,
                    },
                },
            },
        },
        auth=None,
    )
    subscriber.receive_event(event)
    await hass.async_block_till_done()  # Process dispatch/update signal

    temperature = hass.states.get("sensor.my_sensor_temperature")
    assert temperature is not None
    assert temperature.state == "26.2"
