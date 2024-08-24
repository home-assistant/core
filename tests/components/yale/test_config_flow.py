"""Test the yale config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.yale.application_credentials import (
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
)
from homeassistant.components.yale.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from .mocks import USER_ID

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

CLIENT_ID = "1"


@pytest.mark.usefixtures("client_credentials")
@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    jwt: str,
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

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "access_token": jwt,
            "scope": "any",
            "expires_in": 86399,
            "refresh_token": "mock-refresh-token",
            "user_id": "mock-user-id",
            "expires_at": 1697753347,
        },
    )

    with patch(
        "homeassistant.components.yale.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id == USER_ID


@pytest.mark.usefixtures("client_credentials")
@pytest.mark.usefixtures("current_request_with_host")
async def test_reauth(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    reauth_jwt: str,
) -> None:
    """Test the reauthentication case updates the existing config entry."""

    mock_config_entry.add_to_hass(hass)

    mock_config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    result = flows[0]
    assert result["step_id"] == "auth"

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
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "access_token": reauth_jwt,
            "expires_in": 86399,
            "refresh_token": "mock-refresh-token",
            "user_id": USER_ID,
            "token_type": "Bearer",
            "expires_at": 1697753347,
        },
    )
    with patch(
        "homeassistant.components.yale.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert mock_config_entry.unique_id == USER_ID
    assert "token" in mock_config_entry.data
    # Verify access token is refreshed
    assert mock_config_entry.data["token"]["access_token"] == reauth_jwt


@pytest.mark.usefixtures("client_credentials")
@pytest.mark.usefixtures("current_request_with_host")
async def test_reauth_wrong_account(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    reauth_jwt_wrong_account: str,
    jwt: str,
) -> None:
    """Test the reauthentication aborts, if user tries to reauthenticate with another account."""
    assert mock_config_entry.data["token"]["access_token"] == jwt

    mock_config_entry.add_to_hass(hass)

    mock_config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    result = flows[0]
    assert result["step_id"] == "auth"

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
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "access_token": reauth_jwt_wrong_account,
            "expires_in": 86399,
            "refresh_token": "mock-refresh-token",
            "token_type": "Bearer",
            "expires_at": 1697753347,
        },
    )

    with patch(
        "homeassistant.components.yale.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_invalid_user"

    assert mock_config_entry.unique_id == USER_ID
    assert "token" in mock_config_entry.data
    # Verify access token is like before
    assert mock_config_entry.data["token"]["access_token"] == jwt
