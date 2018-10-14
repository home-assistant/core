"""Test the Lovelace initialization."""
from unittest.mock import patch

from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
from homeassistant.components.websocket_api.const import TYPE_RESULT


async def test_deprecated_lovelace_ui(hass, hass_ws_client):
    """Test lovelace_ui command."""
    await async_setup_component(hass, 'lovelace')
    client = await hass_ws_client(hass)

    with patch('homeassistant.components.lovelace.load_yaml',
               return_value={'hello': 'world'}):
        await client.send_json({
            'id': 5,
            'type': 'frontend/lovelace_config',
        })
        msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success']
    assert msg['result'] == {'hello': 'world'}


async def test_deprecated_lovelace_ui_not_found(hass, hass_ws_client):
    """Test lovelace_ui command cannot find file."""
    await async_setup_component(hass, 'lovelace')
    client = await hass_ws_client(hass)

    with patch('homeassistant.components.lovelace.load_yaml',
               side_effect=FileNotFoundError):
        await client.send_json({
            'id': 5,
            'type': 'frontend/lovelace_config',
        })
        msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success'] is False
    assert msg['error']['code'] == 'file_not_found'


async def test_deprecated_lovelace_ui_load_err(hass, hass_ws_client):
    """Test lovelace_ui command cannot find file."""
    await async_setup_component(hass, 'lovelace')
    client = await hass_ws_client(hass)

    with patch('homeassistant.components.lovelace.load_yaml',
               side_effect=HomeAssistantError):
        await client.send_json({
            'id': 5,
            'type': 'frontend/lovelace_config',
        })
        msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success'] is False
    assert msg['error']['code'] == 'load_error'


async def test_lovelace_ui(hass, hass_ws_client):
    """Test lovelace_ui command."""
    await async_setup_component(hass, 'lovelace')
    client = await hass_ws_client(hass)

    with patch('homeassistant.components.lovelace.load_yaml',
               return_value={'hello': 'world'}):
        await client.send_json({
            'id': 5,
            'type': 'lovelace/config',
        })
        msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success']
    assert msg['result'] == {'hello': 'world'}


async def test_lovelace_ui_not_found(hass, hass_ws_client):
    """Test lovelace_ui command cannot find file."""
    await async_setup_component(hass, 'lovelace')
    client = await hass_ws_client(hass)

    with patch('homeassistant.components.lovelace.load_yaml',
               side_effect=FileNotFoundError):
        await client.send_json({
            'id': 5,
            'type': 'lovelace/config',
        })
        msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success'] is False
    assert msg['error']['code'] == 'file_not_found'


async def test_lovelace_ui_load_err(hass, hass_ws_client):
    """Test lovelace_ui command cannot find file."""
    await async_setup_component(hass, 'lovelace')
    client = await hass_ws_client(hass)

    with patch('homeassistant.components.lovelace.load_yaml',
               side_effect=HomeAssistantError):
        await client.send_json({
            'id': 5,
            'type': 'lovelace/config',
        })
        msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success'] is False
    assert msg['error']['code'] == 'load_error'
