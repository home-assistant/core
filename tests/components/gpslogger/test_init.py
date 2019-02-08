"""The tests the for GPSLogger device tracker platform."""
from unittest.mock import patch, Mock

import pytest
from homeassistant.helpers.dispatcher import DATA_DISPATCHER

from homeassistant import data_entry_flow
from homeassistant.components import zone, gpslogger
from homeassistant.components.device_tracker import \
    DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.gpslogger import DOMAIN, TRACKER_UPDATE
from homeassistant.const import HTTP_OK, HTTP_UNPROCESSABLE_ENTITY, \
    STATE_HOME, STATE_NOT_HOME, CONF_WEBHOOK_ID
from homeassistant.setup import async_setup_component
from tests.common import MockConfigEntry

HOME_LATITUDE = 37.239622
HOME_LONGITUDE = -115.815811


@pytest.fixture(autouse=True)
def mock_dev_track(mock_device_tracker_conf):
    """Mock device tracker config loading."""
    pass


@pytest.fixture
def gpslogger_client(loop, hass, aiohttp_client):
    """Mock client for GPSLogger (unauthenticated)."""
    assert loop.run_until_complete(async_setup_component(
        hass, 'persistent_notification', {}))

    assert loop.run_until_complete(async_setup_component(
        hass, DOMAIN, {
            DOMAIN: {}
        }))

    with patch('homeassistant.components.device_tracker.update_config'):
        yield loop.run_until_complete(aiohttp_client(hass.http.app))


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


@pytest.fixture
async def webhook_id(hass, gpslogger_client):
    """Initialize the GPSLogger component and get the webhook_id."""
    hass.config.api = Mock(base_url='http://example.com')
    result = await hass.config_entries.flow.async_init(DOMAIN, context={
        'source': 'user'
    })
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM, result

    result = await hass.config_entries.flow.async_configure(
        result['flow_id'], {})
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    return result['result'].data['webhook_id']


async def test_missing_data(hass, gpslogger_client, webhook_id):
    """Test missing data."""
    url = '/api/webhook/{}'.format(webhook_id)

    data = {
        'latitude': 1.0,
        'longitude': 1.1,
        'device': '123',
    }

    # No data
    req = await gpslogger_client.post(url)
    await hass.async_block_till_done()
    assert req.status == HTTP_UNPROCESSABLE_ENTITY

    # No latitude
    copy = data.copy()
    del copy['latitude']
    req = await gpslogger_client.post(url, data=copy)
    await hass.async_block_till_done()
    assert req.status == HTTP_UNPROCESSABLE_ENTITY

    # No device
    copy = data.copy()
    del copy['device']
    req = await gpslogger_client.post(url, data=copy)
    await hass.async_block_till_done()
    assert req.status == HTTP_UNPROCESSABLE_ENTITY


async def test_enter_and_exit(hass, gpslogger_client, webhook_id):
    """Test when there is a known zone."""
    url = '/api/webhook/{}'.format(webhook_id)

    data = {
        'latitude': HOME_LATITUDE,
        'longitude': HOME_LONGITUDE,
        'device': '123',
    }

    # Enter the Home
    req = await gpslogger_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    state_name = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                                data['device'])).state
    assert STATE_HOME == state_name

    # Enter Home again
    req = await gpslogger_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    state_name = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                                data['device'])).state
    assert STATE_HOME == state_name

    data['longitude'] = 0
    data['latitude'] = 0

    # Enter Somewhere else
    req = await gpslogger_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    state_name = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                                data['device'])).state
    assert STATE_NOT_HOME == state_name


async def test_enter_with_attrs(hass, gpslogger_client, webhook_id):
    """Test when additional attributes are present."""
    url = '/api/webhook/{}'.format(webhook_id)

    data = {
        'latitude': 1.0,
        'longitude': 1.1,
        'device': '123',
        'accuracy': 10.5,
        'battery': 10,
        'speed': 100,
        'direction': 105.32,
        'altitude': 102,
        'provider': 'gps',
        'activity': 'running'
    }

    req = await gpslogger_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    state = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                           data['device']))
    assert STATE_NOT_HOME == state.state
    assert 10.5 == state.attributes['gps_accuracy']
    assert 10.0 == state.attributes['battery']
    assert 100.0 == state.attributes['speed']
    assert 105.32 == state.attributes['direction']
    assert 102.0 == state.attributes['altitude']
    assert 'gps' == state.attributes['provider']
    assert 'running' == state.attributes['activity']


@pytest.mark.xfail(
    reason='The device_tracker component does not support unloading yet.'
)
async def test_load_unload_entry(hass):
    """Test that the appropriate dispatch signals are added and removed."""
    entry = MockConfigEntry(domain=DOMAIN, data={
        CONF_WEBHOOK_ID: 'gpslogger_test'
    })

    await gpslogger.async_setup_entry(hass, entry)
    await hass.async_block_till_done()
    assert 1 == len(hass.data[DATA_DISPATCHER][TRACKER_UPDATE])

    await gpslogger.async_unload_entry(hass, entry)
    await hass.async_block_till_done()
    assert 0 == len(hass.data[DATA_DISPATCHER][TRACKER_UPDATE])
