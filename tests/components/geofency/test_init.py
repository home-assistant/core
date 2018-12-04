"""The tests for the Geofency device tracker platform."""
# pylint: disable=redefined-outer-name
from unittest.mock import patch

import pytest

from homeassistant.components import zone
from homeassistant.components.geofency import (
    CONF_MOBILE_BEACONS, URL, DOMAIN)
from homeassistant.const import (
    HTTP_OK, HTTP_UNPROCESSABLE_ENTITY, STATE_HOME,
    STATE_NOT_HOME)
from homeassistant.setup import async_setup_component
from homeassistant.util import slugify

HOME_LATITUDE = 37.239622
HOME_LONGITUDE = -115.815811

NOT_HOME_LATITUDE = 37.239394
NOT_HOME_LONGITUDE = -115.763283

GPS_ENTER_HOME = {
    'latitude': HOME_LATITUDE,
    'longitude': HOME_LONGITUDE,
    'device': '4A7FE356-2E9D-4264-A43F-BF80ECAEE416',
    'name': 'Home',
    'radius': 100,
    'id': 'BAAD384B-A4AE-4983-F5F5-4C2F28E68205',
    'date': '2017-08-19T10:53:53Z',
    'address': 'Testing Trail 1',
    'entry': '1'
}

GPS_EXIT_HOME = {
    'latitude': HOME_LATITUDE,
    'longitude': HOME_LONGITUDE,
    'device': '4A7FE356-2E9D-4264-A43F-BF80ECAEE416',
    'name': 'Home',
    'radius': 100,
    'id': 'BAAD384B-A4AE-4983-F5F5-4C2F28E68205',
    'date': '2017-08-19T10:53:53Z',
    'address': 'Testing Trail 1',
    'entry': '0'
}

BEACON_ENTER_HOME = {
    'latitude': HOME_LATITUDE,
    'longitude': HOME_LONGITUDE,
    'beaconUUID': 'FFEF0E83-09B2-47C8-9837-E7B563F5F556',
    'minor': '36138',
    'major': '8629',
    'device': '4A7FE356-2E9D-4264-A43F-BF80ECAEE416',
    'name': 'Home',
    'radius': 100,
    'id': 'BAAD384B-A4AE-4983-F5F5-4C2F28E68205',
    'date': '2017-08-19T10:53:53Z',
    'address': 'Testing Trail 1',
    'entry': '1'
}

BEACON_EXIT_HOME = {
    'latitude': HOME_LATITUDE,
    'longitude': HOME_LONGITUDE,
    'beaconUUID': 'FFEF0E83-09B2-47C8-9837-E7B563F5F556',
    'minor': '36138',
    'major': '8629',
    'device': '4A7FE356-2E9D-4264-A43F-BF80ECAEE416',
    'name': 'Home',
    'radius': 100,
    'id': 'BAAD384B-A4AE-4983-F5F5-4C2F28E68205',
    'date': '2017-08-19T10:53:53Z',
    'address': 'Testing Trail 1',
    'entry': '0'
}

BEACON_ENTER_CAR = {
    'latitude': NOT_HOME_LATITUDE,
    'longitude': NOT_HOME_LONGITUDE,
    'beaconUUID': 'FFEF0E83-09B2-47C8-9837-E7B563F5F556',
    'minor': '36138',
    'major': '8629',
    'device': '4A7FE356-2E9D-4264-A43F-BF80ECAEE416',
    'name': 'Car 1',
    'radius': 100,
    'id': 'BAAD384B-A4AE-4983-F5F5-4C2F28E68205',
    'date': '2017-08-19T10:53:53Z',
    'address': 'Testing Trail 1',
    'entry': '1'
}

BEACON_EXIT_CAR = {
    'latitude': NOT_HOME_LATITUDE,
    'longitude': NOT_HOME_LONGITUDE,
    'beaconUUID': 'FFEF0E83-09B2-47C8-9837-E7B563F5F556',
    'minor': '36138',
    'major': '8629',
    'device': '4A7FE356-2E9D-4264-A43F-BF80ECAEE416',
    'name': 'Car 1',
    'radius': 100,
    'id': 'BAAD384B-A4AE-4983-F5F5-4C2F28E68205',
    'date': '2017-08-19T10:53:53Z',
    'address': 'Testing Trail 1',
    'entry': '0'
}


@pytest.fixture(autouse=True)
def mock_dev_track(mock_device_tracker_conf):
    """Mock device tracker config loading."""
    pass


@pytest.fixture
def geofency_client(loop, hass, hass_client):
    """Geofency mock client."""
    assert loop.run_until_complete(async_setup_component(
        hass, DOMAIN, {
            DOMAIN: {
                CONF_MOBILE_BEACONS: ['Car 1']
            }}))

    loop.run_until_complete(hass.async_block_till_done())

    with patch('homeassistant.components.device_tracker.update_config'):
        yield loop.run_until_complete(hass_client())


