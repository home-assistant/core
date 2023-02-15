"""Tests for the SmartThings config flow module."""
from http import HTTPStatus
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from aiohttp import ClientResponseError
from pysmartthings import APIResponseError
from pysmartthings.installedapp import format_install_url

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.smartthings import smartapp
from homeassistant.components.smartthings.const import (
    CONF_APP_ID,
    CONF_INSTALLED_APP_ID,
    CONF_LOCATION_ID,
    DOMAIN,
)
from homeassistant.config import async_process_ha_core_config
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_import_shows_user_step(hass: HomeAssistant) -> None:
    """Test import source shows the user form."""
    # Webhook confirmation shown
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["description_placeholders"][
        "webhook_url"
    ] == smartapp.get_webhook_url(hass)


async def test_entry_created(
    hass: HomeAssistant, app, app_oauth_client, location, smartthings_mock
) -> None:
    """Test local webhook, new app, install event creates entry."""
    token = str(uuid4())
    installed_app_id = str(uuid4())
    refresh_token = str(uuid4())
    smartthings_mock.apps.return_value = []
    smartthings_mock.create_app.return_value = (app, app_oauth_client)
    smartthings_mock.locations.return_value = [location]
    request = Mock()
    request.installed_app_id = installed_app_id
    request.auth_token = token
    request.location_id = location.location_id
    request.refresh_token = refresh_token

    # Webhook confirmation shown
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["description_placeholders"][
        "webhook_url"
    ] == smartapp.get_webhook_url(hass)

    # Advance to PAT screen
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "pat"
    assert "token_url" in result["description_placeholders"]
    assert "component_url" in result["description_placeholders"]

    # Enter token and advance to location screen
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: token}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "select_location"

    # Select location and advance to external auth
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_LOCATION_ID: location.location_id}
    )
    assert result["type"] == data_entry_flow.FlowResultType.EXTERNAL_STEP
    assert result["step_id"] == "authorize"
    assert result["url"] == format_install_url(app.app_id, location.location_id)

    # Complete external auth and advance to install
    await smartapp.smartapp_install(hass, request, None, app)

    # Finish
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"]["app_id"] == app.app_id
    assert result["data"]["installed_app_id"] == installed_app_id
    assert result["data"]["location_id"] == location.location_id
    assert result["data"]["access_token"] == token
    assert result["data"]["refresh_token"] == request.refresh_token
    assert result["data"][CONF_CLIENT_SECRET] == app_oauth_client.client_secret
    assert result["data"][CONF_CLIENT_ID] == app_oauth_client.client_id
    assert result["title"] == location.name
    entry = next(
        (entry for entry in hass.config_entries.async_entries(DOMAIN)),
        None,
    )
    assert entry.unique_id == smartapp.format_unique_id(
        app.app_id, location.location_id
    )


async def test_entry_created_from_update_event(
    hass: HomeAssistant, app, app_oauth_client, location, smartthings_mock
) -> None:
    """Test local webhook, new app, update event creates entry."""
    token = str(uuid4())
    installed_app_id = str(uuid4())
    refresh_token = str(uuid4())
    smartthings_mock.apps.return_value = []
    smartthings_mock.create_app.return_value = (app, app_oauth_client)
    smartthings_mock.locations.return_value = [location]
    request = Mock()
    request.installed_app_id = installed_app_id
    request.auth_token = token
    request.location_id = location.location_id
    request.refresh_token = refresh_token

    # Webhook confirmation shown
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["description_placeholders"][
        "webhook_url"
    ] == smartapp.get_webhook_url(hass)

    # Advance to PAT screen
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "pat"
    assert "token_url" in result["description_placeholders"]
    assert "component_url" in result["description_placeholders"]

    # Enter token and advance to location screen
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: token}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "select_location"

    # Select location and advance to external auth
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_LOCATION_ID: location.location_id}
    )
    assert result["type"] == data_entry_flow.FlowResultType.EXTERNAL_STEP
    assert result["step_id"] == "authorize"
    assert result["url"] == format_install_url(app.app_id, location.location_id)

    # Complete external auth and advance to install
    await smartapp.smartapp_update(hass, request, None, app)

    # Finish
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"]["app_id"] == app.app_id
    assert result["data"]["installed_app_id"] == installed_app_id
    assert result["data"]["location_id"] == location.location_id
    assert result["data"]["access_token"] == token
    assert result["data"]["refresh_token"] == request.refresh_token
    assert result["data"][CONF_CLIENT_SECRET] == app_oauth_client.client_secret
    assert result["data"][CONF_CLIENT_ID] == app_oauth_client.client_id
    assert result["title"] == location.name
    entry = next(
        (entry for entry in hass.config_entries.async_entries(DOMAIN)),
        None,
    )
    assert entry.unique_id == smartapp.format_unique_id(
        app.app_id, location.location_id
    )


