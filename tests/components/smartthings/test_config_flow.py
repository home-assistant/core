"""Tests for the SmartThings config flow module."""
from uuid import uuid4

from aiohttp import ClientResponseError
from asynctest import Mock, patch
from pysmartthings import APIResponseError
from pysmartthings.installedapp import format_install_url

from homeassistant import data_entry_flow
from homeassistant.components.smartthings import smartapp
from homeassistant.components.smartthings.config_flow import SmartThingsFlowHandler
from homeassistant.components.smartthings.const import (
    CONF_APP_ID,
    CONF_INSTALLED_APP_ID,
    CONF_LOCATION_ID,
    CONF_OAUTH_CLIENT_ID,
    CONF_OAUTH_CLIENT_SECRET,
    CONF_REFRESH_TOKEN,
    DOMAIN,
)
from homeassistant.const import CONF_ACCESS_TOKEN, HTTP_FORBIDDEN, HTTP_NOT_FOUND

from tests.common import MockConfigEntry, mock_coro


async def test_step_import(hass):
    """Test import returns user."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass

    result = await flow.async_step_import()

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["description_placeholders"][
        "webhook_url"
    ] == smartapp.get_webhook_url(hass)


async def test_step_user(hass):
    """Test the webhook confirmation is shown."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user()

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["description_placeholders"][
        "webhook_url"
    ] == smartapp.get_webhook_url(hass)


async def test_step_user_aborts_invalid_webhook(hass):
    """Test flow aborts if webhook is invalid."""
    hass.config.api.base_url = "http://0.0.0.0"
    flow = SmartThingsFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user()

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "invalid_webhook_url"
    assert result["description_placeholders"][
        "webhook_url"
    ] == smartapp.get_webhook_url(hass)
    assert "component_url" in result["description_placeholders"]


async def test_step_user_advances_to_pat(hass):
    """Test user step advances to the pat step."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user({})

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "pat"


async def test_step_pat(hass):
    """Test pat step shows the input form."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass

    result = await flow.async_step_pat()

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "pat"
    assert result["errors"] == {}
    assert result["data_schema"]({CONF_ACCESS_TOKEN: ""}) == {CONF_ACCESS_TOKEN: ""}
    assert "token_url" in result["description_placeholders"]
    assert "component_url" in result["description_placeholders"]


async def test_step_pat_defaults_token(hass):
    """Test pat form defaults the token from another entry."""
    token = str(uuid4())
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_ACCESS_TOKEN: token})
    entry.add_to_hass(hass)
    flow = SmartThingsFlowHandler()
    flow.hass = hass

    result = await flow.async_step_pat()

    assert flow.access_token == token
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "pat"
    assert result["errors"] == {}
    assert result["data_schema"]({}) == {CONF_ACCESS_TOKEN: token}
    assert "token_url" in result["description_placeholders"]
    assert "component_url" in result["description_placeholders"]


async def test_step_pat_invalid_token(hass):
    """Test an error is shown for invalid token formats."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass
    token = "123456789"

    result = await flow.async_step_pat({CONF_ACCESS_TOKEN: token})

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "pat"
    assert result["data_schema"]({}) == {CONF_ACCESS_TOKEN: token}
    assert result["errors"] == {"access_token": "token_invalid_format"}
    assert "token_url" in result["description_placeholders"]
    assert "component_url" in result["description_placeholders"]


async def test_step_pat_unauthorized(hass, smartthings_mock):
    """Test an error is shown when the token is not authorized."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass
    request_info = Mock(real_url="http://example.com")
    smartthings_mock.apps.side_effect = ClientResponseError(
        request_info=request_info, history=None, status=401
    )
    token = str(uuid4())

    result = await flow.async_step_pat({CONF_ACCESS_TOKEN: token})

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "pat"
    assert result["errors"] == {CONF_ACCESS_TOKEN: "token_unauthorized"}
    assert result["data_schema"]({}) == {CONF_ACCESS_TOKEN: token}


