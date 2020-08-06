"""Test sensor of AccuWeather integration."""
from datetime import timedelta
import json

from homeassistant.components.accuweather.const import ATTRIBUTION, LENGTH_MILIMETERS
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    DEVICE_CLASS_TEMPERATURE,
    LENGTH_METERS,
    STATE_UNAVAILABLE,
    TEMP_CELSIUS,
    UNIT_PERCENTAGE,
)
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from tests.async_mock import patch
from tests.common import async_fire_time_changed, load_fixture
from tests.components.accuweather import init_integration


async def test_sensor_without_forecast(hass):
    """Test states of the sensor without forecast."""
    await init_integration(hass)
    registry = await hass.helpers.entity_registry.async_get_registry()

    state = hass.states.get("sensor.home_cloud_ceiling")
    assert state
    assert state.state == "3200"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_ICON) == "mdi:weather-fog"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == LENGTH_METERS

    entry = registry.async_get("sensor.home_cloud_ceiling")
    assert entry
    assert entry.unique_id == "0123456-ceiling"
    assert entry.disabled_by is None

    state = hass.states.get("sensor.home_precipitation")
    assert state
    assert state.state == "0.0"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == LENGTH_MILIMETERS
    assert state.attributes.get(ATTR_ICON) == "mdi:weather-rainy"

    entry = registry.async_get("sensor.home_precipitation")
    assert entry
    assert entry.unique_id == "0123456-precipitation"
    assert entry.disabled_by is None

    state = hass.states.get("sensor.home_pressure_tendency")
    assert state
    assert state.state == "falling"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_ICON) == "mdi:gauge"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == "accuweather__pressure_tendency"

    entry = registry.async_get("sensor.home_pressure_tendency")
    assert entry
    assert entry.unique_id == "0123456-pressuretendency"
    assert entry.disabled_by is None

    state = hass.states.get("sensor.home_realfeel_temperature")
    assert state
    assert state.state == "25.1"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == TEMP_CELSIUS
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_TEMPERATURE

    entry = registry.async_get("sensor.home_realfeel_temperature")
    assert entry
    assert entry.unique_id == "0123456-realfeeltemperature"
    assert entry.disabled_by is None

    entry = registry.async_get("sensor.home_apparent_temperature")
    assert entry
    assert entry.unique_id == "0123456-apparenttemperature"
    assert entry.disabled_by == "integration"
    assert entry.device_class == DEVICE_CLASS_TEMPERATURE
    assert entry.unit_of_measurement == TEMP_CELSIUS

    entry = registry.async_get("sensor.home_cloud_cover")
    assert entry
    assert entry.unique_id == "0123456-cloudcover"
    assert entry.disabled_by == "integration"
    assert entry.unit_of_measurement == UNIT_PERCENTAGE


async def test_availability(hass):
    """Ensure that we mark the entities unavailable correctly when service is offline."""
    await init_integration(hass)

    state = hass.states.get("sensor.home_cloud_ceiling")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "3200"

    future = utcnow() + timedelta(minutes=60)
    with patch(
        "accuweather.AccuWeather.async_get_current_conditions",
        side_effect=ConnectionError(),
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.home_cloud_ceiling")
        assert state
        assert state.state == STATE_UNAVAILABLE

    future = utcnow() + timedelta(minutes=120)
    with patch(
        "accuweather.AccuWeather.async_get_current_conditions",
        return_value=json.loads(
            load_fixture("accuweather/current_conditions_data.json")
        ),
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.home_cloud_ceiling")
        assert state
        assert state.state != STATE_UNAVAILABLE
        assert state.state == "3200"


async def test_manual_update_entity(hass):
    """Test manual update entity via service homeasasistant/update_entity."""
    await init_integration(hass)

    await async_setup_component(hass, "homeassistant", {})
    with patch(
        "homeassistant.components.accuweather.AccuWeatherDataUpdateCoordinator._async_update_data"
    ) as mock_update:
        await hass.services.async_call(
            "homeassistant",
            "update_entity",
            {ATTR_ENTITY_ID: ["sensor.home_cloud_ceiling"]},
            blocking=True,
        )
        assert mock_update.call_count == 1
