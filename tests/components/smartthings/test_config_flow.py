"""Tests for the SmartThings config flow module."""
from uuid import uuid4

from aiohttp import ClientResponseError
from asynctest import Mock, patch
from pysmartthings import APIResponseError

from homeassistant import data_entry_flow
from homeassistant.components.smartthings import smartapp
from homeassistant.components.smartthings.config_flow import SmartThingsFlowHandler
from homeassistant.components.smartthings.const import (
    CONF_INSTALLED_APP_ID,
    CONF_INSTALLED_APPS,
    CONF_LOCATION_ID,
    CONF_REFRESH_TOKEN,
    DOMAIN,
)
from homeassistant.const import HTTP_FORBIDDEN, HTTP_NOT_FOUND
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, mock_coro


async def test_step_user(hass):
    """Test the access token form is shown for a user initiated flow."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user()

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_step_init(hass):
    """Test the access token form is shown for an init flow."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass
    result = await flow.async_step_import()

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_base_url_not_https(hass):
    """Test the base_url parameter starts with https://."""
    hass.config.api.base_url = "http://0.0.0.0"
    flow = SmartThingsFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user({"access_token": str(uuid4())})

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "base_url_not_https"}


async def test_invalid_token_format(hass):
    """Test an error is shown for invalid token formats."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user({"access_token": "123456789"})

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"access_token": "token_invalid_format"}


async def test_token_already_setup(hass):
    """Test an error is shown when the token is already setup."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass
    token = str(uuid4())
    entry = MockConfigEntry(domain=DOMAIN, data={"access_token": token})
    entry.add_to_hass(hass)

    result = await flow.async_step_user({"access_token": token})

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"access_token": "token_already_setup"}


async def test_token_unauthorized(hass, smartthings_mock):
    """Test an error is shown when the token is not authorized."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass

    request_info = Mock(real_url="http://example.com")
    smartthings_mock.apps.side_effect = ClientResponseError(
        request_info=request_info, history=None, status=401
    )

    result = await flow.async_step_user({"access_token": str(uuid4())})

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"access_token": "token_unauthorized"}


async def test_token_forbidden(hass, smartthings_mock):
    """Test an error is shown when the token is forbidden."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass

    request_info = Mock(real_url="http://example.com")
    smartthings_mock.apps.side_effect = ClientResponseError(
        request_info=request_info, history=None, status=HTTP_FORBIDDEN
    )

    result = await flow.async_step_user({"access_token": str(uuid4())})

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"access_token": "token_forbidden"}


async def test_webhook_error(hass, smartthings_mock):
    """Test an error is when there's an error with the webhook endpoint."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass

    data = {"error": {}}
    request_info = Mock(real_url="http://example.com")
    error = APIResponseError(
        request_info=request_info, history=None, data=data, status=422
    )
    error.is_target_error = Mock(return_value=True)

    smartthings_mock.apps.side_effect = error

    result = await flow.async_step_user({"access_token": str(uuid4())})

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "webhook_error"}


async def test_api_error(hass, smartthings_mock):
    """Test an error is shown when other API errors occur."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass

    data = {"error": {}}
    request_info = Mock(real_url="http://example.com")
    error = APIResponseError(
        request_info=request_info, history=None, data=data, status=400
    )

    smartthings_mock.apps.side_effect = error

    result = await flow.async_step_user({"access_token": str(uuid4())})

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "app_setup_error"}


async def test_unknown_api_error(hass, smartthings_mock):
    """Test an error is shown when there is an unknown API error."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass

    request_info = Mock(real_url="http://example.com")
    smartthings_mock.apps.side_effect = ClientResponseError(
        request_info=request_info, history=None, status=HTTP_NOT_FOUND
    )

    result = await flow.async_step_user({"access_token": str(uuid4())})

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "app_setup_error"}


async def test_unknown_error(hass, smartthings_mock):
    """Test an error is shown when there is an unknown API error."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass

    smartthings_mock.apps.side_effect = Exception("Unknown error")

    result = await flow.async_step_user({"access_token": str(uuid4())})

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "app_setup_error"}


