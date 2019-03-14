"""Test the cloud component."""
from unittest.mock import patch

from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.components import cloud
from homeassistant.components.cloud.const import DOMAIN
from homeassistant.components.cloud.prefs import STORAGE_KEY
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)
from homeassistant.setup import async_setup_component
from tests.common import mock_coro


async def test_constructor_loads_info_from_config(hass):
    """Test non-dev mode loads info from SERVERS constant."""
    with patch("hass_nabucasa.Cloud.start", return_value=mock_coro()):
        result = await async_setup_component(hass, 'cloud', {
            'http': {},
            'cloud': {
                cloud.CONF_MODE: cloud.MODE_DEV,
                'cognito_client_id': 'test-cognito_client_id',
                'user_pool_id': 'test-user_pool_id',
                'region': 'test-region',
                'relayer': 'test-relayer',
            }
        })
        assert result

    cl = hass.data['cloud']
    assert cl.mode == cloud.MODE_DEV
    assert cl.cognito_client_id == 'test-cognito_client_id'
    assert cl.user_pool_id == 'test-user_pool_id'
    assert cl.region == 'test-region'
    assert cl.relayer == 'test-relayer'


async def test_remote_services(hass, mock_cloud_fixture):
    """Setup cloud component and test services."""
    cloud = hass.data[DOMAIN]

    assert hass.services.has_service(DOMAIN, 'remote_connect')
    assert hass.services.has_service(DOMAIN, 'remote_disconnect')

    with patch(
        "hass_nabucasa.remote.RemoteUI.connect", return_value=mock_coro()
    ) as mock_connect:
        await hass.services.async_call(DOMAIN, "remote_connect", blocking=True)

    assert mock_connect.called
    assert cloud.client.remote_autostart

    with patch(
        "hass_nabucasa.remote.RemoteUI.disconnect", return_value=mock_coro()
    ) as mock_disconnect:
        await hass.services.async_call(
            DOMAIN, "remote_disconnect", blocking=True)

    assert mock_disconnect.called
    assert not cloud.client.remote_autostart


async def test_startup_shutdown_events(hass, mock_cloud_fixture):
    """Test if the cloud will start on startup event."""
    with patch(
        "hass_nabucasa.Cloud.start", return_value=mock_coro()
    ) as mock_start:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

    assert mock_start.called

    with patch(
        "hass_nabucasa.Cloud.stop", return_value=mock_coro()
    ) as mock_stop:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

    assert mock_stop.called


async def test_setup_existing_cloud_user(hass, hass_storage):
    """Test setup with API push default data."""
    user = await hass.auth.async_create_system_user('Cloud test')
    hass_storage[STORAGE_KEY] = {
        'version': 1,
        'data': {
            'cloud_user': user.id
        }
    }
    with patch('hass_nabucasa.Cloud.start', return_value=mock_coro()):
        result = await async_setup_component(hass, 'cloud', {
            'http': {},
            'cloud': {
                cloud.CONF_MODE: cloud.MODE_DEV,
                'cognito_client_id': 'test-cognito_client_id',
                'user_pool_id': 'test-user_pool_id',
                'region': 'test-region',
                'relayer': 'test-relayer',
            }
        })
        assert result

    assert hass_storage[STORAGE_KEY]['data']['cloud_user'] == user.id


async def test_setup_setup_cloud_user(hass, hass_storage):
    """Test setup with API push default data."""
    hass_storage[STORAGE_KEY] = {
        'version': 1,
        'data': {
            'cloud_user': None
        }
    }
    with patch('hass_nabucasa.Cloud.start', return_value=mock_coro()):
        result = await async_setup_component(hass, 'cloud', {
            'http': {},
            'cloud': {
                cloud.CONF_MODE: cloud.MODE_DEV,
                'cognito_client_id': 'test-cognito_client_id',
                'user_pool_id': 'test-user_pool_id',
                'region': 'test-region',
                'relayer': 'test-relayer',
            }
        })
        assert result

    cloud_user = await hass.auth.async_get_user(
        hass_storage[STORAGE_KEY]['data']['cloud_user']
    )

    assert cloud_user
    assert cloud_user.groups[0].id == GROUP_ID_ADMIN
