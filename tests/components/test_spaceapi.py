"""The tests for the Home Assistant SpaceAPI component."""
# pylint: disable=protected-access
from unittest.mock import patch

import pytest
from tests.common import mock_coro

from homeassistant.components.spaceapi import (
    DOMAIN, SPACEAPI_VERSION, URL_API_SPACEAPI)
from homeassistant.setup import async_setup_component

CONFIG = {
    DOMAIN: {
        'space': 'Home',
        'logo': 'https://home-assistant.io/logo.png',
        'url': 'https://home-assistant.io',
        'location': {'address': 'In your Home'},
        'contact': {'email': 'hello@home-assistant.io'},
        'issue_report_channels': ['email'],
        'state': {
            'entity_id': 'test.test_door',
            'icon_open': 'https://home-assistant.io/open.png',
            'icon_closed': 'https://home-assistant.io/close.png',
        },
        'sensors': {
            'temperature': ['test.temp1', 'test.temp2'],
            'humidity': ['test.hum1'],
        }
    }
}

SENSOR_OUTPUT = {
    'temperature': [
        {
            'location': 'Home',
            'name': 'temp1',
            'unit': '°C',
            'value': '25'
        },
        {
            'location': 'Home',
            'name': 'temp2',
            'unit': '°C',
            'value': '23'
        },
    ],
    'humidity': [
        {
            'location': 'Home',
            'name': 'hum1',
            'unit': '%',
            'value': '88'
        },
    ]
}


@pytest.fixture
def mock_client(hass, aiohttp_client):
    """Start the Home Assistant HTTP component."""
    with patch('homeassistant.components.spaceapi',
               return_value=mock_coro(True)):
        hass.loop.run_until_complete(
            async_setup_component(hass, 'spaceapi', CONFIG))

    hass.states.async_set('test.temp1', 25,
                          attributes={'unit_of_measurement': '°C'})
    hass.states.async_set('test.temp2', 23,
                          attributes={'unit_of_measurement': '°C'})
    hass.states.async_set('test.hum1', 88,
                          attributes={'unit_of_measurement': '%'})

    return hass.loop.run_until_complete(aiohttp_client(hass.http.app))


async def test_spaceapi_get(hass, mock_client):
    """Test response after start-up Home Assistant."""
    resp = await mock_client.get(URL_API_SPACEAPI)
    assert resp.status == 200

    data = await resp.json()

    assert data['api'] == SPACEAPI_VERSION
    assert data['space'] == 'Home'
    assert data['contact']['email'] == 'hello@home-assistant.io'
    assert data['location']['address'] == 'In your Home'
    assert data['location']['latitude'] == 32.87336
    assert data['location']['longitude'] == -117.22743
    assert data['state']['open'] == 'null'
    assert data['state']['icon']['open'] == \
        'https://home-assistant.io/open.png'
    assert data['state']['icon']['close'] == \
        'https://home-assistant.io/close.png'


async def test_spaceapi_state_get(hass, mock_client):
    """Test response if the state entity was set."""
    hass.states.async_set('test.test_door', True)

    resp = await mock_client.get(URL_API_SPACEAPI)
    assert resp.status == 200

    data = await resp.json()
    assert data['state']['open'] == bool(1)


async def test_spaceapi_sensors_get(hass, mock_client):
    """Test the response for the sensors."""
    resp = await mock_client.get(URL_API_SPACEAPI)
    assert resp.status == 200

    data = await resp.json()
    assert data['sensors'] == SENSOR_OUTPUT
