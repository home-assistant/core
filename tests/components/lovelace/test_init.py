"""Test the Lovelace initialization."""
from unittest.mock import patch

from homeassistant.setup import async_setup_component
from homeassistant.components import frontend, lovelace

from tests.common import get_system_health_info


async def test_lovelace_from_storage(hass, hass_ws_client, hass_storage):
    """Test we load lovelace config from storage."""
    assert await async_setup_component(hass, 'lovelace', {})
    assert hass.data[frontend.DATA_PANELS]['lovelace'].config == {
        'mode': 'storage'
    }

    client = await hass_ws_client(hass)

    # Fetch data
    await client.send_json({
        'id': 5,
        'type': 'lovelace/config'
    })
    response = await client.receive_json()
    assert not response['success']
    assert response['error']['code'] == 'config_not_found'

    # Store new config
    await client.send_json({
        'id': 6,
        'type': 'lovelace/config/save',
        'config': {
            'yo': 'hello'
        }
    })
    response = await client.receive_json()
    assert response['success']
    assert hass_storage[lovelace.STORAGE_KEY]['data'] == {
        'config': {'yo': 'hello'}
    }

    # Load new config
    await client.send_json({
        'id': 7,
        'type': 'lovelace/config'
    })
    response = await client.receive_json()
    assert response['success']

    assert response['result'] == {
        'yo': 'hello'
    }


async def test_lovelace_from_storage_save_before_load(hass, hass_ws_client,
                                                      hass_storage):
    """Test we can load lovelace config from storage."""
    assert await async_setup_component(hass, 'lovelace', {})
    client = await hass_ws_client(hass)

    # Store new config
    await client.send_json({
        'id': 6,
        'type': 'lovelace/config/save',
        'config': {
            'yo': 'hello'
        }
    })
    response = await client.receive_json()
    assert response['success']
    assert hass_storage[lovelace.STORAGE_KEY]['data'] == {
        'config': {'yo': 'hello'}
    }


async def test_lovelace_from_yaml(hass, hass_ws_client):
    """Test we load lovelace config from yaml."""
    assert await async_setup_component(hass, 'lovelace', {
        'lovelace': {
            'mode': 'YAML'
        }
    })
    assert hass.data[frontend.DATA_PANELS]['lovelace'].config == {
        'mode': 'yaml'
    }

    client = await hass_ws_client(hass)

    # Fetch data
    await client.send_json({
        'id': 5,
        'type': 'lovelace/config'
    })
    response = await client.receive_json()
    assert not response['success']

    assert response['error']['code'] == 'config_not_found'

    # Store new config not allowed
    await client.send_json({
        'id': 6,
        'type': 'lovelace/config/save',
        'config': {
            'yo': 'hello'
        }
    })
    response = await client.receive_json()
    assert not response['success']

    # Patch data
    with patch('homeassistant.components.lovelace.load_yaml', return_value={
        'hello': 'yo'
    }):
        await client.send_json({
            'id': 7,
            'type': 'lovelace/config'
        })
        response = await client.receive_json()

    assert response['success']
    assert response['result'] == {'hello': 'yo'}


async def test_system_health_info_autogen(hass):
    """Test system health info endpoint."""
    assert await async_setup_component(hass, 'lovelace', {})
    info = await get_system_health_info(hass, 'lovelace')
    assert info == {'mode': 'auto-gen'}


async def test_system_health_info_storage(hass, hass_storage):
    """Test system health info endpoint."""
    hass_storage[lovelace.STORAGE_KEY] = {
        'key': 'lovelace',
        'version': 1,
        'data': {
            'config': {
                'resources': [],
                'views': []
            }
        }
    }
    assert await async_setup_component(hass, 'lovelace', {})
    info = await get_system_health_info(hass, 'lovelace')
    assert info == {
        'mode': 'storage',
        'resources': 0,
        'views': 0,
    }


async def test_system_health_info_yaml(hass):
    """Test system health info endpoint."""
    assert await async_setup_component(hass, 'lovelace', {
        'lovelace': {
            'mode': 'YAML'
        }
    })
    with patch('homeassistant.components.lovelace.load_yaml', return_value={
        'views': [
            {
                'cards': []
            }
        ]
    }):
        info = await get_system_health_info(hass, 'lovelace')
    assert info == {
        'mode': 'yaml',
        'resources': 0,
        'views': 1,
    }


async def test_system_health_info_yaml_not_found(hass):
    """Test system health info endpoint."""
    assert await async_setup_component(hass, 'lovelace', {
        'lovelace': {
            'mode': 'YAML'
        }
    })
    info = await get_system_health_info(hass, 'lovelace')
    assert info == {
        'mode': 'yaml',
        'error': "{} not found".format(hass.config.path('ui-lovelace.yaml'))
    }
