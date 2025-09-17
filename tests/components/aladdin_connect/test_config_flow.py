"""Test the Aladdin Connect Garage Door config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.aladdin_connect.const import (
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
)
from homeassistant.config_entries import SOURCE_DHCP
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import CLIENT_ID, USER_ID

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


@pytest.fixture
async def access_token(hass: HomeAssistant) -> str:
    """Return a valid access token with sub field for unique ID."""
    return config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "sub": USER_ID,
            "aud": [],
            "iat": 1234567890,
            "exp": 1234567890 + 3600,
        },
    )


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    access_token,
) -> None:
    """Check full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": access_token,
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch(
        "homeassistant.components.aladdin_connect.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Aladdin Connect"
    assert result["data"] == {
        "auth_implementation": DOMAIN,
        "token": {
            "access_token": access_token,
            "refresh_token": "mock-refresh-token",
            "expires_in": 60,
            "expires_at": result["data"]["token"]["expires_at"],
            "type": "Bearer",
        },
    }
    assert result["result"].unique_id == USER_ID


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_dhcp_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    access_token,
) -> None:
    """Check full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.0.123", macaddress="001122334455", hostname="gdocntl-334455"
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "oauth_discovery"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": access_token,
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch(
        "homeassistant.components.aladdin_connect.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Aladdin Connect"
    assert result["data"] == {
        "auth_implementation": DOMAIN,
        "token": {
            "access_token": access_token,
            "refresh_token": "mock-refresh-token",
            "expires_in": 60,
            "expires_at": result["data"]["token"]["expires_at"],
            "type": "Bearer",
        },
    }
    assert result["result"].unique_id == USER_ID


@pytest.mark.usefixtures("current_request_with_host")
async def test_duplicate_entry(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    access_token,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Check full flow."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": access_token,
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch(
        "homeassistant.components.aladdin_connect.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("current_request_with_host")
async def test_duplicate_dhcp_entry(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    access_token,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Check full flow."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.0.123", macaddress="001122334455", hostname="gdocntl-334455"
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("current_request_with_host")
async def test_flow_reauth(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    access_token,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow."""
    mock_config_entry.add_to_hass(hass)

    # Start reauth flow
    result = await mock_config_entry.start_reauth_flow(hass)

    # Should show reauth confirm form
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    # Confirm reauth
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    # Should now go to user step (OAuth)
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "new-refresh-token",
            "access_token": access_token,
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch(
        "homeassistant.components.aladdin_connect.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    # Verify the entry was updated, not a new one created
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.usefixtures("current_request_with_host")
async def test_flow_wrong_account_reauth(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow with wrong account."""
    mock_config_entry.add_to_hass(hass)

    # Start reauth flow
    result = await mock_config_entry.start_reauth_flow(hass)

    # Should show reauth confirm form
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    # Create access token for a different user
    different_user_token = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "sub": "different_user_456",
            "aud": [],
            "iat": 1234567890,
            "exp": 1234567890 + 3600,
        },
    )

    # Start reauth flow
    result = await mock_config_entry.start_reauth_flow(hass)

    # Confirm reauth
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    # Complete OAuth with different user
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "wrong-user-refresh-token",
            "access_token": different_user_token,
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Should abort with wrong account
    assert result["type"] == "abort"
    assert result["reason"] == "wrong_account"