@pytest.fixture(autouse=True)
def setup_zones(loop, hass):
    """Set up Zone config in HA."""
    assert loop.run_until_complete(async_setup_component(
        hass, zone.DOMAIN, {
            'zone': {
                'name': 'Home',
                'latitude': HOME_LATITUDE,
                'longitude': HOME_LONGITUDE,
                'radius': 100,
            }}))


async def test_data_validation(geofency_client):
    """Test data validation."""
    # No data
    req = await geofency_client.post(URL)
    assert req.status == HTTP_UNPROCESSABLE_ENTITY

    missing_attributes = ['address', 'device',
                          'entry', 'latitude', 'longitude', 'name']

    # missing attributes
    for attribute in missing_attributes:
        copy = GPS_ENTER_HOME.copy()
        del copy[attribute]
        req = await geofency_client.post(URL, data=copy)
        assert req.status == HTTP_UNPROCESSABLE_ENTITY


async def test_gps_enter_and_exit_home(hass, geofency_client):
    """Test GPS based zone enter and exit."""
    # Enter the Home zone
    req = await geofency_client.post(URL, data=GPS_ENTER_HOME)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    device_name = slugify(GPS_ENTER_HOME['device'])
    state_name = hass.states.get('{}.{}'.format(
        'device_tracker', device_name)).state
    assert STATE_HOME == state_name

    # Exit the Home zone
    req = await geofency_client.post(URL, data=GPS_EXIT_HOME)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    device_name = slugify(GPS_EXIT_HOME['device'])
    state_name = hass.states.get('{}.{}'.format(
        'device_tracker', device_name)).state
    assert STATE_NOT_HOME == state_name

    # Exit the Home zone with "Send Current Position" enabled
    data = GPS_EXIT_HOME.copy()
    data['currentLatitude'] = NOT_HOME_LATITUDE
    data['currentLongitude'] = NOT_HOME_LONGITUDE

    req = await geofency_client.post(URL, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    device_name = slugify(GPS_EXIT_HOME['device'])
    current_latitude = hass.states.get('{}.{}'.format(
        'device_tracker', device_name)).attributes['latitude']
    assert NOT_HOME_LATITUDE == current_latitude
    current_longitude = hass.states.get('{}.{}'.format(
        'device_tracker', device_name)).attributes['longitude']
    assert NOT_HOME_LONGITUDE == current_longitude


async def test_beacon_enter_and_exit_home(hass, geofency_client):
    """Test iBeacon based zone enter and exit - a.k.a stationary iBeacon."""
    # Enter the Home zone
    req = await geofency_client.post(URL, data=BEACON_ENTER_HOME)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    device_name = slugify("beacon_{}".format(BEACON_ENTER_HOME['name']))
    state_name = hass.states.get('{}.{}'.format(
        'device_tracker', device_name)).state
    assert STATE_HOME == state_name

    # Exit the Home zone
    req = await geofency_client.post(URL, data=BEACON_EXIT_HOME)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    device_name = slugify("beacon_{}".format(BEACON_ENTER_HOME['name']))
    state_name = hass.states.get('{}.{}'.format(
        'device_tracker', device_name)).state
    assert STATE_NOT_HOME == state_name


async def test_beacon_enter_and_exit_car(hass, geofency_client):
    """Test use of mobile iBeacon."""
    # Enter the Car away from Home zone
    req = await geofency_client.post(URL, data=BEACON_ENTER_CAR)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    device_name = slugify("beacon_{}".format(BEACON_ENTER_CAR['name']))
    state_name = hass.states.get('{}.{}'.format(
        'device_tracker', device_name)).state
    assert STATE_NOT_HOME == state_name

    # Exit the Car away from Home zone
    req = await geofency_client.post(URL, data=BEACON_EXIT_CAR)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    device_name = slugify("beacon_{}".format(BEACON_ENTER_CAR['name']))
    state_name = hass.states.get('{}.{}'.format(
        'device_tracker', device_name)).state
    assert STATE_NOT_HOME == state_name

    # Enter the Car in the Home zone
    data = BEACON_ENTER_CAR.copy()
    data['latitude'] = HOME_LATITUDE
    data['longitude'] = HOME_LONGITUDE
    req = await geofency_client.post(URL, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    device_name = slugify("beacon_{}".format(data['name']))
    state_name = hass.states.get('{}.{}'.format(
        'device_tracker', device_name)).state
    assert STATE_HOME == state_name

    # Exit the Car in the Home zone
    req = await geofency_client.post(URL, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    device_name = slugify("beacon_{}".format(data['name']))
    state_name = hass.states.get('{}.{}'.format(
        'device_tracker', device_name)).state
    assert STATE_HOME == state_name
