"""
Test for Nest sensors platform for the Smart Device Management API.

These tests fake out the subscriber/devicemanager, and are not using a real
pubsub subscriber.
"""

from google_nest_sdm.device import Device
from google_nest_sdm.device_manager import DeviceManager
from google_nest_sdm.event import EventMessage
import pytest

from homeassistant.components.sensor import ATTR_STATE_CLASS, STATE_CLASS_MEASUREMENT
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import FakeSubscriber, PlatformSetup

THERMOSTAT_TYPE = "sdm.devices.types.THERMOSTAT"


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to setup the platforms to test."""
    return ["sensor"]


async def test_thermostat_device(
    hass: HomeAssistant, device_manager: DeviceManager, setup_platform: PlatformSetup
):
    """Test a thermostat with temperature and humidity sensors."""
    device_manager.add_device(
        Device.MakeDevice(
            {
                "name": "some-device-id",
                "type": THERMOSTAT_TYPE,
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
    )
    await setup_platform()

    temperature = hass.states.get("sensor.my_sensor_temperature")
    assert temperature is not None
    assert temperature.state == "25.1"
    assert temperature.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == TEMP_CELSIUS
    assert temperature.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_TEMPERATURE
    assert temperature.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT

    humidity = hass.states.get("sensor.my_sensor_humidity")
    assert humidity is not None
    assert humidity.state == "35"
    assert humidity.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert humidity.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_HUMIDITY
    assert humidity.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT

    registry = er.async_get(hass)
    entry = registry.async_get("sensor.my_sensor_temperature")
    assert entry.unique_id == "some-device-id-temperature"
    assert entry.original_name == "My Sensor Temperature"
    assert entry.domain == "sensor"

    entry = registry.async_get("sensor.my_sensor_humidity")
    assert entry.unique_id == "some-device-id-humidity"
    assert entry.original_name == "My Sensor Humidity"
    assert entry.domain == "sensor"

    device_registry = dr.async_get(hass)
    device = device_registry.async_get(entry.device_id)
    assert device.name == "My Sensor"
    assert device.model == "Thermostat"
    assert device.identifiers == {("nest", "some-device-id")}


async def test_no_devices(hass: HomeAssistant, setup_platform: PlatformSetup):
    """Test no devices returned by the api."""
    await setup_platform()

    temperature = hass.states.get("sensor.my_sensor_temperature")
    assert temperature is None

    humidity = hass.states.get("sensor.my_sensor_humidity")
    assert humidity is None


async def test_device_no_sensor_traits(
    hass: HomeAssistant, device_manager: DeviceManager, setup_platform: PlatformSetup
) -> None:
    """Test a device with applicable sensor traits."""
    device_manager.add_device(
        Device.MakeDevice(
            {
                "name": "some-device-id",
                "type": THERMOSTAT_TYPE,
                "traits": {},
            },
            auth=None,
        )
    )
    await setup_platform()

    temperature = hass.states.get("sensor.my_sensor_temperature")
    assert temperature is None

    humidity = hass.states.get("sensor.my_sensor_humidity")
    assert humidity is None


async def test_device_name_from_structure(
    hass: HomeAssistant, device_manager: DeviceManager, setup_platform: PlatformSetup
) -> None:
    """Test a device without a custom name, inferring name from structure."""
    device_manager.add_device(
        Device.MakeDevice(
            {
                "name": "some-device-id",
                "type": THERMOSTAT_TYPE,
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
    )
    await setup_platform()

    temperature = hass.states.get("sensor.some_room_temperature")
    assert temperature is not None
    assert temperature.state == "25.2"


async def test_event_updates_sensor(
    hass: HomeAssistant,
    subscriber: FakeSubscriber,
    device_manager: DeviceManager,
    setup_platform: PlatformSetup,
) -> None:
    """Test a pubsub message received by subscriber to update temperature."""
    device_manager.add_device(
        Device.MakeDevice(
            {
                "name": "some-device-id",
                "type": THERMOSTAT_TYPE,
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
    )
    await setup_platform()

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
    await subscriber.async_receive_event(event)
    await hass.async_block_till_done()  # Process dispatch/update signal

    temperature = hass.states.get("sensor.my_sensor_temperature")
    assert temperature is not None
    assert temperature.state == "26.2"


async def test_device_with_unknown_type(
    hass: HomeAssistant, device_manager: DeviceManager, setup_platform: PlatformSetup
) -> None:
    """Test a device without a custom name, inferring name from structure."""
    device_manager.add_device(
        Device.MakeDevice(
            {
                "name": "some-device-id",
                "type": "some-unknown-type",
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
    )
    await setup_platform()

    temperature = hass.states.get("sensor.my_sensor_temperature")
    assert temperature is not None
    assert temperature.state == "25.1"

    registry = er.async_get(hass)
    entry = registry.async_get("sensor.my_sensor_temperature")
    assert entry.unique_id == "some-device-id-temperature"
    assert entry.original_name == "My Sensor Temperature"
    assert entry.domain == "sensor"

    device_registry = dr.async_get(hass)
    device = device_registry.async_get(entry.device_id)
    assert device.name == "My Sensor"
    assert device.model is None
    assert device.identifiers == {("nest", "some-device-id")}


async def test_temperature_rounding(
    hass: HomeAssistant, device_manager: DeviceManager, setup_platform: PlatformSetup
) -> None:
    """Test the rounding of overly precise temperatures."""
    device_manager.add_device(
        Device.MakeDevice(
            {
                "name": "some-device-id",
                "type": THERMOSTAT_TYPE,
                "traits": {
                    "sdm.devices.traits.Info": {
                        "customName": "My Sensor",
                    },
                    "sdm.devices.traits.Temperature": {
                        "ambientTemperatureCelsius": 25.15678,
                    },
                },
            },
            auth=None,
        )
    )
    await setup_platform()

    temperature = hass.states.get("sensor.my_sensor_temperature")
    assert temperature.state == "25.2"
