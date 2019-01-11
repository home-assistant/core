"""The tests the for Locative device tracker platform."""
from unittest.mock import patch

import pytest

from homeassistant.components.device_tracker import \
    DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.locative import URL, DOMAIN
from homeassistant.const import HTTP_OK, HTTP_UNPROCESSABLE_ENTITY
from homeassistant.setup import async_setup_component


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
def locative_client(loop, hass, hass_client):
    """Locative mock client."""
    assert loop.run_until_complete(async_setup_component(
        hass, DOMAIN, {
            DOMAIN: {}
        }))

    with patch('homeassistant.components.device_tracker.update_config'):
        yield loop.run_until_complete(hass_client())


async def test_missing_data(locative_client):
    """Test missing data."""
    data = {
        'latitude': 1.0,
        'longitude': 1.1,
        'device': '123',
        'id': 'Home',
        'trigger': 'enter'
    }

    # No data
    req = await locative_client.get(_url({}))
    assert req.status == HTTP_UNPROCESSABLE_ENTITY

    # No latitude
    copy = data.copy()
    del copy['latitude']
    req = await locative_client.get(_url(copy))
    assert req.status == HTTP_UNPROCESSABLE_ENTITY

    # No device
    copy = data.copy()
    del copy['device']
    req = await locative_client.get(_url(copy))
    assert req.status == HTTP_UNPROCESSABLE_ENTITY

    # No location
    copy = data.copy()
    del copy['id']
    req = await locative_client.get(_url(copy))
    assert req.status == HTTP_UNPROCESSABLE_ENTITY

    # No trigger
    copy = data.copy()
    del copy['trigger']
    req = await locative_client.get(_url(copy))
    assert req.status == HTTP_UNPROCESSABLE_ENTITY

    # Test message
    copy = data.copy()
    copy['trigger'] = 'test'
    req = await locative_client.get(_url(copy))
    assert req.status == HTTP_OK

    # Test message, no location
    copy = data.copy()
    copy['trigger'] = 'test'
    del copy['id']
    req = await locative_client.get(_url(copy))
    assert req.status == HTTP_OK

    # Unknown trigger
    copy = data.copy()
    copy['trigger'] = 'foobar'
    req = await locative_client.get(_url(copy))
    assert req.status == HTTP_UNPROCESSABLE_ENTITY


async def test_enter_and_exit(hass, locative_client):
    """Test when there is a known zone."""
    data = {
        'latitude': 40.7855,
        'longitude': -111.7367,
        'device': '123',
        'id': 'Home',
        'trigger': 'enter'
    }

    # Enter the Home
    req = await locative_client.get(_url(data))
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    state_name = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                                data['device'])).state
    assert 'home' == state_name

    data['id'] = 'HOME'
    data['trigger'] = 'exit'

    # Exit Home
    req = await locative_client.get(_url(data))
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    state_name = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                                data['device'])).state
    assert 'not_home' == state_name

    data['id'] = 'hOmE'
    data['trigger'] = 'enter'

    # Enter Home again
    req = await locative_client.get(_url(data))
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    state_name = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                                data['device'])).state
    assert 'home' == state_name

    data['trigger'] = 'exit'

    # Exit Home
    req = await locative_client.get(_url(data))
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    state_name = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                                data['device'])).state
    assert 'not_home' == state_name

    data['id'] = 'work'
    data['trigger'] = 'enter'

    # Enter Work
    req = await locative_client.get(_url(data))
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    state_name = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                                data['device'])).state
    assert 'work' == state_name


async def test_exit_after_enter(hass, locative_client):
    """Test when an exit message comes after an enter message."""
    data = {
        'latitude': 40.7855,
        'longitude': -111.7367,
        'device': '123',
        'id': 'Home',
        'trigger': 'enter'
    }

    # Enter Home
    req = await locative_client.get(_url(data))
    await hass.async_block_till_done()
    assert req.status == HTTP_OK

    state = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                           data['device']))
    assert state.state == 'home'

    data['id'] = 'Work'

    # Enter Work
    req = await locative_client.get(_url(data))
    await hass.async_block_till_done()
    assert req.status == HTTP_OK

    state = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                           data['device']))
    assert state.state == 'work'

    data['id'] = 'Home'
    data['trigger'] = 'exit'

    # Exit Home
    req = await locative_client.get(_url(data))
    await hass.async_block_till_done()
    assert req.status == HTTP_OK

    state = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                           data['device']))
    assert state.state == 'work'


async def test_exit_first(hass, locative_client):
    """Test when an exit message is sent first on a new device."""
    data = {
        'latitude': 40.7855,
        'longitude': -111.7367,
        'device': 'new_device',
        'id': 'Home',
        'trigger': 'exit'
    }

    # Exit Home
    req = await locative_client.get(_url(data))
    await hass.async_block_till_done()
    assert req.status == HTTP_OK

    state = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                           data['device']))
    assert state.state == 'not_home'
