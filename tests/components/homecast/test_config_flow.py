"""Tests for the Homecast config flow."""

from http import HTTPStatus
from unittest.mock import AsyncMock

from pyhomecast import HomecastAuthError, HomecastConnectionError
import pytest

from homeassistant.components.homecast.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


async def _start_cloud_flow(
    hass: HomeAssistant,
) -> dict:
    """Init the config flow and select the cloud option from the menu."""
    menu = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert menu["type"] is FlowResultType.MENU

    return await hass.config_entries.flow.async_configure(
        menu["flow_id"], {"next_step_id": "cloud"}
    )


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_homecast: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the complete OAuth config flow via cloud."""
    result = await _start_cloud_flow(hass)

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert "oauth/authorize" in result["url"]

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        "https://api.homecast.cloud/oauth/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "read write",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Homecast"
    assert result["data"]["token"]["access_token"] == "mock-access-token"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("current_request_with_host")
async def test_flow_already_configured(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that we abort if already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await _start_cloud_flow(hass)

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        "https://api.homecast.cloud/oauth/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "read write",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        (HomecastConnectionError("timeout"), "cannot_connect"),
        (HomecastAuthError("unauthorized"), "invalid_auth"),
        (RuntimeError("unexpected"), "unknown"),
    ],
)
@pytest.mark.usefixtures("current_request_with_host")
async def test_flow_get_state_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_homecast: AsyncMock,
    mock_setup_entry: AsyncMock,
    side_effect: Exception,
    reason: str,
) -> None:
    """Test that we handle errors from get_state during OAuth completion."""
    mock_homecast.get_state.side_effect = side_effect

    result = await _start_cloud_flow(hass)

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        "https://api.homecast.cloud/oauth/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "read write",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.usefixtures("current_request_with_host")
async def test_reauth_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reauth flow updates the existing entry."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    # Reauth confirm → goes to menu → select cloud
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "cloud"}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        "https://api.homecast.cloud/oauth/token",
        json={
            "refresh_token": "new-refresh-token",
            "access_token": "new-access-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "read write",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.usefixtures("current_request_with_host")
async def test_flow_register_client_failure(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test that we abort if dynamic client registration fails."""
    mock_homecast.register_client.side_effect = HomecastConnectionError("timeout")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "cloud"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.usefixtures("current_request_with_host")
async def test_menu_shows_cloud_and_community(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
) -> None:
    """Test that the first step shows a menu with cloud and community options."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert "cloud" in result["menu_options"]
    assert "community" in result["menu_options"]


async def _start_community_flow(
    hass: HomeAssistant,
    server_url: str = "http://localhost:5656",
) -> dict:
    """Init the config flow, select community, and submit the server URL."""
    menu = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert menu["type"] is FlowResultType.MENU

    # Select "community" from the menu
    form = await hass.config_entries.flow.async_configure(
        menu["flow_id"], {"next_step_id": "community"}
    )
    assert form["type"] is FlowResultType.FORM
    assert form["step_id"] == "community"

    # Submit the server URL
    return await hass.config_entries.flow.async_configure(
        form["flow_id"], {"api_url": server_url}
    )


@pytest.mark.usefixtures("current_request_with_host")
async def test_community_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_homecast: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the complete OAuth config flow via community mode."""
    server_url = "http://my-server.local:5656"

    # Start community flow — submits server URL, registers client, kicks off OAuth
    result = await _start_community_flow(hass, server_url)

    # Should be at the external OAuth step
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert f"{server_url}/oauth/authorize" in result["url"]

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        f"{server_url}/oauth/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "read write",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Homecast Community"
    assert result["data"]["token"]["access_token"] == "mock-access-token"
    assert result["data"]["mode"] == "community"
    assert result["data"]["api_url"] == server_url
    assert result["data"]["oauth_authorize_url"] == f"{server_url}/oauth/authorize"
    assert result["data"]["oauth_token_url"] == f"{server_url}/oauth/token"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("current_request_with_host")
async def test_community_flow_register_client_connection_error(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test community flow shows error when register_client fails with connection error."""
    mock_homecast.register_client.side_effect = HomecastConnectionError("timeout")

    menu = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    form = await hass.config_entries.flow.async_configure(
        menu["flow_id"], {"next_step_id": "community"}
    )
    assert form["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        form["flow_id"], {"api_url": "http://bad-server.local:5656"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


@pytest.mark.usefixtures("current_request_with_host")
async def test_community_flow_register_client_unexpected_error(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test community flow shows error when register_client raises unexpected exception."""
    mock_homecast.register_client.side_effect = RuntimeError("unexpected")

    menu = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    form = await hass.config_entries.flow.async_configure(
        menu["flow_id"], {"next_step_id": "community"}
    )

    result = await hass.config_entries.flow.async_configure(
        form["flow_id"], {"api_url": "http://bad-server.local:5656"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "unknown"


@pytest.mark.usefixtures("current_request_with_host")
async def test_community_flow_shows_form_initially(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
) -> None:
    """Test that selecting community from menu shows the server URL form."""
    menu = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        menu["flow_id"], {"next_step_id": "community"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "community"
