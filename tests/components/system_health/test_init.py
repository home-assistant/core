"""Tests for the system health component init."""
from unittest.mock import patch

import pytest

from homeassistant.setup import async_setup_component

from tests.common import mock_coro


@pytest.fixture
def mock_system_info():
    """Mock system info."""
    with patch('homeassistant.components.updater.get_system_info',
               return_value=mock_coro({'hello': True})):
        yield


async def test_info_endpoint_requires_auth(hass, aiohttp_client):
    """Test that the info endpoint requires auth."""
    assert await async_setup_component(hass, 'system_health', {})
    client = await aiohttp_client(hass.http.app)
    resp = await client.get('/api/system_health/info')
    assert resp.status == 401


async def test_info_endpoint_return_info(hass, hass_client,
                                         mock_system_info):
    """Test that the info endpoint requires auth."""
    assert await async_setup_component(hass, 'system_health', {})
    client = await hass_client()

    resp = await client.get('/api/system_health/info')
    assert resp.status == 200
    data = await resp.json()

    assert len(data) == 1
    data = data['homeassistant']
    assert data == {'hello': True}


async def test_info_endpoint_register_callback(hass, hass_client,
                                               mock_system_info):
    """Test that the info endpoint requires auth."""
    hass.components.system_health.async_register_info(
        'lovelace', lambda hass: {'storage': 'YAML'})
    assert await async_setup_component(hass, 'system_health', {})
    client = await hass_client()

    resp = await client.get('/api/system_health/info')
    assert resp.status == 200
    data = await resp.json()

    assert len(data) == 2
    data = data['lovelace']
    assert data == {'storage': 'YAML'}
    assert False, data