async def test_app_created_then_show_wait_form(
    hass, app, app_oauth_client, smartthings_mock
):
    """Test SmartApp is created when one does not exist and shows wait form."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass

    smartthings_mock.apps.return_value = []
    smartthings_mock.create_app.return_value = (app, app_oauth_client)

    result = await flow.async_step_user({"access_token": str(uuid4())})

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "wait_install"


async def test_cloudhook_app_created_then_show_wait_form(
    hass, app, app_oauth_client, smartthings_mock
):
    """Test SmartApp is created with a cloudhoko and shows wait form."""
    hass.config.components.add("cloud")

    # Unload the endpoint so we can reload it under the cloud.
    await smartapp.unload_smartapp_endpoint(hass)

    with patch.object(
        hass.components.cloud, "async_active_subscription", return_value=True
    ), patch.object(
        hass.components.cloud,
        "async_create_cloudhook",
        return_value=mock_coro("http://cloud.test"),
    ) as mock_create_cloudhook:

        await smartapp.setup_smartapp_endpoint(hass)

        flow = SmartThingsFlowHandler()
        flow.hass = hass
        smartthings_mock.apps.return_value = []
        smartthings_mock.create_app.return_value = (app, app_oauth_client)

        result = await flow.async_step_user({"access_token": str(uuid4())})

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "wait_install"
        assert mock_create_cloudhook.call_count == 1


async def test_app_updated_then_show_wait_form(
    hass, app, app_oauth_client, smartthings_mock
):
    """Test SmartApp is updated when an existing is already created."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass

    smartthings_mock.apps.return_value = [app]
    smartthings_mock.generate_app_oauth.return_value = app_oauth_client

    result = await flow.async_step_user({"access_token": str(uuid4())})

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "wait_install"


async def test_wait_form_displayed(hass):
    """Test the wait for installation form is displayed."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass

    result = await flow.async_step_wait_install(None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "wait_install"


async def test_wait_form_displayed_after_checking(hass, smartthings_mock):
    """Test error is shown when the user has not installed the app."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass
    flow.access_token = str(uuid4())

    result = await flow.async_step_wait_install({})

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "wait_install"
    assert result["errors"] == {"base": "app_not_installed"}


async def test_config_entry_created_when_installed(
    hass, location, installed_app, smartthings_mock
):
    """Test a config entry is created once the app is installed."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass
    flow.access_token = str(uuid4())
    flow.app_id = installed_app.app_id
    flow.api = smartthings_mock
    flow.oauth_client_id = str(uuid4())
    flow.oauth_client_secret = str(uuid4())
    data = {
        CONF_REFRESH_TOKEN: str(uuid4()),
        CONF_LOCATION_ID: installed_app.location_id,
        CONF_INSTALLED_APP_ID: installed_app.installed_app_id,
    }
    hass.data[DOMAIN][CONF_INSTALLED_APPS].append(data)

    result = await flow.async_step_wait_install({})

    assert not hass.data[DOMAIN][CONF_INSTALLED_APPS]
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"]["app_id"] == installed_app.app_id
    assert result["data"]["installed_app_id"] == installed_app.installed_app_id
    assert result["data"]["location_id"] == installed_app.location_id
    assert result["data"]["access_token"] == flow.access_token
    assert result["data"]["refresh_token"] == data[CONF_REFRESH_TOKEN]
    assert result["data"]["client_secret"] == flow.oauth_client_secret
    assert result["data"]["client_id"] == flow.oauth_client_id
    assert result["title"] == location.name


async def test_multiple_config_entry_created_when_installed(
    hass, app, locations, installed_apps, smartthings_mock
):
    """Test a config entries are created for multiple installs."""
    assert await async_setup_component(hass, "persistent_notification", {})
    flow = SmartThingsFlowHandler()
    flow.hass = hass
    flow.access_token = str(uuid4())
    flow.app_id = app.app_id
    flow.api = smartthings_mock
    flow.oauth_client_id = str(uuid4())
    flow.oauth_client_secret = str(uuid4())
    for installed_app in installed_apps:
        data = {
            CONF_REFRESH_TOKEN: str(uuid4()),
            CONF_LOCATION_ID: installed_app.location_id,
            CONF_INSTALLED_APP_ID: installed_app.installed_app_id,
        }
        hass.data[DOMAIN][CONF_INSTALLED_APPS].append(data)
    install_data = hass.data[DOMAIN][CONF_INSTALLED_APPS].copy()

    result = await flow.async_step_wait_install({})

    assert not hass.data[DOMAIN][CONF_INSTALLED_APPS]

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"]["app_id"] == installed_apps[0].app_id
    assert result["data"]["installed_app_id"] == installed_apps[0].installed_app_id
    assert result["data"]["location_id"] == installed_apps[0].location_id
    assert result["data"]["access_token"] == flow.access_token
    assert result["data"]["refresh_token"] == install_data[0][CONF_REFRESH_TOKEN]
    assert result["data"]["client_secret"] == flow.oauth_client_secret
    assert result["data"]["client_id"] == flow.oauth_client_id
    assert result["title"] == locations[0].name

    await hass.async_block_till_done()
    entries = hass.config_entries.async_entries("smartthings")
    assert len(entries) == 1
    assert entries[0].data["app_id"] == installed_apps[1].app_id
    assert entries[0].data["installed_app_id"] == installed_apps[1].installed_app_id
    assert entries[0].data["location_id"] == installed_apps[1].location_id
    assert entries[0].data["access_token"] == flow.access_token
    assert entries[0].data["client_secret"] == flow.oauth_client_secret
    assert entries[0].data["client_id"] == flow.oauth_client_id
    assert entries[0].title == locations[1].name