async def test_entry_created_existing_app_new_oauth_client(
    hass: HomeAssistant, app, app_oauth_client, location, smartthings_mock
) -> None:
    """Test entry is created with an existing app and generation of a new oauth client."""
    token = str(uuid4())
    installed_app_id = str(uuid4())
    refresh_token = str(uuid4())
    smartthings_mock.apps.return_value = [app]
    smartthings_mock.generate_app_oauth.return_value = app_oauth_client
    smartthings_mock.locations.return_value = [location]
    request = Mock()
    request.installed_app_id = installed_app_id
    request.auth_token = token
    request.location_id = location.location_id
    request.refresh_token = refresh_token

    # Webhook confirmation shown
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["description_placeholders"][
        "webhook_url"
    ] == smartapp.get_webhook_url(hass)

    # Advance to PAT screen
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "pat"
    assert "token_url" in result["description_placeholders"]
    assert "component_url" in result["description_placeholders"]

    # Enter token and advance to location screen
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: token}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "select_location"

    # Select location and advance to external auth
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_LOCATION_ID: location.location_id}
    )
    assert result["type"] == data_entry_flow.FlowResultType.EXTERNAL_STEP
    assert result["step_id"] == "authorize"
    assert result["url"] == format_install_url(app.app_id, location.location_id)

    # Complete external auth and advance to install
    await smartapp.smartapp_install(hass, request, None, app)

    # Finish
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"]["app_id"] == app.app_id
    assert result["data"]["installed_app_id"] == installed_app_id
    assert result["data"]["location_id"] == location.location_id
    assert result["data"]["access_token"] == token
    assert result["data"]["refresh_token"] == request.refresh_token
    assert result["data"][CONF_CLIENT_SECRET] == app_oauth_client.client_secret
    assert result["data"][CONF_CLIENT_ID] == app_oauth_client.client_id
    assert result["title"] == location.name
    entry = next(
        (entry for entry in hass.config_entries.async_entries(DOMAIN)),
        None,
    )
    assert entry.unique_id == smartapp.format_unique_id(
        app.app_id, location.location_id
    )


