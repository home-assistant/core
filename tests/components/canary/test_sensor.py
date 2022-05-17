"""The tests for the Canary sensor platform."""
import datetime
from datetime import timedelta
from unittest.mock import patch

from homeassistant.components.canary.const import DOMAIN, MANUFACTURER
from homeassistant.components.canary.sensor import (
    ATTR_AIR_QUALITY,
    STATE_AIR_QUALITY_ABNORMAL,
    STATE_AIR_QUALITY_NORMAL,
    STATE_AIR_QUALITY_VERY_ABNORMAL,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    TEMP_CELSIUS,
)
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from . import mock_device, mock_entry, mock_location, mock_reading

from tests.common import async_fire_time_changed, mock_device_registry, mock_registry

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S+00:00"


async def test_sensors_pro(hass, canary) -> None:
    """Test the creation and values of the sensors for Canary Pro."""

    registry = mock_registry(hass)
    device_registry = mock_device_registry(hass)

    online_device_at_home = mock_device(20, "Dining Room", True, "Canary Pro")

    instance = canary.return_value
    instance.get_locations.return_value = [
        mock_location(100, "Home", True, devices=[online_device_at_home]),
    ]

    instance.get_latest_readings.return_value = [
        mock_reading("temperature", "21.12"),
        mock_reading("humidity", "50.46"),
        mock_reading("air_quality", "0.59"),
        mock_reading("wifi", "-61.2"),
    ]

    config = {DOMAIN: {"username": "test-username", "password": "test-password"}}
    with patch("homeassistant.components.canary.PLATFORMS", ["sensor"]):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    sensors = {
        "home_dining_room_temperature": (
            "20_temperature",
            "21.12",
            TEMP_CELSIUS,
            SensorDeviceClass.TEMPERATURE,
            None,
        ),
        "home_dining_room_humidity": (
            "20_humidity",
            "50.46",
            PERCENTAGE,
            SensorDeviceClass.HUMIDITY,
            None,
        ),
        "home_dining_room_air_quality": (
            "20_air_quality",
            "0.59",
            None,
            None,
            "mdi:weather-windy",
        ),
        "home_dining_room_wifi": (
            "20_wifi",
            "-61.2",
            SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
            SensorDeviceClass.SIGNAL_STRENGTH,
            None,
        ),
    }

    for (sensor_id, data) in sensors.items():
        entity_entry = registry.async_get(f"sensor.{sensor_id}")
        assert entity_entry
        assert entity_entry.original_device_class == data[3]
        assert entity_entry.unique_id == data[0]
        assert entity_entry.original_icon == data[4]

        state = hass.states.get(f"sensor.{sensor_id}")
        assert state
        assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == data[2]
        assert state.state == data[1]

    device = device_registry.async_get_device({(DOMAIN, "20")})
    assert device
    assert device.manufacturer == MANUFACTURER
    assert device.name == "Dining Room"
    assert device.model == "Canary Pro"


