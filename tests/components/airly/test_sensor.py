"""Test sensor of Airly integration."""
from datetime import timedelta
from http import HTTPStatus

from airly.exceptions import AirlyError

from homeassistant.components.airly.sensor import ATTRIBUTION
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    PERCENTAGE,
    STATE_UNAVAILABLE,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from . import API_POINT_URL, init_integration

from tests.common import async_fire_time_changed, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_sensor(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Test states of the sensor."""
    await init_integration(hass, aioclient_mock)
    registry = er.async_get(hass)

    state = hass.states.get("sensor.home_common_air_quality_index")
    assert state
    assert state.state == "7.29"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "CAQI"
    assert state.attributes.get(ATTR_ICON) == "mdi:air-filter"

    entry = registry.async_get("sensor.home_common_air_quality_index")
    assert entry
    assert entry.unique_id == "123-456-caqi"
    assert entry.options["sensor"] == {"suggested_display_precision": 0}

    state = hass.states.get("sensor.home_humidity")
    assert state
    assert state.state == "68.35"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.HUMIDITY
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.home_humidity")
    assert entry
    assert entry.unique_id == "123-456-humidity"
    assert entry.options["sensor"] == {"suggested_display_precision": 1}

    state = hass.states.get("sensor.home_pm1")
    assert state
    assert state.state == "2.83"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.PM1
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.home_pm1")
    assert entry
    assert entry.unique_id == "123-456-pm1"
    assert entry.options["sensor"] == {"suggested_display_precision": 0}

    state = hass.states.get("sensor.home_pm2_5")
    assert state
    assert state.state == "4.37"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.PM25
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.home_pm2_5")
    assert entry
    assert entry.unique_id == "123-456-pm25"
    assert entry.options["sensor"] == {"suggested_display_precision": 0}

    state = hass.states.get("sensor.home_pm10")
    assert state
    assert state.state == "6.06"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.PM10
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.home_pm10")
    assert entry
    assert entry.unique_id == "123-456-pm10"
    assert entry.options["sensor"] == {"suggested_display_precision": 0}

    state = hass.states.get("sensor.home_carbon_monoxide")
    assert state
    assert state.state == "162.49"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert entry.options["sensor"] == {"suggested_display_precision": 0}

    entry = registry.async_get("sensor.home_carbon_monoxide")
    assert entry
    assert entry.unique_id == "123-456-co"

    state = hass.states.get("sensor.home_nitrogen_dioxide")
    assert state
    assert state.state == "16.04"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.NITROGEN_DIOXIDE
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.home_nitrogen_dioxide")
    assert entry
    assert entry.unique_id == "123-456-no2"
    assert entry.options["sensor"] == {"suggested_display_precision": 0}

    state = hass.states.get("sensor.home_ozone")
    assert state
    assert state.state == "41.52"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.OZONE
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.home_ozone")
    assert entry
    assert entry.unique_id == "123-456-o3"
    assert entry.options["sensor"] == {"suggested_display_precision": 0}

    state = hass.states.get("sensor.home_sulphur_dioxide")
    assert state
    assert state.state == "13.97"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.SULPHUR_DIOXIDE
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.home_sulphur_dioxide")
    assert entry
    assert entry.unique_id == "123-456-so2"
    assert entry.options["sensor"] == {"suggested_display_precision": 0}

    state = hass.states.get("sensor.home_pressure")
    assert state
    assert state.state == "1019.86"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfPressure.HPA
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.PRESSURE
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.home_pressure")
    assert entry
    assert entry.unique_id == "123-456-pressure"
    assert entry.options["sensor"] == {"suggested_display_precision": 0}

    state = hass.states.get("sensor.home_temperature")
    assert state
    assert state.state == "14.37"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TEMPERATURE
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entry = registry.async_get("sensor.home_temperature")
    assert entry
    assert entry.unique_id == "123-456-temperature"
    assert entry.options["sensor"] == {"suggested_display_precision": 1}


async def test_availability(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Ensure that we mark the entities unavailable correctly when service is offline."""
    await init_integration(hass, aioclient_mock)

    state = hass.states.get("sensor.home_humidity")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "68.35"

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        API_POINT_URL, exc=AirlyError(HTTPStatus.NOT_FOUND, {"message": "Not found"})
    )
    future = utcnow() + timedelta(minutes=60)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.home_humidity")
    assert state
    assert state.state == STATE_UNAVAILABLE

    aioclient_mock.clear_requests()
    aioclient_mock.get(API_POINT_URL, text=load_fixture("valid_station.json", "airly"))
    future = utcnow() + timedelta(minutes=120)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.home_humidity")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "68.35"


async def test_manual_update_entity(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test manual update entity via service homeassistant/update_entity."""
    await init_integration(hass, aioclient_mock)

    call_count = aioclient_mock.call_count
    await async_setup_component(hass, "homeassistant", {})
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {ATTR_ENTITY_ID: ["sensor.home_humidity"]},
        blocking=True,
    )

    assert aioclient_mock.call_count == call_count + 1