async def test_entry_created_existing_app_copies_oauth_client(
    hass: HomeAssistant, app, location, smartthings_mock
) -> None:
    """Test entry is created with an existing app and copies the oauth client from another entry."""
    token = str(uuid4())
    installed_app_id = str(uuid4())
    refresh_token = str(uuid4())
    oauth_client_id = str(uuid4())
    oauth_client_secret = str(uuid4())
    smartthings_mock.apps.return_value = [app]
    smartthings_mock.locations.return_value = [location]
    request = Mock()
    request.installed_app_id = installed_app_id
    request.auth_token = token
    request.location_id = location.location_id
    request.refresh_token = refresh_token
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_APP_ID: app.app_id,
            CONF_CLIENT_ID: oauth_client_id,
            CONF_CLIENT_SECRET: oauth_client_secret,
            CONF_LOCATION_ID: str(uuid4()),
            CONF_INSTALLED_APP_ID: str(uuid4()),
            CONF_ACCESS_TOKEN: token,
        },
    )
    entry.add_to_hass(hass)

    # Webhook confirmation shown
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["description_placeholders"][
        "webhook_url"
    ] == smartapp.get_webhook_url(hass)

    # Advance to PAT screen
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "pat"
    assert "token_url" in result["description_placeholders"]
    assert "component_url" in result["description_placeholders"]
    # Assert access token is defaulted to an existing entry for convenience.
    assert result["data_schema"]({}) == {CONF_ACCESS_TOKEN: token}

    # Enter token and advance to location screen
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: token}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "select_location"

    # Select location and advance to external auth
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_LOCATION_ID: location.location_id}
    )
    assert result["type"] == data_entry_flow.FlowResultType.EXTERNAL_STEP
    assert result["step_id"] == "authorize"
    assert result["url"] == format_install_url(app.app_id, location.location_id)

    # Complete external auth and advance to install
    await smartapp.smartapp_install(hass, request, None, app)

    # Finish
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"]["app_id"] == app.app_id
    assert result["data"]["installed_app_id"] == installed_app_id
    assert result["data"]["location_id"] == location.location_id
    assert result["data"]["access_token"] == token
    assert result["data"]["refresh_token"] == request.refresh_token
    assert result["data"][CONF_CLIENT_SECRET] == oauth_client_secret
    assert result["data"][CONF_CLIENT_ID] == oauth_client_id
    assert result["title"] == location.name
    entry = next(
        (
            entry
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.data[CONF_INSTALLED_APP_ID] == installed_app_id
        ),
        None,
    )
    assert entry.unique_id == smartapp.format_unique_id(
        app.app_id, location.location_id
    )


async def test_entry_created_with_cloudhook(
    hass: HomeAssistant, app, app_oauth_client, location, smartthings_mock
) -> None:
    """Test cloud, new app, install event creates entry."""
    hass.config.components.add("cloud")
    # Unload the endpoint so we can reload it under the cloud.
    await smartapp.unload_smartapp_endpoint(hass)
    token = str(uuid4())
    installed_app_id = str(uuid4())
    refresh_token = str(uuid4())
    smartthings_mock.apps.return_value = []
    smartthings_mock.create_app = AsyncMock(return_value=(app, app_oauth_client))
    smartthings_mock.locations = AsyncMock(return_value=[location])
    request = Mock()
    request.installed_app_id = installed_app_id
    request.auth_token = token
    request.location_id = location.location_id
    request.refresh_token = refresh_token

    with patch.object(
        smartapp.cloud,
        "async_active_subscription",
        Mock(return_value=True),
    ), patch.object(
        smartapp.cloud,
        "async_create_cloudhook",
        AsyncMock(return_value="http://cloud.test"),
    ) as mock_create_cloudhook:
        await smartapp.setup_smartapp_endpoint(hass)

        # Webhook confirmation shown
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["description_placeholders"][
            "webhook_url"
        ] == smartapp.get_webhook_url(hass)
        assert mock_create_cloudhook.call_count == 1

        # Advance to PAT screen
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "pat"
        assert "token_url" in result["description_placeholders"]
        assert "component_url" in result["description_placeholders"]

        # Enter token and advance to location screen
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ACCESS_TOKEN: token}
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "select_location"

        # Select location and advance to external auth
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_LOCATION_ID: location.location_id}
        )
        assert result["type"] == data_entry_flow.FlowResultType.EXTERNAL_STEP
        assert result["step_id"] == "authorize"
        assert result["url"] == format_install_url(app.app_id, location.location_id)

        # Complete external auth and advance to install
        await smartapp.smartapp_install(hass, request, None, app)

        # Finish
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["data"]["app_id"] == app.app_id
        assert result["data"]["installed_app_id"] == installed_app_id
        assert result["data"]["location_id"] == location.location_id
        assert result["data"]["access_token"] == token
        assert result["data"]["refresh_token"] == request.refresh_token
        assert result["data"][CONF_CLIENT_SECRET] == app_oauth_client.client_secret
        assert result["data"][CONF_CLIENT_ID] == app_oauth_client.client_id
        assert result["title"] == location.name
        entry = next(
            (entry for entry in hass.config_entries.async_entries(DOMAIN)),
            None,
        )
        assert entry.unique_id == smartapp.format_unique_id(
            app.app_id, location.location_id
        )