async def test_sensors_attributes_pro(hass, canary) -> None:
    """Test the creation and values of the sensors attributes for Canary Pro."""

    online_device_at_home = mock_device(20, "Dining Room", True, "Canary Pro")

    instance = canary.return_value
    instance.get_locations.return_value = [
        mock_location(100, "Home", True, devices=[online_device_at_home]),
    ]

    instance.get_latest_readings.return_value = [
        mock_reading("temperature", "21.12"),
        mock_reading("humidity", "50.46"),
        mock_reading("air_quality", "0.59"),
        mock_reading("wifi", "-81.2"),
    ]

    config = {DOMAIN: {"username": "test-username", "password": "test-password"}}
    with patch("homeassistant.components.canary.PLATFORMS", ["sensor"]):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    entity_id = "sensor.home_dining_room_air_quality"
    state1 = hass.states.get(entity_id)
    assert state1
    assert state1.state == "0.59"
    assert state1.attributes[ATTR_AIR_QUALITY] == STATE_AIR_QUALITY_ABNORMAL

    instance.get_latest_readings.return_value = [
        mock_reading("temperature", "21.12"),
        mock_reading("humidity", "50.46"),
        mock_reading("air_quality", "0.4"),
        mock_reading("wifi", "-81.2"),
    ]

    future = utcnow() + timedelta(seconds=30)
    async_fire_time_changed(hass, future)
    await async_update_entity(hass, entity_id)
    await hass.async_block_till_done()

    state2 = hass.states.get(entity_id)
    assert state2
    assert state2.state == "0.4"
    assert state2.attributes[ATTR_AIR_QUALITY] == STATE_AIR_QUALITY_VERY_ABNORMAL

    instance.get_latest_readings.return_value = [
        mock_reading("temperature", "21.12"),
        mock_reading("humidity", "50.46"),
        mock_reading("air_quality", "1.0"),
        mock_reading("wifi", "-61.2"),
    ]

    future += timedelta(seconds=30)
    async_fire_time_changed(hass, future)
    await async_update_entity(hass, entity_id)
    await hass.async_block_till_done()

    state3 = hass.states.get(entity_id)
    assert state3
    assert state3.state == "1.0"
    assert state3.attributes[ATTR_AIR_QUALITY] == STATE_AIR_QUALITY_NORMAL


async def test_sensors_flex(hass, canary) -> None:
    """Test the creation and values of the sensors for Canary Flex."""

    registry = mock_registry(hass)
    device_registry = mock_device_registry(hass)

    online_device_at_home = mock_device(20, "Dining Room", True, "Canary Flex")

    instance = canary.return_value
    instance.get_locations.return_value = [
        mock_location(100, "Home", True, devices=[online_device_at_home]),
    ]

    instance.get_latest_readings.return_value = [
        mock_reading("battery", "70.4567"),
        mock_reading("wifi", "-47"),
    ]

    config = {DOMAIN: {"username": "test-username", "password": "test-password"}}
    with patch("homeassistant.components.canary.PLATFORMS", ["sensor"]):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    sensors = {
        "home_dining_room_battery": (
            "20_battery",
            "70.46",
            PERCENTAGE,
            SensorDeviceClass.BATTERY,
            None,
        ),
        "home_dining_room_wifi": (
            "20_wifi",
            "-47.0",
            SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
            SensorDeviceClass.SIGNAL_STRENGTH,
            None,
        ),
    }

    for (sensor_id, data) in sensors.items():
        entity_entry = registry.async_get(f"sensor.{sensor_id}")
        assert entity_entry
        assert entity_entry.original_device_class == data[3]
        assert entity_entry.unique_id == data[0]
        assert entity_entry.original_icon == data[4]

        state = hass.states.get(f"sensor.{sensor_id}")
        assert state
        assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == data[2]
        assert state.state == data[1]

    device = device_registry.async_get_device({(DOMAIN, "20")})
    assert device
    assert device.manufacturer == MANUFACTURER
    assert device.name == "Dining Room"
    assert device.model == "Canary Flex"


async def test_sensors_view(hass, canary) -> None:
    """Test the creation and values of the sensors for Canary View."""

    registry = mock_registry(hass)
    device_registry = mock_device_registry(hass)

    online_device_at_home = mock_device(20, "Dining Room", True, "Canary View")

    instance = canary.return_value
    instance.get_locations.return_value = [
        mock_location(100, "Home", True, devices=[online_device_at_home]),
    ]

    instance.get_latest_readings.return_value = [
        mock_reading("wifi", "-77"),
    ]

    config = {DOMAIN: {"username": "test-username", "password": "test-password"}}
    with patch("homeassistant.components.canary.PLATFORMS", ["sensor"]):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    sensors = {
        "home_dining_room_wifi": (
            "20_wifi",
            "-77.0",
            SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
            SensorDeviceClass.SIGNAL_STRENGTH,
            None,
        ),
    }

    for (sensor_id, data) in sensors.items():
        entity_entry = registry.async_get(f"sensor.{sensor_id}")
        assert entity_entry
        assert entity_entry.original_device_class == data[3]
        assert entity_entry.unique_id == data[0]
        assert entity_entry.original_icon == data[4]

        state = hass.states.get(f"sensor.{sensor_id}")
        assert state
        assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == data[2]
        assert state.state == data[1]

    device = device_registry.async_get_device({(DOMAIN, "20")})
    assert device
    assert device.manufacturer == MANUFACTURER
    assert device.name == "Dining Room"
    assert device.model == "Canary View"


