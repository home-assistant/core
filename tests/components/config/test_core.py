"""Test hassbian config."""
import asyncio
from unittest.mock import patch

from homeassistant.bootstrap import async_setup_component
from homeassistant.components import config
from homeassistant.components.websocket_api.const import TYPE_RESULT
from tests.common import mock_coro


async def test_validate_config_ok(hass, hass_client):
    """Test checking config."""
    with patch.object(config, 'SECTIONS', ['core']):
        await async_setup_component(hass, 'config', {})

    await asyncio.sleep(0.1, loop=hass.loop)

    client = await hass_client()

    with patch(
        'homeassistant.components.config.core.async_check_ha_config_file',
            return_value=mock_coro()):
        resp = await client.post('/api/config/core/check_config')

    assert resp.status == 200
    result = await resp.json()
    assert result['result'] == 'valid'
    assert result['errors'] is None

    with patch(
        'homeassistant.components.config.core.async_check_ha_config_file',
            return_value=mock_coro('beer')):
        resp = await client.post('/api/config/core/check_config')

    assert resp.status == 200
    result = await resp.json()
    assert result['result'] == 'invalid'
    assert result['errors'] == 'beer'


async def test_websocket_core_update(hass, hass_ws_client):
    """Test core config update websocket command."""
    with patch.object(config, 'SECTIONS', ['core']):
        await async_setup_component(hass, 'config', {})

    client = await hass_ws_client(hass)
    await client.send_json({
        'id': 5,
        'type': 'config/core/update',
        'latitude': 123,
    })

    msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success']


async def test_websocket_core_update_not_admin(
        hass, hass_ws_client, hass_admin_user):
    """Test core config fails for non admin."""
    hass_admin_user.groups = []
    with patch.object(config, 'SECTIONS', ['core']):
        await async_setup_component(hass, 'config', {})

    client = await hass_ws_client(hass)
    await client.send_json({
        'id': 6,
        'type': 'config/core/update',
        'latitude': 123,
    })

    msg = await client.receive_json()

    assert msg['id'] == 6
    assert msg['type'] == TYPE_RESULT
    assert not msg['success']
    assert msg['error']['code'] == 'unauthorized'


async def test_websocket_bad_core_update(hass, hass_ws_client):
    """Test core config update fails with bad parameters."""
    with patch.object(config, 'SECTIONS', ['core']):
        await async_setup_component(hass, 'config', {})

    client = await hass_ws_client(hass)
    await client.send_json({
        'id': 7,
        'type': 'config/core/update',
        'latituude': 123,
    })

    msg = await client.receive_json()

    assert msg['id'] == 7
    assert msg['type'] == TYPE_RESULT
    assert not msg['success']
    assert msg['error']['code'] == 'invalid_format'
