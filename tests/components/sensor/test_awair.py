"""Tests for the Awair sensor platform."""

from contextlib import contextmanager
from datetime import timedelta
import json
import logging
from unittest.mock import patch

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.sensor.awair import (
    ATTR_LAST_API_UPDATE, ATTR_TIMESTAMP, DEVICE_CLASS_CARBON_DIOXIDE,
    DEVICE_CLASS_PM2_5, DEVICE_CLASS_SCORE,
    DEVICE_CLASS_VOLATILE_ORGANIC_COMPOUNDS)
from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_TEMPERATURE, STATE_UNAVAILABLE,
    TEMP_CELSIUS)
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import parse_datetime, utcnow

from tests.common import async_fire_time_changed, load_fixture, mock_coro

DISCOVERY_CONFIG = {
    'sensor': {
        'platform': 'awair',
        'access_token': 'qwerty',
    }
}

MANUAL_CONFIG = {
    'sensor': {
        'platform': 'awair',
        'access_token': 'qwerty',
        'devices': [
            {'uuid': 'awair_foo'}
        ]
    }
}

_LOGGER = logging.getLogger(__name__)

NOW = utcnow()
AIR_DATA_FIXTURE = json.loads(load_fixture('awair_air_data_latest.json'))
AIR_DATA_FIXTURE[0][ATTR_TIMESTAMP] = str(NOW)
AIR_DATA_FIXTURE_UPDATED = json.loads(
    load_fixture('awair_air_data_latest_updated.json'))
AIR_DATA_FIXTURE_UPDATED[0][ATTR_TIMESTAMP] = str(NOW + timedelta(minutes=5))


@contextmanager
def alter_time(retval):
    """Manage multiple time mocks."""
    patch_one = patch('homeassistant.util.dt.utcnow', return_value=retval)
    patch_two = patch('homeassistant.util.utcnow', return_value=retval)
    patch_three = patch('homeassistant.components.sensor.awair.dt.utcnow',
                        return_value=retval)

    with patch_one, patch_two, patch_three:
        yield


async def setup_awair(hass, config=None):
    """Load the Awair platform."""
    devices_json = json.loads(load_fixture('awair_devices.json'))
    devices_mock = mock_coro(devices_json)
    devices_patch = patch('python_awair.AwairClient.devices',
                          return_value=devices_mock)
    air_data_mock = mock_coro(AIR_DATA_FIXTURE)
    air_data_patch = patch('python_awair.AwairClient.air_data_latest',
                           return_value=air_data_mock)

    if config is None:
        config = DISCOVERY_CONFIG

    with devices_patch, air_data_patch, alter_time(NOW):
        assert await async_setup_component(hass, SENSOR_DOMAIN, config)
        await hass.async_block_till_done()


async def test_platform_manually_configured(hass):
    """Test that we can manually configure devices."""
    await setup_awair(hass, MANUAL_CONFIG)

    assert len(hass.states.async_all()) == 6

    # Ensure that we loaded the device with uuid 'awair_foo', not the
    # 'awair_12345' device that we stub out for API device discovery
    entity = hass.data[SENSOR_DOMAIN].get_entity('sensor.awair_co2')
    assert entity.unique_id == 'awair_foo_CO2'


async def test_platform_automatically_configured(hass):
    """Test that we can discover devices from the API."""
    await setup_awair(hass)

    assert len(hass.states.async_all()) == 6

    # Ensure that we loaded the device with uuid 'awair_12345', which is
    # the device that we stub out for API device discovery
    entity = hass.data[SENSOR_DOMAIN].get_entity('sensor.awair_co2')
    assert entity.unique_id == 'awair_12345_CO2'


async def test_bad_platform_setup(hass):
    """Tests that we throw correct exceptions when setting up Awair."""
    from python_awair import AwairClient

    auth_patch = patch('python_awair.AwairClient.devices',
                       side_effect=AwairClient.AuthError)
    rate_patch = patch('python_awair.AwairClient.devices',
                       side_effect=AwairClient.RatelimitError)
    generic_patch = patch('python_awair.AwairClient.devices',
                          side_effect=AwairClient.GenericError)

    with auth_patch:
        assert await async_setup_component(hass, SENSOR_DOMAIN,
                                           DISCOVERY_CONFIG)
        assert not hass.states.async_all()

    with rate_patch:
        assert await async_setup_component(hass, SENSOR_DOMAIN,
                                           DISCOVERY_CONFIG)
        assert not hass.states.async_all()

    with generic_patch:
        assert await async_setup_component(hass, SENSOR_DOMAIN,
                                           DISCOVERY_CONFIG)
        assert not hass.states.async_all()


async def test_awair_misc_attributes(hass):
    """Test that desired attributes are set."""
    await setup_awair(hass)

    attributes = hass.states.get('sensor.awair_co2').attributes
    assert (attributes[ATTR_LAST_API_UPDATE] ==
            parse_datetime(AIR_DATA_FIXTURE[0][ATTR_TIMESTAMP]))


