"""Test for Nest sensors platform for the Smart Device Management API.

These tests fake out the subscriber/devicemanager, and are not using a real
pubsub subscriber.
"""

from typing import Any

from google_nest_sdm.event import EventMessage
import pytest

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    STATE_UNAVAILABLE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import DEVICE_ID, CreateDevice, FakeSubscriber, PlatformSetup


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to setup the platforms to test."""
    return ["sensor"]


@pytest.fixture
def device_traits() -> dict[str, Any]:
    """Fixture that sets default traits used for devices."""
    return {"sdm.devices.traits.Info": {"customName": "My Sensor"}}


async def test_thermostat_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    create_device: CreateDevice,
    setup_platform: PlatformSetup,
) -> None:
    """Test a thermostat with temperature and humidity sensors."""
    create_device.create(
        {
            "sdm.devices.traits.Temperature": {
                "ambientTemperatureCelsius": 25.1,
            },
            "sdm.devices.traits.Humidity": {
                "ambientHumidityPercent": 35.0,
            },
        }
    )
    await setup_platform()

    temperature = hass.states.get("sensor.my_sensor_temperature")
    assert temperature is not None
    assert temperature.state == "25.1"
    assert (
        temperature.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == UnitOfTemperature.CELSIUS
    )
    assert (
        temperature.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TEMPERATURE
    )
    assert temperature.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert temperature.attributes.get(ATTR_FRIENDLY_NAME) == "My Sensor Temperature"

    humidity = hass.states.get("sensor.my_sensor_humidity")
    assert humidity is not None
    assert humidity.state == "35"
    assert humidity.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert humidity.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.HUMIDITY
    assert humidity.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert humidity.attributes.get(ATTR_FRIENDLY_NAME) == "My Sensor Humidity"

    entry = entity_registry.async_get("sensor.my_sensor_temperature")
    assert entry.unique_id == f"{DEVICE_ID}-temperature"
    assert entry.domain == "sensor"

    entry = entity_registry.async_get("sensor.my_sensor_humidity")
    assert entry.unique_id == f"{DEVICE_ID}-humidity"
    assert entry.domain == "sensor"

    device = device_registry.async_get(entry.device_id)
    assert device.name == "My Sensor"
    assert device.model == "Thermostat"
    assert device.identifiers == {("nest", DEVICE_ID)}


async def test_thermostat_device_available(
    hass: HomeAssistant, create_device: CreateDevice, setup_platform: PlatformSetup
) -> None:
    """Test a thermostat with temperature and humidity sensors that is Online."""
    create_device.create(
        {
            "sdm.devices.traits.Temperature": {
                "ambientTemperatureCelsius": 25.1,
            },
            "sdm.devices.traits.Humidity": {
                "ambientHumidityPercent": 35.0,
            },
            "sdm.devices.traits.Connectivity": {"status": "ONLINE"},
        }
    )
    await setup_platform()

    temperature = hass.states.get("sensor.my_sensor_temperature")
    assert temperature is not None
    assert temperature.state == "25.1"

    humidity = hass.states.get("sensor.my_sensor_humidity")
    assert humidity is not None
    assert humidity.state == "35"


async def test_thermostat_device_unavailable(
    hass: HomeAssistant, create_device: CreateDevice, setup_platform: PlatformSetup
) -> None:
    """Test a thermostat with temperature and humidity sensors that is Offline."""
    create_device.create(
        {
            "sdm.devices.traits.Temperature": {
                "ambientTemperatureCelsius": 25.1,
            },
            "sdm.devices.traits.Humidity": {
                "ambientHumidityPercent": 35.0,
            },
            "sdm.devices.traits.Connectivity": {"status": "OFFLINE"},
        }
    )
    await setup_platform()

    temperature = hass.states.get("sensor.my_sensor_temperature")
    assert temperature is not None
    assert temperature.state == STATE_UNAVAILABLE

    humidity = hass.states.get("sensor.my_sensor_humidity")
    assert humidity is not None
    assert humidity.state == STATE_UNAVAILABLE


async def test_no_devices(hass: HomeAssistant, setup_platform: PlatformSetup) -> None:
    """Test no devices returned by the api."""
    await setup_platform()

    temperature = hass.states.get("sensor.my_sensor_temperature")
    assert temperature is None

    humidity = hass.states.get("sensor.my_sensor_humidity")
    assert humidity is None


async def test_device_no_sensor_traits(
    hass: HomeAssistant, create_device: CreateDevice, setup_platform: PlatformSetup
) -> None:
    """Test a device with applicable sensor traits."""
    create_device.create({})
    await setup_platform()

    temperature = hass.states.get("sensor.my_sensor_temperature")
    assert temperature is None

    humidity = hass.states.get("sensor.my_sensor_humidity")
    assert humidity is None


@pytest.mark.parametrize("device_traits", [{}])  # Disable default name
async def test_device_name_from_structure(
    hass: HomeAssistant, create_device: CreateDevice, setup_platform: PlatformSetup
) -> None:
    """Test a device without a custom name, inferring name from structure."""
    create_device.create(
        raw_traits={
            "sdm.devices.traits.Temperature": {
                "ambientTemperatureCelsius": 25.2,
            },
        },
        raw_data={
            "parentRelations": [
                {"parent": "some-structure-id", "displayName": "Some Room"}
            ],
        },
    )
    await setup_platform()

    temperature = hass.states.get("sensor.some_room_temperature")
    assert temperature is not None
    assert temperature.state == "25.2"


async def test_event_updates_sensor(
    hass: HomeAssistant,
    subscriber: FakeSubscriber,
    create_device: CreateDevice,
    setup_platform: PlatformSetup,
) -> None:
    """Test a pubsub message received by subscriber to update temperature."""
    create_device.create(
        {
            "sdm.devices.traits.Temperature": {
                "ambientTemperatureCelsius": 25.1,
            },
        }
    )
    await setup_platform()

    temperature = hass.states.get("sensor.my_sensor_temperature")
    assert temperature is not None
    assert temperature.state == "25.1"

    # Simulate a pubsub message received by the subscriber with a trait update
    event = EventMessage.create_event(
        {
            "eventId": "some-event-id",
            "timestamp": "2019-01-01T00:00:01Z",
            "resourceUpdate": {
                "name": DEVICE_ID,
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


@pytest.mark.parametrize("device_type", ["some-unknown-type"])
async def test_device_with_unknown_type(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    create_device: CreateDevice,
    setup_platform: PlatformSetup,
) -> None:
    """Test a device without a custom name, inferring name from structure."""
    create_device.create(
        {
            "sdm.devices.traits.Temperature": {
                "ambientTemperatureCelsius": 25.1,
            },
        }
    )
    await setup_platform()

    temperature = hass.states.get("sensor.my_sensor_temperature")
    assert temperature is not None
    assert temperature.state == "25.1"
    assert temperature.attributes.get(ATTR_FRIENDLY_NAME) == "My Sensor Temperature"

    entry = entity_registry.async_get("sensor.my_sensor_temperature")
    assert entry.unique_id == f"{DEVICE_ID}-temperature"
    assert entry.domain == "sensor"

    device = device_registry.async_get(entry.device_id)
    assert device.name == "My Sensor"
    assert device.model is None
    assert device.identifiers == {("nest", DEVICE_ID)}


async def test_temperature_rounding(
    hass: HomeAssistant, create_device: CreateDevice, setup_platform: PlatformSetup
) -> None:
    """Test the rounding of overly precise temperatures."""
    create_device.create(
        {
            "sdm.devices.traits.Temperature": {
                "ambientTemperatureCelsius": 25.15678,
            },
        }
    )
    await setup_platform()

    temperature = hass.states.get("sensor.my_sensor_temperature")
    assert temperature.state == "25.2"
