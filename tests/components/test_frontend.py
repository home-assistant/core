"""The tests for Home Assistant frontend."""
import asyncio
import re

import pytest

from homeassistant.setup import async_setup_component


@pytest.fixture
def mock_http_client(hass, test_client):
    """Start the Hass HTTP component."""
    hass.loop.run_until_complete(async_setup_component(hass, 'frontend', {}))
    return hass.loop.run_until_complete(test_client(hass.http.app))


@asyncio.coroutine
def test_frontend_and_static(mock_http_client):
    """Test if we can get the frontend."""
    resp = yield from mock_http_client.get('')
    assert resp.status == 200
    assert 'cache-control' not in resp.headers

    text = yield from resp.text()

    # Test we can retrieve frontend.js
    frontendjs = re.search(
        r'(?P<app>\/static\/frontend-[A-Za-z0-9]{32}.html)', text)

    assert frontendjs is not None
    resp = yield from mock_http_client.get(frontendjs.groups(0)[0])
    assert resp.status == 200
    assert 'public' in resp.headers.get('cache-control')


@asyncio.coroutine
def test_dont_cache_service_worker(mock_http_client):
    """Test that we don't cache the service worker."""
    resp = yield from mock_http_client.get('/service_worker.js')
    assert resp.status == 200
    assert 'cache-control' not in resp.headers


@asyncio.coroutine
def test_404(mock_http_client):
    """Test for HTTP 404 error."""
    resp = yield from mock_http_client.get('/not-existing')
    assert resp.status == 404


@asyncio.coroutine
def test_we_cannot_POST_to_root(mock_http_client):
    """Test that POST is not allow to root."""
    resp = yield from mock_http_client.post('/')
    assert resp.status == 405


@asyncio.coroutine
def test_states_routes(hass, mock_http_client):
    """All served by index."""
    resp = yield from mock_http_client.get('/states')
    assert resp.status == 200

    resp = yield from mock_http_client.get('/states/group.non_existing')
    assert resp.status == 404

    hass.states.async_set('group.existing', 'on', {'view': True})
    resp = yield from mock_http_client.get('/states/group.existing')
    assert resp.status == 200
