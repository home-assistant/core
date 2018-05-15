"""The tests the for Locative device tracker platform."""
import asyncio
from unittest.mock import patch

import pytest

from homeassistant.setup import async_setup_component
import homeassistant.components.device_tracker as device_tracker
from homeassistant.const import CONF_PLATFORM
from homeassistant.components.device_tracker.locative import URL


def _url(data=None):
    """Helper method to generate URLs."""
    data = data or {}
    data = "&".join(["{}={}".format(name, value) for
                     name, value in data.items()])
    return "{}?{}".format(URL, data)


@pytest.fixture
def locative_client(loop, hass, aiohttp_client):
    """Locative mock client."""
    assert loop.run_until_complete(async_setup_component(
        hass, device_tracker.DOMAIN, {
            device_tracker.DOMAIN: {
                CONF_PLATFORM: 'locative'
            }
        }))

    with patch('homeassistant.components.device_tracker.update_config'):
        yield loop.run_until_complete(aiohttp_client(hass.http.app))


@asyncio.coroutine
def test_missing_data(locative_client):
    """Test missing data."""
    data = {
        'latitude': 1.0,
        'longitude': 1.1,
        'device': '123',
        'id': 'Home',
        'trigger': 'enter'
    }

    # No data
    req = yield from locative_client.get(_url({}))
    assert req.status == 422

    # No latitude
    copy = data.copy()
    del copy['latitude']
    req = yield from locative_client.get(_url(copy))
    assert req.status == 422

    # No device
    copy = data.copy()
    del copy['device']
    req = yield from locative_client.get(_url(copy))
    assert req.status == 422

    # No location
    copy = data.copy()
    del copy['id']
    req = yield from locative_client.get(_url(copy))
    assert req.status == 422

    # No trigger
    copy = data.copy()
    del copy['trigger']
    req = yield from locative_client.get(_url(copy))
    assert req.status == 422

    # Test message
    copy = data.copy()
    copy['trigger'] = 'test'
    req = yield from locative_client.get(_url(copy))
    assert req.status == 200

    # Test message, no location
    copy = data.copy()
    copy['trigger'] = 'test'
    del copy['id']
    req = yield from locative_client.get(_url(copy))
    assert req.status == 200

    # Unknown trigger
    copy = data.copy()
    copy['trigger'] = 'foobar'
    req = yield from locative_client.get(_url(copy))
    assert req.status == 422


@asyncio.coroutine
def test_enter_and_exit(hass, locative_client):
    """Test when there is a known zone."""
    data = {
        'latitude': 40.7855,
        'longitude': -111.7367,
        'device': '123',
        'id': 'Home',
        'trigger': 'enter'
    }

    # Enter the Home
    req = yield from locative_client.get(_url(data))
    assert req.status == 200
    state_name = hass.states.get('{}.{}'.format('device_tracker',
                                                data['device'])).state
    assert 'home' == state_name

    data['id'] = 'HOME'
    data['trigger'] = 'exit'

    # Exit Home
    req = yield from locative_client.get(_url(data))
    assert req.status == 200
    state_name = hass.states.get('{}.{}'.format('device_tracker',
                                                data['device'])).state
    assert 'not_home' == state_name

    data['id'] = 'hOmE'
    data['trigger'] = 'enter'

    # Enter Home again
    req = yield from locative_client.get(_url(data))
    assert req.status == 200
    state_name = hass.states.get('{}.{}'.format('device_tracker',
                                                data['device'])).state
    assert 'home' == state_name

    data['trigger'] = 'exit'

    # Exit Home
    req = yield from locative_client.get(_url(data))
    assert req.status == 200
    state_name = hass.states.get('{}.{}'.format('device_tracker',
                                                data['device'])).state
    assert 'not_home' == state_name

    data['id'] = 'work'
    data['trigger'] = 'enter'

    # Enter Work
    req = yield from locative_client.get(_url(data))
    assert req.status == 200
    state_name = hass.states.get('{}.{}'.format('device_tracker',
                                                data['device'])).state
    assert 'work' == state_name


@asyncio.coroutine
def test_exit_after_enter(hass, locative_client):
    """Test when an exit message comes after an enter message."""
    data = {
        'latitude': 40.7855,
        'longitude': -111.7367,
        'device': '123',
        'id': 'Home',
        'trigger': 'enter'
    }

    # Enter Home
    req = yield from locative_client.get(_url(data))
    assert req.status == 200

    state = hass.states.get('{}.{}'.format('device_tracker',
                                           data['device']))
    assert state.state == 'home'

    data['id'] = 'Work'

    # Enter Work
    req = yield from locative_client.get(_url(data))
    assert req.status == 200

    state = hass.states.get('{}.{}'.format('device_tracker',
                                           data['device']))
    assert state.state == 'work'

    data['id'] = 'Home'
    data['trigger'] = 'exit'

    # Exit Home
    req = yield from locative_client.get(_url(data))
    assert req.status == 200

    state = hass.states.get('{}.{}'.format('device_tracker',
                                           data['device']))
    assert state.state == 'work'


@asyncio.coroutine
def test_exit_first(hass, locative_client):
    """Test when an exit message is sent first on a new device."""
    data = {
        'latitude': 40.7855,
        'longitude': -111.7367,
        'device': 'new_device',
        'id': 'Home',
        'trigger': 'exit'
    }

    # Exit Home
    req = yield from locative_client.get(_url(data))
    assert req.status == 200

    state = hass.states.get('{}.{}'.format('device_tracker',
                                           data['device']))
    assert state.state == 'not_home'
