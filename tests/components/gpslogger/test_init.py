"""The tests the for GPSLogger device tracker platform."""
from unittest.mock import patch

import pytest

from homeassistant.components import zone
from homeassistant.components.device_tracker import \
    DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.gpslogger import URL, DOMAIN
from homeassistant.const import HTTP_OK, HTTP_UNPROCESSABLE_ENTITY, \
    STATE_HOME, STATE_NOT_HOME
from homeassistant.setup import async_setup_component

HOME_LATITUDE = 37.239622
HOME_LONGITUDE = -115.815811


def _url(data=None):
    """Generate URL."""
    data = data or {}
    data = "&".join(["{}={}".format(name, value) for
                     name, value in data.items()])
    return "{}?{}".format(URL, data)


@pytest.fixture(autouse=True)
def mock_dev_track(mock_device_tracker_conf):
    """Mock device tracker config loading."""
    pass


@pytest.fixture
def gpslogger_client(loop, hass, hass_client):
    """Locative mock client."""
    assert loop.run_until_complete(async_setup_component(
        hass, DOMAIN, {
            DOMAIN: {}
        }))

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


async def test_missing_data(gpslogger_client):
    """Test missing data."""
    data = {
        'latitude': 1.0,
        'longitude': 1.1,
        'device': '123',
        'id': 'Home',
    }

    # No data
    req = await gpslogger_client.get(_url({}))
    assert req.status == HTTP_UNPROCESSABLE_ENTITY

    # No latitude
    copy = data.copy()
    del copy['latitude']
    req = await gpslogger_client.get(_url(copy))
    assert req.status == HTTP_UNPROCESSABLE_ENTITY

    # No device
    copy = data.copy()
    del copy['device']
    req = await gpslogger_client.get(_url(copy))
    assert req.status == HTTP_UNPROCESSABLE_ENTITY


async def test_enter_and_exit(hass, gpslogger_client):
    """Test when there is a known zone."""
    data = {
        'latitude': HOME_LATITUDE,
        'longitude': HOME_LONGITUDE,
        'device': '123',
    }

    # Enter the Home
    req = await gpslogger_client.get(_url(data))
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    state_name = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                                data['device'])).state
    assert STATE_HOME == state_name

    # Enter Home again
    req = await gpslogger_client.get(_url(data))
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    state_name = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                                data['device'])).state
    assert STATE_HOME == state_name

    data['longitude'] = 0
    data['latitude'] = 0

    # Enter Somewhere else
    req = await gpslogger_client.get(_url(data))
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    state_name = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                                data['device'])).state
    assert STATE_NOT_HOME == state_name