async def test_invalid_webhook_aborts(hass: HomeAssistant) -> None:
    """Test flow aborts if webhook is invalid."""
    # Webhook confirmation shown
    await async_process_ha_core_config(
        hass,
        {"external_url": "http://example.local:8123"},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "invalid_webhook_url"
    assert result["description_placeholders"][
        "webhook_url"
    ] == smartapp.get_webhook_url(hass)
    assert "component_url" in result["description_placeholders"]


async def test_invalid_token_shows_error(hass: HomeAssistant) -> None:
    """Test an error is shown for invalid token formats."""
    token = "123456789"

    # Webhook confirmation shown
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["description_placeholders"][
        "webhook_url"
    ] == smartapp.get_webhook_url(hass)

    # Advance to PAT screen
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "pat"
    assert "token_url" in result["description_placeholders"]
    assert "component_url" in result["description_placeholders"]

    # Enter token
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: token}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "pat"
    assert result["data_schema"]({}) == {CONF_ACCESS_TOKEN: token}
    assert result["errors"] == {CONF_ACCESS_TOKEN: "token_invalid_format"}
    assert "token_url" in result["description_placeholders"]
    assert "component_url" in result["description_placeholders"]


async def test_unauthorized_token_shows_error(
    hass: HomeAssistant, smartthings_mock
) -> None:
    """Test an error is shown for unauthorized token formats."""
    token = str(uuid4())
    request_info = Mock(real_url="http://example.com")
    smartthings_mock.apps.side_effect = ClientResponseError(
        request_info=request_info, history=None, status=HTTPStatus.UNAUTHORIZED
    )

    # Webhook confirmation shown
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["description_placeholders"][
        "webhook_url"
    ] == smartapp.get_webhook_url(hass)

    # Advance to PAT screen
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "pat"
    assert "token_url" in result["description_placeholders"]
    assert "component_url" in result["description_placeholders"]

    # Enter token
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: token}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "pat"
    assert result["data_schema"]({}) == {CONF_ACCESS_TOKEN: token}
    assert result["errors"] == {CONF_ACCESS_TOKEN: "token_unauthorized"}
    assert "token_url" in result["description_placeholders"]
    assert "component_url" in result["description_placeholders"]


async def test_forbidden_token_shows_error(
    hass: HomeAssistant, smartthings_mock
) -> None:
    """Test an error is shown for forbidden token formats."""
    token = str(uuid4())
    request_info = Mock(real_url="http://example.com")
    smartthings_mock.apps.side_effect = ClientResponseError(
        request_info=request_info, history=None, status=HTTPStatus.FORBIDDEN
    )

    # Webhook confirmation shown
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["description_placeholders"][
        "webhook_url"
    ] == smartapp.get_webhook_url(hass)

    # Advance to PAT screen
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "pat"
    assert "token_url" in result["description_placeholders"]
    assert "component_url" in result["description_placeholders"]

    # Enter token
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: token}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "pat"
    assert result["data_schema"]({}) == {CONF_ACCESS_TOKEN: token}
    assert result["errors"] == {CONF_ACCESS_TOKEN: "token_forbidden"}
    assert "token_url" in result["description_placeholders"]
    assert "component_url" in result["description_placeholders"]


async def test_webhook_problem_shows_error(
    hass: HomeAssistant, smartthings_mock
) -> None:
    """Test an error is shown when there's an problem with the webhook endpoint."""
    token = str(uuid4())
    data = {"error": {}}
    request_info = Mock(real_url="http://example.com")
    error = APIResponseError(
        request_info=request_info,
        history=None,
        data=data,
        status=HTTPStatus.UNPROCESSABLE_ENTITY,
    )
    error.is_target_error = Mock(return_value=True)
    smartthings_mock.apps.side_effect = error

    # Webhook confirmation shown
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["description_placeholders"][
        "webhook_url"
    ] == smartapp.get_webhook_url(hass)

    # Advance to PAT screen
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "pat"
    assert "token_url" in result["description_placeholders"]
    assert "component_url" in result["description_placeholders"]

    # Enter token
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: token}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "pat"
    assert result["data_schema"]({}) == {CONF_ACCESS_TOKEN: token}
    assert result["errors"] == {"base": "webhook_error"}
    assert "token_url" in result["description_placeholders"]
    assert "component_url" in result["description_placeholders"]


