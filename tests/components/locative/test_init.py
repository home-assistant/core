"""The tests the for Locative device tracker platform."""
from unittest.mock import patch, Mock

import pytest

from homeassistant import data_entry_flow
from homeassistant.components import locative
from homeassistant.components.device_tracker import \
    DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.locative import DOMAIN, TRACKER_UPDATE
from homeassistant.const import HTTP_OK, HTTP_UNPROCESSABLE_ENTITY, \
    CONF_WEBHOOK_ID
from homeassistant.helpers.dispatcher import DATA_DISPATCHER
from homeassistant.setup import async_setup_component
from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_dev_track(mock_device_tracker_conf):
    """Mock device tracker config loading."""
    pass


@pytest.fixture
def locative_client(loop, hass, hass_client):
    """Locative mock client."""
    assert loop.run_until_complete(async_setup_component(
        hass, DOMAIN, {
            DOMAIN: {}
        }))

    with patch('homeassistant.components.device_tracker.update_config'):
        yield loop.run_until_complete(hass_client())


@pytest.fixture
async def webhook_id(hass, locative_client):
    """Initialize the Geofency component and get the webhook_id."""
    hass.config.api = Mock(base_url='http://example.com')
    result = await hass.config_entries.flow.async_init('locative', context={
        'source': 'user'
    })
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM, result

    result = await hass.config_entries.flow.async_configure(
        result['flow_id'], {})
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    return result['result'].data['webhook_id']


async def test_missing_data(locative_client, webhook_id):
    """Test missing data."""
    url = '/api/webhook/{}'.format(webhook_id)

    data = {
        'latitude': 1.0,
        'longitude': 1.1,
        'device': '123',
        'id': 'Home',
        'trigger': 'enter'
    }

    # No data
    req = await locative_client.post(url)
    assert req.status == HTTP_UNPROCESSABLE_ENTITY

    # No latitude
    copy = data.copy()
    del copy['latitude']
    req = await locative_client.post(url, data=copy)
    assert req.status == HTTP_UNPROCESSABLE_ENTITY

    # No device
    copy = data.copy()
    del copy['device']
    req = await locative_client.post(url, data=copy)
    assert req.status == HTTP_UNPROCESSABLE_ENTITY

    # No location
    copy = data.copy()
    del copy['id']
    req = await locative_client.post(url, data=copy)
    assert req.status == HTTP_UNPROCESSABLE_ENTITY

    # No trigger
    copy = data.copy()
    del copy['trigger']
    req = await locative_client.post(url, data=copy)
    assert req.status == HTTP_UNPROCESSABLE_ENTITY

    # Test message
    copy = data.copy()
    copy['trigger'] = 'test'
    req = await locative_client.post(url, data=copy)
    assert req.status == HTTP_OK

    # Test message, no location
    copy = data.copy()
    copy['trigger'] = 'test'
    del copy['id']
    req = await locative_client.post(url, data=copy)
    assert req.status == HTTP_OK

    # Unknown trigger
    copy = data.copy()
    copy['trigger'] = 'foobar'
    req = await locative_client.post(url, data=copy)
    assert req.status == HTTP_UNPROCESSABLE_ENTITY


async def test_enter_and_exit(hass, locative_client, webhook_id):
    """Test when there is a known zone."""
    url = '/api/webhook/{}'.format(webhook_id)

    data = {
        'latitude': 40.7855,
        'longitude': -111.7367,
        'device': '123',
        'id': 'Home',
        'trigger': 'enter'
    }

    # Enter the Home
    req = await locative_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    state_name = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                                data['device'])).state
    assert 'home' == state_name

    data['id'] = 'HOME'
    data['trigger'] = 'exit'

    # Exit Home
    req = await locative_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    state_name = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                                data['device'])).state
    assert 'not_home' == state_name

    data['id'] = 'hOmE'
    data['trigger'] = 'enter'

    # Enter Home again
    req = await locative_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    state_name = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                                data['device'])).state
    assert 'home' == state_name

    data['trigger'] = 'exit'

    # Exit Home
    req = await locative_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    state_name = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                                data['device'])).state
    assert 'not_home' == state_name

    data['id'] = 'work'
    data['trigger'] = 'enter'

    # Enter Work
    req = await locative_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    state_name = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                                data['device'])).state
    assert 'work' == state_name


async def test_exit_after_enter(hass, locative_client, webhook_id):
    """Test when an exit message comes after an enter message."""
    url = '/api/webhook/{}'.format(webhook_id)

    data = {
        'latitude': 40.7855,
        'longitude': -111.7367,
        'device': '123',
        'id': 'Home',
        'trigger': 'enter'
    }

    # Enter Home
    req = await locative_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK

    state = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                           data['device']))
    assert state.state == 'home'

    data['id'] = 'Work'

    # Enter Work
    req = await locative_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK

    state = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                           data['device']))
    assert state.state == 'work'

    data['id'] = 'Home'
    data['trigger'] = 'exit'

    # Exit Home
    req = await locative_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK

    state = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                           data['device']))
    assert state.state == 'work'


async def test_exit_first(hass, locative_client, webhook_id):
    """Test when an exit message is sent first on a new device."""
    url = '/api/webhook/{}'.format(webhook_id)

    data = {
        'latitude': 40.7855,
        'longitude': -111.7367,
        'device': 'new_device',
        'id': 'Home',
        'trigger': 'exit'
    }

    # Exit Home
    req = await locative_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK

    state = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                           data['device']))
    assert state.state == 'not_home'


@pytest.mark.xfail(
    reason='The device_tracker component does not support unloading yet.'
)
async def test_load_unload_entry(hass):
    """Test that the appropriate dispatch signals are added and removed."""
    entry = MockConfigEntry(domain=DOMAIN, data={
        CONF_WEBHOOK_ID: 'locative_test'
    })

    await locative.async_setup_entry(hass, entry)
    await hass.async_block_till_done()
    assert 1 == len(hass.data[DATA_DISPATCHER][TRACKER_UPDATE])

    await locative.async_unload_entry(hass, entry)
    await hass.async_block_till_done()
    assert 0 == len(hass.data[DATA_DISPATCHER][TRACKER_UPDATE])