async def test_step_pat_forbidden(hass, smartthings_mock):
    """Test an error is shown when the token is forbidden."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass
    request_info = Mock(real_url="http://example.com")
    smartthings_mock.apps.side_effect = ClientResponseError(
        request_info=request_info, history=None, status=HTTP_FORBIDDEN
    )
    token = str(uuid4())

    result = await flow.async_step_pat({CONF_ACCESS_TOKEN: token})

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "pat"
    assert result["errors"] == {CONF_ACCESS_TOKEN: "token_forbidden"}
    assert result["data_schema"]({}) == {CONF_ACCESS_TOKEN: token}


async def test_step_pat_webhook_error(hass, smartthings_mock):
    """Test an error is shown when there's an problem with the webhook endpoint."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass
    data = {"error": {}}
    request_info = Mock(real_url="http://example.com")
    error = APIResponseError(
        request_info=request_info, history=None, data=data, status=422
    )
    error.is_target_error = Mock(return_value=True)
    smartthings_mock.apps.side_effect = error
    token = str(uuid4())

    result = await flow.async_step_pat({CONF_ACCESS_TOKEN: token})

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "pat"
    assert result["errors"] == {"base": "webhook_error"}
    assert result["data_schema"]({}) == {CONF_ACCESS_TOKEN: token}


async def test_step_pat_api_error(hass, smartthings_mock):
    """Test an error is shown when other API errors occur."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass
    data = {"error": {}}
    request_info = Mock(real_url="http://example.com")
    error = APIResponseError(
        request_info=request_info, history=None, data=data, status=400
    )
    smartthings_mock.apps.side_effect = error
    token = str(uuid4())

    result = await flow.async_step_pat({CONF_ACCESS_TOKEN: token})

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "pat"
    assert result["errors"] == {"base": "app_setup_error"}
    assert result["data_schema"]({}) == {CONF_ACCESS_TOKEN: token}


async def test_step_pat_unknown_api_error(hass, smartthings_mock):
    """Test an error is shown when there is an unknown API error."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass
    request_info = Mock(real_url="http://example.com")
    smartthings_mock.apps.side_effect = ClientResponseError(
        request_info=request_info, history=None, status=HTTP_NOT_FOUND
    )
    token = str(uuid4())

    result = await flow.async_step_pat({CONF_ACCESS_TOKEN: token})

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "pat"
    assert result["errors"] == {"base": "app_setup_error"}
    assert result["data_schema"]({}) == {CONF_ACCESS_TOKEN: token}


async def test_step_pat_unknown_error(hass, smartthings_mock):
    """Test an error is shown when there is an unknown API error."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass
    smartthings_mock.apps.side_effect = Exception("Unknown error")
    token = str(uuid4())

    result = await flow.async_step_pat({CONF_ACCESS_TOKEN: token})

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "pat"
    assert result["errors"] == {"base": "app_setup_error"}
    assert result["data_schema"]({}) == {CONF_ACCESS_TOKEN: token}


async def test_step_pat_app_created_webhook(
    hass, app, app_oauth_client, location, smartthings_mock
):
    """Test SmartApp is created when one does not exist and shows location form."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass

    smartthings_mock.apps.return_value = []
    smartthings_mock.create_app.return_value = (app, app_oauth_client)
    smartthings_mock.locations.return_value = [location]
    token = str(uuid4())

    result = await flow.async_step_pat({CONF_ACCESS_TOKEN: token})

    assert flow.access_token == token
    assert flow.app_id == app.app_id
    assert flow.oauth_client_secret == app_oauth_client.client_secret
    assert flow.oauth_client_id == app_oauth_client.client_id
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "select_location"


async def test_step_pat_app_created_cloudhook(
    hass, app, app_oauth_client, location, smartthings_mock
):
    """Test SmartApp is created with a cloudhook and shows location form."""
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
        smartthings_mock.locations.return_value = [location]
        token = str(uuid4())

        result = await flow.async_step_pat({CONF_ACCESS_TOKEN: token})

        assert flow.access_token == token
        assert flow.app_id == app.app_id
        assert flow.oauth_client_secret == app_oauth_client.client_secret
        assert flow.oauth_client_id == app_oauth_client.client_id
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "select_location"
        assert mock_create_cloudhook.call_count == 1


