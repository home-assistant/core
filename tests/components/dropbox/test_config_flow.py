"""Test the Dropbox config flow."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from yarl import URL

from homeassistant import config_entries
from homeassistant.components.dropbox.const import (
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_SCOPES,
    OAUTH2_TOKEN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from .conftest import ACCOUNT_EMAIL, ACCOUNT_ID, CLIENT_ID

from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_dropbox_client,
) -> None:
    """Test creating a new config entry through the OAuth flow."""

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

    result_url = URL(result["url"])
    assert f"{result_url.origin()}{result_url.path}" == OAUTH2_AUTHORIZE
    assert result_url.query["response_type"] == "code"
    assert result_url.query["client_id"] == CLIENT_ID
    assert (
        result_url.query["redirect_uri"] == "https://example.com/auth/external/callback"
    )
    assert result_url.query["state"] == state
    assert result_url.query["scope"] == " ".join(OAUTH2_SCOPES)
    assert result_url.query["token_access_type"] == "offline"
    assert result_url.query["code_challenge"]
    assert result_url.query["code_challenge_method"] == "S256"

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "token_type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch(
        "homeassistant.components.dropbox.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ACCOUNT_EMAIL
    assert result["data"]["token"]["access_token"] == "mock-access-token"
    assert result["context"]["unique_id"] == ACCOUNT_ID
    assert len(mock_setup.mock_calls) == 1
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.usefixtures("current_request_with_host")
async def test_already_configured(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    config_entry,
    mock_dropbox_client,
) -> None:
    """Test aborting when the account is already configured."""

    config_entry.add_to_hass(hass)

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

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "token_type": "Bearer",
            "expires_in": 60,
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.parametrize(
    ("new_account_info", "expected_reason", "expected_setup_calls"),
    [
        (
            SimpleNamespace(account_id=ACCOUNT_ID, email=ACCOUNT_EMAIL),
            "reauth_successful",
            1,
        ),
        (
            SimpleNamespace(account_id="dbid:different", email="other@example.com"),
            "wrong_account",
            0,
        ),
    ],
    ids=["success", "wrong_account"],
)
async def test_reauth_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    config_entry,
    mock_dropbox_client,
    new_account_info: SimpleNamespace,
    expected_reason: str,
    expected_setup_calls: int,
) -> None:
    """Test reauthentication flow outcomes."""

    config_entry.add_to_hass(hass)

    mock_dropbox_client.async_get_account_info.return_value = new_account_info

    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

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
            "refresh_token": "mock-refresh-token",
            "access_token": "updated-access-token",
            "token_type": "Bearer",
            "expires_in": 120,
        },
    )

    with patch(
        "homeassistant.components.dropbox.async_setup_entry", new=AsyncMock()
    ) as mock_setup:
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason
    assert mock_setup.await_count == expected_setup_calls

    if expected_reason == "reauth_successful":
        assert config_entry.data["token"]["access_token"] == "updated-access-token"
    else:
        assert config_entry.data["token"]["access_token"] == "mock-access-token"
