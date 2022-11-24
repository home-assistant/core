"""Test sensor of Airly integration."""
from datetime import timedelta

from spencerassistant.components.airly.sensor import ATTRIBUTION
from spencerassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from spencerassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    PERCENTAGE,
    PRESSURE_HPA,
    STATE_UNAVAILABLE,
    TEMP_CELSIUS,
)
from spencerassistant.helpers import entity_registry as er
from spencerassistant.setup import async_setup_component
from spencerassistant.util.dt import utcnow

from . import API_POINT_URL, init_integration

from tests.common import async_fire_time_changed, load_fixture


async def test_sensor(hass, aioclient_mock):
    """Test states of the sensor."""
    await init_integration(hass, aioclient_mock)
    registry = er.async_get(hass)

    state = hass.states.get("sensor.spencer_caqi")
    assert state
    assert state.state == "7"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "CAQI"
    assert state.attributes.get(ATTR_ICON) == "mdi:air-filter"

    entry = registry.async_get("sensor.spencer_caqi")
    assert entry
    assert entry.unique_id == "123-456-caqi"

    state = hass.states.get("sensor.spencer_humidity")
    assert state
    assert state.state == "68.3"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.HUMIDITY
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.spencer_humidity")
    assert entry
    assert entry.unique_id == "123-456-humidity"

    state = hass.states.get("sensor.spencer_pm1")
    assert state
    assert state.state == "3"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.PM1
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.spencer_pm1")
    assert entry
    assert entry.unique_id == "123-456-pm1"

    state = hass.states.get("sensor.spencer_pm2_5")
    assert state
    assert state.state == "4"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.PM25
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.spencer_pm2_5")
    assert entry
    assert entry.unique_id == "123-456-pm25"

    state = hass.states.get("sensor.spencer_pm10")
    assert state
    assert state.state == "6"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.PM10
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.spencer_pm10")
    assert entry
    assert entry.unique_id == "123-456-pm10"

    state = hass.states.get("sensor.spencer_co")
    assert state
    assert state.state == "162"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.spencer_co")
    assert entry
    assert entry.unique_id == "123-456-co"

    state = hass.states.get("sensor.spencer_no2")
    assert state
    assert state.state == "16"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.NITROGEN_DIOXIDE
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.spencer_no2")
    assert entry
    assert entry.unique_id == "123-456-no2"

    state = hass.states.get("sensor.spencer_o3")
    assert state
    assert state.state == "42"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.OZONE
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.spencer_o3")
    assert entry
    assert entry.unique_id == "123-456-o3"

    state = hass.states.get("sensor.spencer_so2")
    assert state
    assert state.state == "14"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.SULPHUR_DIOXIDE
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.spencer_so2")
    assert entry
    assert entry.unique_id == "123-456-so2"

    state = hass.states.get("sensor.spencer_pressure")
    assert state
    assert state.state == "1020"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PRESSURE_HPA
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.PRESSURE
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.spencer_pressure")
    assert entry
    assert entry.unique_id == "123-456-pressure"

    state = hass.states.get("sensor.spencer_temperature")
    assert state
    assert state.state == "14.4"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == TEMP_CELSIUS
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TEMPERATURE
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.spencer_temperature")
    assert entry
    assert entry.unique_id == "123-456-temperature"


async def test_availability(hass, aioclient_mock):
    """Ensure that we mark the entities unavailable correctly when service is offline."""
    await init_integration(hass, aioclient_mock)

    state = hass.states.get("sensor.spencer_humidity")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "68.3"

    aioclient_mock.clear_requests()
    aioclient_mock.get(API_POINT_URL, exc=ConnectionError())
    future = utcnow() + timedelta(minutes=60)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.spencer_humidity")
    assert state
    assert state.state == STATE_UNAVAILABLE

    aioclient_mock.clear_requests()
    aioclient_mock.get(API_POINT_URL, text=load_fixture("valid_station.json", "airly"))
    future = utcnow() + timedelta(minutes=120)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.spencer_humidity")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "68.3"


async def test_manual_update_entity(hass, aioclient_mock):
    """Test manual update entity via service spencerassistant/update_entity."""
    await init_integration(hass, aioclient_mock)

    call_count = aioclient_mock.call_count
    await async_setup_component(hass, "spencerassistant", {})
    await hass.services.async_call(
        "spencerassistant",
        "update_entity",
        {ATTR_ENTITY_ID: ["sensor.spencer_humidity"]},
        blocking=True,
    )

    assert aioclient_mock.call_count == call_count + 1