async def test_step_pat_app_updated_webhook(
    hass, app, app_oauth_client, location, smartthings_mock
):
    """Test SmartApp is updated then show location form."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass

    smartthings_mock.apps.return_value = [app]
    smartthings_mock.generate_app_oauth.return_value = app_oauth_client
    smartthings_mock.locations.return_value = [location]
    token = str(uuid4())

    result = await flow.async_step_pat({CONF_ACCESS_TOKEN: token})

    assert flow.access_token == token
    assert flow.app_id == app.app_id
    assert flow.oauth_client_secret == app_oauth_client.client_secret
    assert flow.oauth_client_id == app_oauth_client.client_id
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "select_location"


async def test_step_pat_app_updated_webhook_from_existing_oauth_client(
    hass, app, location, smartthings_mock
):
    """Test SmartApp is updated from existing then show location form."""
    oauth_client_id = str(uuid4())
    oauth_client_secret = str(uuid4())
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_APP_ID: app.app_id,
            CONF_OAUTH_CLIENT_ID: oauth_client_id,
            CONF_OAUTH_CLIENT_SECRET: oauth_client_secret,
            CONF_LOCATION_ID: str(uuid4()),
        },
    )
    entry.add_to_hass(hass)
    flow = SmartThingsFlowHandler()
    flow.hass = hass
    smartthings_mock.apps.return_value = [app]
    smartthings_mock.locations.return_value = [location]
    token = str(uuid4())

    result = await flow.async_step_pat({CONF_ACCESS_TOKEN: token})

    assert flow.access_token == token
    assert flow.app_id == app.app_id
    assert flow.oauth_client_secret == oauth_client_secret
    assert flow.oauth_client_id == oauth_client_id
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "select_location"


async def test_step_select_location(hass, location, smartthings_mock):
    """Test select location shows form with available locations."""
    smartthings_mock.locations.return_value = [location]
    flow = SmartThingsFlowHandler()
    flow.hass = hass
    flow.api = smartthings_mock

    result = await flow.async_step_select_location()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "select_location"
    assert result["data_schema"]({CONF_LOCATION_ID: location.location_id}) == {
        CONF_LOCATION_ID: location.location_id
    }


async def test_step_select_location_aborts(hass, location, smartthings_mock):
    """Test select location aborts if no available locations."""
    smartthings_mock.locations.return_value = [location]
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_LOCATION_ID: location.location_id}
    )
    entry.add_to_hass(hass)
    flow = SmartThingsFlowHandler()
    flow.hass = hass
    flow.api = smartthings_mock

    result = await flow.async_step_select_location()
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "no_available_locations"


async def test_step_select_location_advances(hass):
    """Test select location aborts if no available locations."""
    location_id = str(uuid4())
    app_id = str(uuid4())
    flow = SmartThingsFlowHandler()
    flow.hass = hass
    flow.app_id = app_id

    result = await flow.async_step_select_location({CONF_LOCATION_ID: location_id})

    assert flow.location_id == location_id
    assert result["type"] == data_entry_flow.RESULT_TYPE_EXTERNAL_STEP
    assert result["step_id"] == "authorize"
    assert result["url"] == format_install_url(app_id, location_id)


async def test_step_authorize_advances(hass):
    """Test authorize step advances when completed."""
    installed_app_id = str(uuid4())
    refresh_token = str(uuid4())
    flow = SmartThingsFlowHandler()
    flow.hass = hass

    result = await flow.async_step_authorize(
        {CONF_INSTALLED_APP_ID: installed_app_id, CONF_REFRESH_TOKEN: refresh_token}
    )

    assert flow.installed_app_id == installed_app_id
    assert flow.refresh_token == refresh_token
    assert result["type"] == data_entry_flow.RESULT_TYPE_EXTERNAL_STEP_DONE
    assert result["step_id"] == "install"


async def test_step_install_creates_entry(hass, location, smartthings_mock):
    """Test a config entry is created once the app is installed."""
    flow = SmartThingsFlowHandler()
    flow.hass = hass
    flow.api = smartthings_mock
    flow.access_token = str(uuid4())
    flow.app_id = str(uuid4())
    flow.installed_app_id = str(uuid4())
    flow.location_id = location.location_id
    flow.oauth_client_id = str(uuid4())
    flow.oauth_client_secret = str(uuid4())
    flow.refresh_token = str(uuid4())

    result = await flow.async_step_install()

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"]["app_id"] == flow.app_id
    assert result["data"]["installed_app_id"] == flow.installed_app_id
    assert result["data"]["location_id"] == flow.location_id
    assert result["data"]["access_token"] == flow.access_token
    assert result["data"]["refresh_token"] == flow.refresh_token
    assert result["data"]["client_secret"] == flow.oauth_client_secret
    assert result["data"]["client_id"] == flow.oauth_client_id
    assert result["title"] == location.name
