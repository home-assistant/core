"""Tests for the smartapp module."""
from unittest.mock import Mock, patch
from uuid import uuid4

from pysmartthings import AppEntity

from homeassistant.components.smartthings import smartapp
from homeassistant.components.smartthings.const import (
    DATA_MANAGER, DOMAIN, SUPPORTED_CAPABILITIES)

from tests.common import mock_coro


async def test_update_app(hass, app):
    """Test update_app does not save if app is current."""
    await smartapp.update_app(hass, app)
    assert app.save.call_count == 0


async def test_update_app_updated_needed(hass, app):
    """Test update_app updates when an app is needed."""
    mock_app = Mock(spec=AppEntity)
    mock_app.app_name = 'Test'
    mock_app.refresh.return_value = mock_coro()
    mock_app.save.return_value = mock_coro()

    await smartapp.update_app(hass, mock_app)

    assert mock_app.save.call_count == 1
    assert mock_app.app_name == 'Test'
    assert mock_app.display_name == app.display_name
    assert mock_app.description == app.description
    assert mock_app.webhook_target_url == app.webhook_target_url
    assert mock_app.app_type == app.app_type
    assert mock_app.single_instance == app.single_instance
    assert mock_app.classifications == app.classifications


async def test_smartapp_install_abort_if_no_other(hass, smartthings_mock):
    """Test aborts if no other app was configured already."""
    api = smartthings_mock.return_value
    api.create_subscription.return_value = mock_coro()
    app = Mock()
    app.app_id = uuid4()
    request = Mock()
    request.installed_app_id = uuid4()
    request.auth_token = uuid4()
    request.location_id = uuid4()

    await smartapp.smartapp_install(hass, request, None, app)

    entries = hass.config_entries.async_entries('smartthings')
    assert not entries
    assert api.create_subscription.call_count == \
        len(SUPPORTED_CAPABILITIES)


async def test_smartapp_install_creates_flow(
        hass, smartthings_mock, config_entry, location):
    """Test installation creates flow."""
    # Arrange
    setattr(hass.config_entries, '_entries', [config_entry])
    api = smartthings_mock.return_value
    api.create_subscription.return_value = mock_coro()
    app = Mock()
    app.app_id = config_entry.data['app_id']
    request = Mock()
    request.installed_app_id = str(uuid4())
    request.auth_token = str(uuid4())
    request.location_id = location.location_id
    # Act
    await smartapp.smartapp_install(hass, request, None, app)
    # Assert
    await hass.async_block_till_done()
    entries = hass.config_entries.async_entries('smartthings')
    assert len(entries) == 2
    assert api.create_subscription.call_count == \
        len(SUPPORTED_CAPABILITIES)
    assert entries[1].data['app_id'] == app.app_id
    assert entries[1].data['installed_app_id'] == request.installed_app_id
    assert entries[1].data['location_id'] == request.location_id
    assert entries[1].data['access_token'] == \
        config_entry.data['access_token']
    assert entries[1].title == location.name


async def test_smartapp_uninstall(hass, config_entry):
    """Test the config entry is unloaded when the app is uninstalled."""
    setattr(hass.config_entries, '_entries', [config_entry])
    app = Mock()
    app.app_id = config_entry.data['app_id']
    request = Mock()
    request.installed_app_id = config_entry.data['installed_app_id']

    with patch.object(hass.config_entries, 'async_remove',
                      return_value=mock_coro()) as remove:
        await smartapp.smartapp_uninstall(hass, request, None, app)
        assert remove.call_count == 1


async def test_smartapp_webhook(hass):
    """Test the smartapp webhook calls the manager."""
    manager = Mock()
    manager.handle_request = Mock()
    manager.handle_request.return_value = mock_coro(return_value={})
    hass.data[DOMAIN][DATA_MANAGER] = manager
    request = Mock()
    request.headers = []
    request.json.return_value = mock_coro(return_value={})
    result = await smartapp.smartapp_webhook(hass, '', request)

    assert result.body == b'{}'
