"""Test the owntracks_http platform."""
import asyncio

import pytest

from homeassistant.setup import async_setup_component

from tests.common import mock_component, MockConfigEntry

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
def mock_dev_track(mock_device_tracker_conf):
    """Mock device tracker config loading."""
    pass


@pytest.fixture
def mock_client(hass, aiohttp_client):
    """Start the Hass HTTP component."""
    mock_component(hass, 'group')
    mock_component(hass, 'zone')
    mock_component(hass, 'device_tracker')

    MockConfigEntry(domain='owntracks', data={
        'webhook_id': 'owntracks_test',
        'secret': 'abcd',
    }).add_to_hass(hass)
    hass.loop.run_until_complete(async_setup_component(hass, 'owntracks', {}))

    return hass.loop.run_until_complete(aiohttp_client(hass.http.app))


@asyncio.coroutine
def test_handle_valid_message(mock_client):
    """Test that we forward messages correctly to OwnTracks."""
    resp = yield from mock_client.post(
        '/api/webhook/owntracks_test',
        json=LOCATION_MESSAGE,
        headers={
            'X-Limit-u': 'Paulus',
            'X-Limit-d': 'Pixel',
        }
    )

    assert resp.status == 200

    json = yield from resp.json()
    assert json == []


@asyncio.coroutine
def test_handle_valid_minimal_message(mock_client):
    """Test that we forward messages correctly to OwnTracks."""
    resp = yield from mock_client.post(
        '/api/webhook/owntracks_test',
        json=MINIMAL_LOCATION_MESSAGE,
        headers={
            'X-Limit-u': 'Paulus',
            'X-Limit-d': 'Pixel',
        }
    )

    assert resp.status == 200

    json = yield from resp.json()
    assert json == []


@asyncio.coroutine
def test_handle_value_error(mock_client):
    """Test we don't disclose that this is a valid webhook."""
    resp = yield from mock_client.post(
        '/api/webhook/owntracks_test',
        json='',
        headers={
            'X-Limit-u': 'Paulus',
            'X-Limit-d': 'Pixel',
        }
    )

    assert resp.status == 200

    json = yield from resp.text()
    assert json == ""


@asyncio.coroutine
def test_returns_error_missing_username(mock_client, caplog):
    """Test that an error is returned when username is missing."""
    resp = yield from mock_client.post(
        '/api/webhook/owntracks_test',
        json=LOCATION_MESSAGE,
        headers={
            'X-Limit-d': 'Pixel',
        }
    )

    # Needs to be 200 or OwnTracks keeps retrying bad packet.
    assert resp.status == 200
    json = yield from resp.json()
    assert json == []
    assert 'No topic or user found' in caplog.text


@asyncio.coroutine
def test_returns_error_incorrect_json(mock_client, caplog):
    """Test that an error is returned when username is missing."""
    resp = yield from mock_client.post(
        '/api/webhook/owntracks_test',
        data='not json',
        headers={
            'X-Limit-d': 'Pixel',
        }
    )

    # Needs to be 200 or OwnTracks keeps retrying bad packet.
    assert resp.status == 200
    json = yield from resp.json()
    assert json == []
    assert 'invalid JSON' in caplog.text


@asyncio.coroutine
def test_returns_error_missing_device(mock_client):
    """Test that an error is returned when device name is missing."""
    resp = yield from mock_client.post(
        '/api/webhook/owntracks_test',
        json=LOCATION_MESSAGE,
        headers={
            'X-Limit-u': 'Paulus',
        }
    )

    assert resp.status == 200

    json = yield from resp.json()
    assert json == []


async def test_config_flow_import(hass):
    """Test that we automatically create a config flow."""
    assert not hass.config_entries.async_entries('owntracks')
    assert await async_setup_component(hass, 'owntracks', {
        'owntracks': {

        }
    })
    await hass.async_block_till_done()
    assert hass.config_entries.async_entries('owntracks')
