"""Test sensor of Nettigo Air Monitor integration."""
from datetime import timedelta
from unittest.mock import patch

from nettigo_air_monitor import ApiError

from homeassistant.components.nam.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    PRESSURE_HPA,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    STATE_UNAVAILABLE,
    TEMP_CELSIUS,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from . import INCOMPLETE_NAM_DATA, nam_data

from tests.common import async_fire_time_changed
from tests.components.nam import init_integration


async def test_sensor(hass):
    """Test states of the air_quality."""
    registry = er.async_get(hass)

    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "aa:bb:cc:dd:ee:ff-signal",
        suggested_object_id="nettigo_air_monitor_signal_strength",
        disabled_by=None,
    )

    await init_integration(hass)

    state = hass.states.get("sensor.nettigo_air_monitor_bme280_humidity")
    assert state
    assert state.state == "45.7"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_HUMIDITY
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE

    entry = registry.async_get("sensor.nettigo_air_monitor_bme280_humidity")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-bme280_humidity"

    state = hass.states.get("sensor.nettigo_air_monitor_bme280_temperature")
    assert state
    assert state.state == "7.6"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_TEMPERATURE
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == TEMP_CELSIUS

    entry = registry.async_get("sensor.nettigo_air_monitor_bme280_temperature")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-bme280_temperature"

    state = hass.states.get("sensor.nettigo_air_monitor_bme280_pressure")
    assert state
    assert state.state == "1011"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_PRESSURE
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PRESSURE_HPA

    entry = registry.async_get("sensor.nettigo_air_monitor_bme280_pressure")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-bme280_pressure"

    state = hass.states.get("sensor.nettigo_air_monitor_bmp280_temperature")
    assert state
    assert state.state == "5.6"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_TEMPERATURE
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == TEMP_CELSIUS

    entry = registry.async_get("sensor.nettigo_air_monitor_bmp280_temperature")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-bmp280_temperature"

    state = hass.states.get("sensor.nettigo_air_monitor_bmp280_pressure")
    assert state
    assert state.state == "1022"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_PRESSURE
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PRESSURE_HPA

    entry = registry.async_get("sensor.nettigo_air_monitor_bmp280_pressure")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-bmp280_pressure"

    state = hass.states.get("sensor.nettigo_air_monitor_sht3x_humidity")
    assert state
    assert state.state == "34.7"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_HUMIDITY
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE

    entry = registry.async_get("sensor.nettigo_air_monitor_sht3x_humidity")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-sht3x_humidity"

    state = hass.states.get("sensor.nettigo_air_monitor_sht3x_temperature")
    assert state
    assert state.state == "6.3"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_TEMPERATURE
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == TEMP_CELSIUS

    entry = registry.async_get("sensor.nettigo_air_monitor_sht3x_temperature")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-sht3x_temperature"

    state = hass.states.get("sensor.nettigo_air_monitor_dht22_humidity")
    assert state
    assert state.state == "46.2"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_HUMIDITY
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE

    entry = registry.async_get("sensor.nettigo_air_monitor_dht22_humidity")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-humidity"

    state = hass.states.get("sensor.nettigo_air_monitor_dht22_temperature")
    assert state
    assert state.state == "6.3"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_TEMPERATURE
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == TEMP_CELSIUS

    entry = registry.async_get("sensor.nettigo_air_monitor_dht22_temperature")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-temperature"

    state = hass.states.get("sensor.nettigo_air_monitor_heca_humidity")
    assert state
    assert state.state == "50.0"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_HUMIDITY
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE

    entry = registry.async_get("sensor.nettigo_air_monitor_heca_humidity")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-heca_humidity"

    state = hass.states.get("sensor.nettigo_air_monitor_heca_temperature")
    assert state
    assert state.state == "8.0"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_TEMPERATURE
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == TEMP_CELSIUS

    entry = registry.async_get("sensor.nettigo_air_monitor_heca_temperature")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-heca_temperature"

    state = hass.states.get("sensor.nettigo_air_monitor_signal_strength")
    assert state
    assert state.state == "-72"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_SIGNAL_STRENGTH
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    )

    entry = registry.async_get("sensor.nettigo_air_monitor_signal_strength")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-signal"


async def test_sensor_disabled(hass):
    """Test sensor disabled by default."""
    await init_integration(hass)
    registry = er.async_get(hass)

    entry = registry.async_get("sensor.nettigo_air_monitor_signal_strength")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-signal"
    assert entry.disabled
    assert entry.disabled_by == er.DISABLED_INTEGRATION

    # Test enabling entity
    updated_entry = registry.async_update_entity(
        entry.entity_id, **{"disabled_by": None}
    )

    assert updated_entry != entry
    assert updated_entry.disabled is False


async def test_incompleta_data_after_device_restart(hass):
    """Test states of the air_quality after device restart."""
    await init_integration(hass)

    state = hass.states.get("sensor.nettigo_air_monitor_heca_temperature")
    assert state
    assert state.state == "8.0"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_TEMPERATURE
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == TEMP_CELSIUS

    future = utcnow() + timedelta(minutes=6)
    with patch(
        "homeassistant.components.nam.NettigoAirMonitor._async_get_data",
        return_value=INCOMPLETE_NAM_DATA,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.nettigo_air_monitor_heca_temperature")
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_availability(hass):
    """Ensure that we mark the entities unavailable correctly when device causes an error."""
    await init_integration(hass)

    state = hass.states.get("sensor.nettigo_air_monitor_bme280_temperature")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "7.6"

    future = utcnow() + timedelta(minutes=6)
    with patch(
        "homeassistant.components.nam.NettigoAirMonitor._async_get_data",
        side_effect=ApiError("API Error"),
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.nettigo_air_monitor_bme280_temperature")
    assert state
    assert state.state == STATE_UNAVAILABLE

    future = utcnow() + timedelta(minutes=12)
    with patch(
        "homeassistant.components.nam.NettigoAirMonitor._async_get_data",
        return_value=nam_data,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.nettigo_air_monitor_bme280_temperature")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "7.6"


async def test_manual_update_entity(hass):
    """Test manual update entity via service homeasasistant/update_entity."""
    await init_integration(hass)

    await async_setup_component(hass, "homeassistant", {})

    with patch(
        "homeassistant.components.nam.NettigoAirMonitor._async_get_data",
        return_value=nam_data,
    ) as mock_get_data:
        await hass.services.async_call(
            "homeassistant",
            "update_entity",
            {ATTR_ENTITY_ID: ["sensor.nettigo_air_monitor_bme280_temperature"]},
            blocking=True,
        )

    assert mock_get_data.call_count == 1
