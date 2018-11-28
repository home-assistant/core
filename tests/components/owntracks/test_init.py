"""Test the owntracks_http platform."""
import asyncio
from unittest.mock import Mock

import os
import pytest

from homeassistant.components import device_tracker
from homeassistant.setup import async_setup_component

from tests.common import mock_component, mock_coro, MockConfigEntry

MINIMAL_LOCATION_MESSAGE = {
    '_type': 'location',
    'lon': 45,
    'lat': 90,
    'p': 101.3977584838867,
    'tid': 'test',
    'tst': 1,
}

LOCATION_MESSAGE = {
    '_type': 'location',
    'acc': 60,
    'alt': 27,
    'batt': 92,
    'cog': 248,
    'lon': 45,
    'lat': 90,
    'p': 101.3977584838867,
    'tid': 'test',
    't': 'u',
    'tst': 1,
    'vac': 4,
    'vel': 0
}


@pytest.fixture(autouse=True)
def owntracks_http_cleanup(hass):
    """Remove known_devices.yaml."""
    try:
        os.remove(hass.config.path(device_tracker.YAML_DEVICES))
    except OSError:
        pass


@pytest.fixture
def mock_client(hass, aiohttp_client):
    """Start the Hass HTTP component."""
    mock_component(hass, 'group')
    mock_component(hass, 'zone')
    mock_component(hass, 'device_tracker')
    hass.data['device_tracker'] = Mock(
        async_see=Mock(return_value=mock_coro())
    )

    MockConfigEntry(domain='owntracks', data={
        'webhook_id': 'owntracks_test',
        'secret': 'abcd',
    }).add_to_hass(hass)
    hass.loop.run_until_complete(async_setup_component(hass, 'owntracks', {}))

    return hass.loop.run_until_complete(aiohttp_client(hass.http.app))


@asyncio.coroutine
def test_handle_valid_message(mock_client):
    """Test that we forward messages correctly to OwnTracks."""
    resp = yield from mock_client.post('/api/webhook/owntracks_test?'
                                       'u=test&d=test',
                                       json=LOCATION_MESSAGE)

    assert resp.status == 200

    json = yield from resp.json()
    assert json == []


@asyncio.coroutine
def test_handle_valid_minimal_message(mock_client):
    """Test that we forward messages correctly to OwnTracks."""
    resp = yield from mock_client.post('/api/webhook/owntracks_test?'
                                       'u=test&d=test',
                                       json=MINIMAL_LOCATION_MESSAGE)

    assert resp.status == 200

    json = yield from resp.json()
    assert json == []


@asyncio.coroutine
def test_handle_value_error(mock_client):
    """Test we don't disclose that this is a valid webhook."""
    resp = yield from mock_client.post('/api/webhook/owntracks_test'
                                       '?u=test&d=test', json='')

    assert resp.status == 200

    json = yield from resp.text()
    assert json == ""


@asyncio.coroutine
def test_returns_error_missing_username(mock_client):
    """Test that an error is returned when username is missing."""
    resp = yield from mock_client.post('/api/webhook/owntracks_test?d=test',
                                       json=LOCATION_MESSAGE)

    assert resp.status == 200

    json = yield from resp.json()
    assert json == {'error': 'You need to supply username.'}


@asyncio.coroutine
def test_returns_error_missing_device(mock_client):
    """Test that an error is returned when device name is missing."""
    resp = yield from mock_client.post('/api/webhook/owntracks_test?u=test',
                                       json=LOCATION_MESSAGE)

    assert resp.status == 200

    json = yield from resp.json()
    assert json == {'error': 'You need to supply device name.'}