async def test_awair_score(hass):
    """Test that we create a sensor for the 'Awair score'."""
    await setup_awair(hass)

    sensor = hass.states.get('sensor.awair_score')
    assert sensor.state == '78'
    assert sensor.attributes['device_class'] == DEVICE_CLASS_SCORE
    assert sensor.attributes['unit_of_measurement'] == '%'


async def test_awair_temp(hass):
    """Test that we create a temperature sensor."""
    await setup_awair(hass)

    sensor = hass.states.get('sensor.awair_temperature')
    assert sensor.state == '22.4'
    assert sensor.attributes['device_class'] == DEVICE_CLASS_TEMPERATURE
    assert sensor.attributes['unit_of_measurement'] == TEMP_CELSIUS


async def test_awair_humid(hass):
    """Test that we create a humidity sensor."""
    await setup_awair(hass)

    sensor = hass.states.get('sensor.awair_humidity')
    assert sensor.state == '32.73'
    assert sensor.attributes['device_class'] == DEVICE_CLASS_HUMIDITY
    assert sensor.attributes['unit_of_measurement'] == '%'


async def test_awair_co2(hass):
    """Test that we create a CO2 sensor."""
    await setup_awair(hass)

    sensor = hass.states.get('sensor.awair_co2')
    assert sensor.state == '612'
    assert sensor.attributes['device_class'] == DEVICE_CLASS_CARBON_DIOXIDE
    assert sensor.attributes['unit_of_measurement'] == 'ppm'


async def test_awair_voc(hass):
    """Test that we create a CO2 sensor."""
    await setup_awair(hass)

    sensor = hass.states.get('sensor.awair_voc')
    assert sensor.state == '1012'
    assert (sensor.attributes['device_class'] ==
            DEVICE_CLASS_VOLATILE_ORGANIC_COMPOUNDS)
    assert sensor.attributes['unit_of_measurement'] == 'ppb'


async def test_awair_dust(hass):
    """Test that we create a pm25 sensor."""
    await setup_awair(hass)

    # The Awair Gen1 that we mock actually returns 'DUST', but that
    # is mapped to pm25 internally so that it shows up in Homekit
    sensor = hass.states.get('sensor.awair_pm25')
    assert sensor.state == '6.2'
    assert sensor.attributes['device_class'] == DEVICE_CLASS_PM2_5
    assert sensor.attributes['unit_of_measurement'] == 'µg/m3'


async def test_awair_unsupported_sensors(hass):
    """Ensure we don't create sensors the stubbed device doesn't support."""
    await setup_awair(hass)

    # Our tests mock an Awair Gen 1 device, which should never return
    # PM10 sensor readings. Assert that we didn't create a pm10 sensor,
    # which could happen if someone were ever to refactor incorrectly.
    assert hass.states.get('sensor.awair_pm10') is None


async def test_availability(hass):
    """Ensure that we mark the component available/unavailable correctly."""
    await setup_awair(hass)

    assert hass.states.get('sensor.awair_score').state == '78'

    future = NOW + timedelta(minutes=30)
    data_patch = patch('python_awair.AwairClient.air_data_latest',
                       return_value=mock_coro(AIR_DATA_FIXTURE))

    with data_patch, alter_time(future):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    assert hass.states.get('sensor.awair_score').state == STATE_UNAVAILABLE

    future = NOW + timedelta(hours=1)
    fixture = AIR_DATA_FIXTURE_UPDATED
    fixture[0][ATTR_TIMESTAMP] = str(future)
    data_patch = patch('python_awair.AwairClient.air_data_latest',
                       return_value=mock_coro(fixture))

    with data_patch, alter_time(future):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    assert hass.states.get('sensor.awair_score').state == '79'


async def test_async_update(hass):
    """Ensure we can update sensors."""
    await setup_awair(hass)

    future = NOW + timedelta(minutes=10)
    data_patch = patch('python_awair.AwairClient.air_data_latest',
                       return_value=mock_coro(AIR_DATA_FIXTURE_UPDATED))

    with data_patch, alter_time(future):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    score_sensor = hass.states.get('sensor.awair_score')
    assert score_sensor.state == '79'

    assert hass.states.get('sensor.awair_temperature').state == '23.4'
    assert hass.states.get('sensor.awair_humidity').state == '33.73'
    assert hass.states.get('sensor.awair_co2').state == '613'
    assert hass.states.get('sensor.awair_voc').state == '1013'
    assert hass.states.get('sensor.awair_pm25').state == '7.2'


async def test_throttle_async_update(hass):
    """Ensure we throttle updates."""
    await setup_awair(hass)

    future = NOW + timedelta(minutes=1)
    data_patch = patch('python_awair.AwairClient.air_data_latest',
                       return_value=mock_coro(AIR_DATA_FIXTURE_UPDATED))

    with data_patch, alter_time(future):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    assert hass.states.get('sensor.awair_score').state == '78'

    future = NOW + timedelta(minutes=15)
    with data_patch, alter_time(future):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    assert hass.states.get('sensor.awair_score').state == '79'
