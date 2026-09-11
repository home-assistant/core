"""Test for Nest sensors platform for the Smart Device Management API.

These tests fake out the subscriber/devicemanager, and are not using a real
pubsub subscriber.
"""

from typing import Any
from unittest.mock import AsyncMock

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
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import DEVICE_ID, CreateDevice, PlatformSetup, create_nest_event


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

    temperature = hass.states.get("sensor.some_room_some_room_temperature")
    assert temperature is not None
    assert temperature.state == "25.2"


async def test_event_updates_sensor(
    hass: HomeAssistant,
    subscriber: AsyncMock,
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
    event = create_nest_event(
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


async def test_thermostat_fan_timer_sensor(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    create_device: CreateDevice,
    setup_platform: PlatformSetup,
) -> None:
    """Test a thermostat with a fan timer sensor."""
    create_device.create(
        {
            "sdm.devices.traits.Fan": {
                "timerMode": "ON",
                "timerTimeout": "2019-05-10T03:22:54Z",
            },
        }
    )
    await setup_platform()

    fan_timer = hass.states.get("sensor.my_sensor_fan_timer_timeout")
    assert fan_timer is not None
    assert fan_timer.state == "2019-05-10T03:22:54+00:00"
    assert fan_timer.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP
    assert fan_timer.attributes.get(ATTR_STATE_CLASS) is None
    assert fan_timer.attributes.get(ATTR_FRIENDLY_NAME) == "My Sensor Fan timer timeout"

    entry = entity_registry.async_get("sensor.my_sensor_fan_timer_timeout")
    assert entry.unique_id == f"{DEVICE_ID}-fan-timer"
    assert entry.domain == "sensor"

    device = device_registry.async_get(entry.device_id)
    assert device.name == "My Sensor"
    assert device.identifiers == {("nest", DEVICE_ID)}


async def test_thermostat_fan_timer_sensor_not_active(
    hass: HomeAssistant,
    create_device: CreateDevice,
    setup_platform: PlatformSetup,
) -> None:
    """Test a thermostat fan timer sensor when the timer is inactive."""
    create_device.create(
        {
            "sdm.devices.traits.Fan": {
                "timerMode": "OFF",
            },
        }
    )
    await setup_platform()

    fan_timer = hass.states.get("sensor.my_sensor_fan_timer_timeout")
    # When the timer is inactive, timer_timeout is None, rendering the sensor state unknown.
    assert fan_timer is not None
    assert fan_timer.state == STATE_UNKNOWN


async def test_thermostat_fan_timer_sensor_unsupported(
    hass: HomeAssistant,
    create_device: CreateDevice,
    setup_platform: PlatformSetup,
) -> None:
    """Test that the fan timer sensor is not created if the Fan trait lacks timer support."""
    create_device.create(
        {
            "sdm.devices.traits.Fan": {},
        }
    )
    await setup_platform()

    fan_timer = hass.states.get("sensor.my_sensor_fan_timer_timeout")
    # The sensor should not be created when timer_mode is unsupported/None
    assert fan_timer is None
