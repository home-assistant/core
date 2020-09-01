"""Test sensor of Airly integration."""
from datetime import timedelta
import json

from homeassistant.components.airly.sensor import ATTRIBUTION
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    PRESSURE_HPA,
    STATE_UNAVAILABLE,
    TEMP_CELSIUS,
    UNIT_PERCENTAGE,
)
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from tests.async_mock import patch
from tests.common import async_fire_time_changed, load_fixture
from tests.components.airly import init_integration


async def test_sensor(hass):
    """Test states of the sensor."""
    await init_integration(hass)
    registry = await hass.helpers.entity_registry.async_get_registry()

    state = hass.states.get("sensor.home_humidity")
    assert state
    assert state.state == "92.8"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UNIT_PERCENTAGE
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_HUMIDITY

    entry = registry.async_get("sensor.home_humidity")
    assert entry
    assert entry.unique_id == "55.55-122.12-humidity"

    state = hass.states.get("sensor.home_pm1")
    assert state
    assert state.state == "9"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert state.attributes.get(ATTR_ICON) == "mdi:blur"

    entry = registry.async_get("sensor.home_pm1")
    assert entry
    assert entry.unique_id == "55.55-122.12-pm1"

    state = hass.states.get("sensor.home_pressure")
    assert state
    assert state.state == "1001"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PRESSURE_HPA
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_PRESSURE

    entry = registry.async_get("sensor.home_pressure")
    assert entry
    assert entry.unique_id == "55.55-122.12-pressure"

    state = hass.states.get("sensor.home_temperature")
    assert state
    assert state.state == "14.2"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == TEMP_CELSIUS
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_TEMPERATURE

    entry = registry.async_get("sensor.home_temperature")
    assert entry
    assert entry.unique_id == "55.55-122.12-temperature"


async def test_availability(hass):
    """Ensure that we mark the entities unavailable correctly when service is offline."""
    await init_integration(hass)

    state = hass.states.get("sensor.home_humidity")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "92.8"

    future = utcnow() + timedelta(minutes=60)
    with patch("airly._private._RequestsHandler.get", side_effect=ConnectionError()):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.home_humidity")
        assert state
        assert state.state == STATE_UNAVAILABLE

    future = utcnow() + timedelta(minutes=120)
    with patch(
        "airly._private._RequestsHandler.get",
        return_value=json.loads(load_fixture("airly_valid_station.json")),
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.home_humidity")
        assert state
        assert state.state != STATE_UNAVAILABLE
        assert state.state == "92.8"


async def test_manual_update_entity(hass):
    """Test manual update entity via service homeasasistant/update_entity."""
    await init_integration(hass)

    await async_setup_component(hass, "homeassistant", {})
    with patch(
        "homeassistant.components.airly.AirlyDataUpdateCoordinator._async_update_data"
    ) as mock_update:
        await hass.services.async_call(
            "homeassistant",
            "update_entity",
            {ATTR_ENTITY_ID: ["sensor.home_humidity"]},
            blocking=True,
        )
        assert mock_update.call_count == 1
