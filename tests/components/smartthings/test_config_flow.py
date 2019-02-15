"""Tests for the SmartThings config flow module."""
from unittest.mock import Mock, patch
from uuid import uuid4

from aiohttp import ClientResponseError
from pysmartthings import APIResponseError

from homeassistant import data_entry_flow
from homeassistant.components.smartthings.config_flow import (
    SmartThingsFlowHandler)
from homeassistant.config_entries import ConfigEntry

from tests.common import mock_coro


async def test_step_user(hass):
    """Test the access token form is shown for a user initiated flow."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user()

    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'user'


async def test_step_init(hass):
    """Test the access token form is shown for an init flow."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass
    result = await flow.async_step_import()

    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'user'


async def test_base_url_not_https(hass):
    """Test the base_url parameter starts with https://."""
    hass.config.api.base_url = 'http://0.0.0.0'
    flow = SmartThingsFlowHandler()
    flow.hass = hass
    result = await flow.async_step_import()

    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'user'
    assert result['errors'] == {'base': 'base_url_not_https'}


async def test_invalid_token_format(hass):
    """Test an error is shown for invalid token formats."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user({'access_token': '123456789'})

    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'user'
    assert result['errors'] == {'access_token': 'token_invalid_format'}


async def test_token_already_setup(hass):
    """Test an error is shown when the token is already setup."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass
    token = str(uuid4())
    entries = [ConfigEntry(
        version='', domain='', title='', data={'access_token': token},
        source='', connection_class='')]

    with patch.object(hass.config_entries, 'async_entries',
                      return_value=entries):
        result = await flow.async_step_user({'access_token': token})

    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'user'
    assert result['errors'] == {'access_token': 'token_already_setup'}


async def test_token_unauthorized(hass, smartthings_mock):
    """Test an error is shown when the token is not authorized."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass

    smartthings_mock.return_value.apps.return_value = mock_coro(
        exception=ClientResponseError(None, None, status=401))

    result = await flow.async_step_user({'access_token': str(uuid4())})

    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'user'
    assert result['errors'] == {'access_token': 'token_unauthorized'}


async def test_token_forbidden(hass, smartthings_mock):
    """Test an error is shown when the token is forbidden."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass

    smartthings_mock.return_value.apps.return_value = mock_coro(
        exception=ClientResponseError(None, None, status=403))

    result = await flow.async_step_user({'access_token': str(uuid4())})

    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'user'
    assert result['errors'] == {'access_token': 'token_forbidden'}


async def test_webhook_error(hass, smartthings_mock):
    """Test an error is when there's an error with the webhook endpoint."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass

    data = {'error': {}}
    error = APIResponseError(None, None, data=data, status=422)
    error.is_target_error = Mock(return_value=True)

    smartthings_mock.return_value.apps.return_value = mock_coro(
        exception=error)

    result = await flow.async_step_user({'access_token': str(uuid4())})

    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'user'
    assert result['errors'] == {'base': 'webhook_error'}


async def test_api_error(hass, smartthings_mock):
    """Test an error is shown when other API errors occur."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass

    data = {'error': {}}
    error = APIResponseError(None, None, data=data, status=400)

    smartthings_mock.return_value.apps.return_value = mock_coro(
        exception=error)

    result = await flow.async_step_user({'access_token': str(uuid4())})

    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'user'
    assert result['errors'] == {'base': 'app_setup_error'}


async def test_unknown_api_error(hass, smartthings_mock):
    """Test an error is shown when there is an unknown API error."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass

    smartthings_mock.return_value.apps.return_value = mock_coro(
        exception=ClientResponseError(None, None, status=404))

    result = await flow.async_step_user({'access_token': str(uuid4())})

    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'user'
    assert result['errors'] == {'base': 'app_setup_error'}


async def test_unknown_error(hass, smartthings_mock):
    """Test an error is shown when there is an unknown API error."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass

    smartthings_mock.return_value.apps.return_value = mock_coro(
        exception=Exception('Unknown error'))

    result = await flow.async_step_user({'access_token': str(uuid4())})

    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'user'
    assert result['errors'] == {'base': 'app_setup_error'}


async def test_app_created_then_show_wait_form(hass, app, smartthings_mock):
    """Test SmartApp is created when one does not exist and shows wait form."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass

    smartthings = smartthings_mock.return_value
    smartthings.apps.return_value = mock_coro(return_value=[])
    smartthings.create_app.return_value = mock_coro(return_value=(app, None))
    smartthings.update_app_settings.return_value = mock_coro()
    smartthings.update_app_oauth.return_value = mock_coro()

    result = await flow.async_step_user({'access_token': str(uuid4())})

    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'wait_install'


async def test_app_updated_then_show_wait_form(
        hass, app, smartthings_mock):
    """Test SmartApp is updated when an existing is already created."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass

    api = smartthings_mock.return_value
    api.apps.return_value = mock_coro(return_value=[app])

    result = await flow.async_step_user({'access_token': str(uuid4())})

    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'wait_install'


async def test_wait_form_displayed(hass):
    """Test the wait for installation form is displayed."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass

    result = await flow.async_step_wait_install(None)

    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'wait_install'


async def test_wait_form_displayed_after_checking(hass, smartthings_mock):
    """Test error is shown when the user has not installed the app."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass
    flow.access_token = str(uuid4())
    flow.api = smartthings_mock.return_value
    flow.api.installed_apps.return_value = mock_coro(return_value=[])

    result = await flow.async_step_wait_install({})

    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'wait_install'
    assert result['errors'] == {'base': 'app_not_installed'}


async def test_config_entry_created_when_installed(
        hass, location, installed_app, smartthings_mock):
    """Test a config entry is created once the app is installed."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass
    flow.access_token = str(uuid4())
    flow.api = smartthings_mock.return_value
    flow.app_id = installed_app.app_id
    flow.api.installed_apps.return_value = \
        mock_coro(return_value=[installed_app])

    result = await flow.async_step_wait_install({})

    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result['data']['app_id'] == installed_app.app_id
    assert result['data']['installed_app_id'] == \
        installed_app.installed_app_id
    assert result['data']['location_id'] == installed_app.location_id
    assert result['data']['access_token'] == flow.access_token
    assert result['title'] == location.name


async def test_multiple_config_entry_created_when_installed(
        hass, app, locations, installed_apps, smartthings_mock):
    """Test a config entries are created for multiple installs."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass
    flow.access_token = str(uuid4())
    flow.app_id = app.app_id
    flow.api = smartthings_mock.return_value
    flow.api.installed_apps.return_value = \
        mock_coro(return_value=installed_apps)

    result = await flow.async_step_wait_install({})

    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result['data']['app_id'] == installed_apps[0].app_id
    assert result['data']['installed_app_id'] == \
        installed_apps[0].installed_app_id
    assert result['data']['location_id'] == installed_apps[0].location_id
    assert result['data']['access_token'] == flow.access_token
    assert result['title'] == locations[0].name

    await hass.async_block_till_done()
    entries = hass.config_entries.async_entries('smartthings')
    assert len(entries) == 1
    assert entries[0].data['app_id'] == installed_apps[1].app_id
    assert entries[0].data['installed_app_id'] == \
        installed_apps[1].installed_app_id
    assert entries[0].data['location_id'] == installed_apps[1].location_id
    assert entries[0].data['access_token'] == flow.access_token
    assert entries[0].title == locations[1].name