async def test_sensors_entries(hass, canary) -> None:
    """Test the creation and values of the sensors for Canary Entry data."""

    registry = mock_registry(hass)

    online_device_at_home = mock_device(20, "Dining Room", True, "Canary View", "12345")

    instance = canary.return_value
    instance.get_locations.return_value = [
        mock_location(100, "Home", True, devices=[online_device_at_home]),
    ]

    now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
    instance.get_entries.return_value = [
        mock_entry(None, uuids=["12345"], start_time=now),
        mock_entry(None, uuids=["12345"], start_time=now),
        mock_entry(None, uuids=["12345"], start_time=now),
        mock_entry(None, uuids=["65432"], start_time=now),
    ]

    instance.get_latest_entries.return_value = [
        mock_entry(None, uuids=["12345"], start_time=now),
    ]

    config = {DOMAIN: {"username": "test-username", "password": "test-password"}}
    with patch("homeassistant.components.canary.PLATFORMS", ["sensor"]):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    sensors = {
        "home_dining_room_entries_captured_today": (
            "20_entries_captured_today",
            "3",
            None,
            None,
            "mdi:file-video",
        ),
        "home_dining_room_last_entry_date": (
            "20_last_entry_date",
            now.strftime(DATETIME_FORMAT),
            None,
            SensorDeviceClass.TIMESTAMP,
            "mdi:run-fast",
        ),
    }

    for (sensor_id, data) in sensors.items():
        entity_entry = registry.async_get(f"sensor.{sensor_id}")
        assert entity_entry
        assert entity_entry.original_device_class == data[3]
        assert entity_entry.unique_id == data[0]
        assert entity_entry.original_icon == data[4]

        state = hass.states.get(f"sensor.{sensor_id}")
        assert state
        assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == data[2]
        assert state.state == data[1]


async def test_sensors_entries_with_no_data(hass, canary) -> None:
    """Test the creation and values of the sensors for Canary Entry data."""

    registry = mock_registry(hass)

    online_device_at_home = mock_device(21, "Living Room", True, "Canary View", "22345")

    instance = canary.return_value
    instance.get_locations.return_value = [
        mock_location(100, "Home", True, devices=[online_device_at_home]),
    ]

    instance.get_entries.return_value = []

    instance.get_latest_entries.return_value = []

    config = {DOMAIN: {"username": "test-username", "password": "test-password"}}
    with patch("homeassistant.components.canary.PLATFORMS", ["sensor"]):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    sensors = {
        "home_living_room_entries_captured_today": (
            "21_entries_captured_today",
            "0",
            None,
            None,
            "mdi:file-video",
        ),
        "home_living_room_last_entry_date": (
            "21_last_entry_date",
            "unknown",
            None,
            SensorDeviceClass.TIMESTAMP,
            "mdi:run-fast",
        ),
    }

    for (sensor_id, data) in sensors.items():
        entity_entry = registry.async_get(f"sensor.{sensor_id}")
        assert entity_entry
        assert entity_entry.original_device_class == data[3]
        assert entity_entry.unique_id == data[0]
        assert entity_entry.original_icon == data[4]

        state = hass.states.get(f"sensor.{sensor_id}")
        assert state
        assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == data[2]
        assert state.state == data[1]
