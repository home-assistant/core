"""Test the Lovelace initialization."""
from unittest.mock import patch

from homeassistant.setup import async_setup_component
from homeassistant.components import frontend, lovelace


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