async def test_api_error_shows_error(hass: HomeAssistant, smartthings_mock) -> None:
    """Test an error is shown when other API errors occur."""
    token = str(uuid4())
    data = {"error": {}}
    request_info = Mock(real_url="http://example.com")
    error = APIResponseError(
        request_info=request_info,
        history=None,
        data=data,
        status=HTTPStatus.BAD_REQUEST,
    )
    smartthings_mock.apps.side_effect = error

    # Webhook confirmation shown
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["description_placeholders"][
        "webhook_url"
    ] == smartapp.get_webhook_url(hass)

    # Advance to PAT screen
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "pat"
    assert "token_url" in result["description_placeholders"]
    assert "component_url" in result["description_placeholders"]

    # Enter token
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: token}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "pat"
    assert result["data_schema"]({}) == {CONF_ACCESS_TOKEN: token}
    assert result["errors"] == {"base": "app_setup_error"}
    assert "token_url" in result["description_placeholders"]
    assert "component_url" in result["description_placeholders"]


async def test_unknown_response_error_shows_error(
    hass: HomeAssistant, smartthings_mock
) -> None:
    """Test an error is shown when there is an unknown API error."""
    token = str(uuid4())
    request_info = Mock(real_url="http://example.com")
    error = ClientResponseError(
        request_info=request_info, history=None, status=HTTPStatus.NOT_FOUND
    )
    smartthings_mock.apps.side_effect = error

    # Webhook confirmation shown
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["description_placeholders"][
        "webhook_url"
    ] == smartapp.get_webhook_url(hass)

    # Advance to PAT screen
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "pat"
    assert "token_url" in result["description_placeholders"]
    assert "component_url" in result["description_placeholders"]

    # Enter token
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: token}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "pat"
    assert result["data_schema"]({}) == {CONF_ACCESS_TOKEN: token}
    assert result["errors"] == {"base": "app_setup_error"}
    assert "token_url" in result["description_placeholders"]
    assert "component_url" in result["description_placeholders"]


async def test_unknown_error_shows_error(hass: HomeAssistant, smartthings_mock) -> None:
    """Test an error is shown when there is an unknown API error."""
    token = str(uuid4())
    smartthings_mock.apps.side_effect = Exception("Unknown error")

    # Webhook confirmation shown
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["description_placeholders"][
        "webhook_url"
    ] == smartapp.get_webhook_url(hass)

    # Advance to PAT screen
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "pat"
    assert "token_url" in result["description_placeholders"]
    assert "component_url" in result["description_placeholders"]

    # Enter token
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: token}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "pat"
    assert result["data_schema"]({}) == {CONF_ACCESS_TOKEN: token}
    assert result["errors"] == {"base": "app_setup_error"}
    assert "token_url" in result["description_placeholders"]
    assert "component_url" in result["description_placeholders"]


async def test_no_available_locations_aborts(
    hass: HomeAssistant, app, app_oauth_client, location, smartthings_mock
) -> None:
    """Test select location aborts if no available locations."""
    token = str(uuid4())
    smartthings_mock.apps.return_value = []
    smartthings_mock.create_app.return_value = (app, app_oauth_client)
    smartthings_mock.locations.return_value = [location]
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_LOCATION_ID: location.location_id}
    )
    entry.add_to_hass(hass)

    # Webhook confirmation shown
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["description_placeholders"][
        "webhook_url"
    ] == smartapp.get_webhook_url(hass)

    # Advance to PAT screen
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "pat"
    assert "token_url" in result["description_placeholders"]
    assert "component_url" in result["description_placeholders"]

    # Enter token and advance to location screen
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: token}
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "no_available_locations"
