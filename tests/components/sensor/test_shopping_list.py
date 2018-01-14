"""The tests for the Shopping List sensor platform."""
import asyncio
import logging
from unittest.mock import patch

import pytest

from homeassistant.bootstrap import async_setup_component
import homeassistant.components.sensor as sensor
from homeassistant.helpers import intent
#from tests.common import get_test_home_assistant


@pytest.fixture(autouse=True)
def mock_shopping_list_io():
    """Stub out the persistence."""
    with patch('homeassistant.components.shopping_list.ShoppingData.save'), \
            patch('homeassistant.components.shopping_list.'
                  'ShoppingData.async_load'):
        yield


# def setup_function():
#     """Initialize a Home Assistant server."""
#     global hass
#
#     hass = get_test_home_assistant()
#
# def teardown_function():
#     """Stop the Home Assistant server."""
#     hass.stop()
#
#
@asyncio.coroutine
def test_shopping_list_setup(hass):
    """Test the setup via shopping_list."""
    result = yield from async_setup_component(hass, sensor.DOMAIN, {
        sensor.DOMAIN: {
            'platform': 'shopping_list'
        }
    })
    assert result


@asyncio.coroutine
def test_shopping_list_setup_name(hass):
    """Test the setup via shopping_list."""
    yield from async_setup_component(hass, sensor.DOMAIN, {
        sensor.DOMAIN: {
            'platform': 'shopping_list',
            'name': 'test_list'
        }
    })
    state = hass.states.get('sensor.test_list')
    assert state.state == 'empty'


@asyncio.coroutine
def test_shopping_list_setup_name(hass):
    """Test the setup via shopping_list."""
    yield from async_setup_component(hass, sensor.DOMAIN, {
        sensor.DOMAIN: {
            'platform': 'shopping_list',
            'name': 'test_list'
        }
    })
    state = hass.states.get('sensor.test_list')
    assert state.state == 'empty'


@asyncio.coroutine
def test_shopping_list_not_empty(hass, test_client):
    """Test adding an item via shopping_list."""
    yield from async_setup_component(hass, 'shopping_list', {
        'shopping_list': {
        }
    })
    yield from intent.async_handle(
        hass, 'test', 'HassShoppingListAddItem', {'item': {'value': 'beer'}}
    )
    yield from hass.async_block_till_done()

    assert hass.data['shopping_list'].items
    assert hass.data['shopping_list'].items[0]['name'] == 'beer'

    yield from async_setup_component(hass, sensor.DOMAIN, {
        sensor.DOMAIN: {
            'platform': 'shopping_list',
        }
    })
    state = hass.states.get('sensor.shopping_list')
    assert state.state == 'not_empty'
    assert state.attributes.get('items')[0]['name'] == 'beer'
