"""The tests for the Canary sensor platform."""
from homeassistant.components.canary import DOMAIN
from homeassistant.components.canary.sensor import (
    ATTR_AIR_QUALITY,
    STATE_AIR_QUALITY_ABNORMAL,
    STATE_AIR_QUALITY_NORMAL,
    STATE_AIR_QUALITY_VERY_ABNORMAL,
)
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, PERCENTAGE, TEMP_CELSIUS
from homeassistant.setup import async_setup_component

from . import mock_device, mock_location, mock_reading

from tests.async_mock import patch
from tests.common import mock_registry


async def test_sensors_pro(hass, canary) -> None:
    """Test the creation and values of the sensors for Canary Pro."""
    await async_setup_component(hass, "persistent_notification", {})

    registry = mock_registry(hass)
    online_device_at_home = mock_device(20, "Dining Room", True, "Canary Pro")

    instance = canary.return_value
    instance.get_locations.return_value = [
        mock_location(100, "Home", True, devices=[online_device_at_home]),
    ]

    instance.get_latest_readings.return_value = [
        mock_reading("temperature", "21.12"),
        mock_reading("humidity", "50.46"),
        mock_reading("air_quality", "0.59"),
    ]

    config = {DOMAIN: {"username": "test-username", "password": "test-password"}}
    with patch("homeassistant.components.canary.CANARY_COMPONENTS", ["sensor"]):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    sensors = {
        "home_dining_room_temperature": (
            "20_temperature",
            "21.12",
            TEMP_CELSIUS,
            None,
            "mdi:thermometer",
        ),
        "home_dining_room_humidity": (
            "20_humidity",
            "50.46",
            PERCENTAGE,
            None,
            "mdi:water-percent",
        ),
        "home_dining_room_air_quality": (
            "20_air_quality",
            "0.59",
            None,
            None,
            "mdi:weather-windy",
        ),
    }

    for (sensor_id, data) in sensors.items():
        entity_entry = registry.async_get(f"sensor.{sensor_id}")
        assert entity_entry
        assert entity_entry.device_class == data[3]
        assert entity_entry.unique_id == data[0]
        assert entity_entry.original_icon == data[4]

        state = hass.states.get(f"sensor.{sensor_id}")
        assert state
        assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == data[2]
        assert state.state == data[1]


async def test_sensors_attributes_pro(hass, canary) -> None:
    """Test the creation and values of the sensors attributes for Canary Pro."""
    await async_setup_component(hass, "persistent_notification", {})

    online_device_at_home = mock_device(20, "Dining Room", True, "Canary Pro")

    instance = canary.return_value
    instance.get_locations.return_value = [
        mock_location(100, "Home", True, devices=[online_device_at_home]),
    ]

    instance.get_latest_readings.return_value = [
        mock_reading("temperature", "21.12"),
        mock_reading("humidity", "50.46"),
        mock_reading("air_quality", "0.59"),
    ]

    config = {DOMAIN: {"username": "test-username", "password": "test-password"}}
    with patch("homeassistant.components.canary.CANARY_COMPONENTS", ["sensor"]):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    entity_id = "sensor.home_dining_room_air_quality"
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_AIR_QUALITY] == STATE_AIR_QUALITY_ABNORMAL

    instance.get_latest_readings.return_value = [
        mock_reading("temperature", "21.12"),
        mock_reading("humidity", "50.46"),
        mock_reading("air_quality", "0.4"),
    ]

    await hass.helpers.entity_component.async_update_entity(entity_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_AIR_QUALITY] == STATE_AIR_QUALITY_VERY_ABNORMAL

    instance.get_latest_readings.return_value = [
        mock_reading("temperature", "21.12"),
        mock_reading("humidity", "50.46"),
        mock_reading("air_quality", "1.0"),
    ]

    await hass.helpers.entity_component.async_update_entity(entity_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_AIR_QUALITY] == STATE_AIR_QUALITY_NORMAL


async def test_sensors_flex(hass, canary) -> None:
    """Test the creation and values of the sensors for Canary Flex."""
    await async_setup_component(hass, "persistent_notification", {})

    registry = mock_registry(hass)
    online_device_at_home = mock_device(20, "Dining Room", True, "Canary Flex")

    instance = canary.return_value
    instance.get_locations.return_value = [
        mock_location(100, "Home", True, devices=[online_device_at_home]),
    ]

    instance.get_latest_readings.return_value = [
        mock_reading("battery", "70.4567"),
        mock_reading("wifi", "-57"),
    ]

    config = {DOMAIN: {"username": "test-username", "password": "test-password"}}
    with patch("homeassistant.components.canary.CANARY_COMPONENTS", ["sensor"]):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    sensors = {
        "home_dining_room_battery": (
            "20_battery",
            "70.46",
            PERCENTAGE,
            None,
            "mdi:battery-70",
        ),
        "home_dining_room_wifi": ("20_wifi", "-57.0", "dBm", None, "mdi:wifi"),
    }

    for (sensor_id, data) in sensors.items():
        entity_entry = registry.async_get(f"sensor.{sensor_id}")
        assert entity_entry
        assert entity_entry.device_class == data[3]
        assert entity_entry.unique_id == data[0]
        assert entity_entry.original_icon == data[4]

        state = hass.states.get(f"sensor.{sensor_id}")
        assert state
        assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == data[2]
        assert state.state == data[1]
