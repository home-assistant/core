"""Test the Dropbox config flow."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

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
    mock_setup_entry: AsyncMock,
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

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ACCOUNT_EMAIL
    assert result["data"]["token"]["access_token"] == "mock-access-token"
    assert result["result"].unique_id == ACCOUNT_ID
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.usefixtures("current_request_with_host")
async def test_already_configured(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry,
    mock_dropbox_client,
) -> None:
    """Test aborting when the account is already configured."""

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
    ("token", "expected_step"),
    [
        (
            {
                "access_token": "mock-access-token",
                "expires_at": 9_999_999_999,
                "scope": " ".join(OAUTH2_SCOPES),
            },
            "reauth_confirm",
        ),
        (
            {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": 9_999_999_999,
                "scope": "account_info.read files.content.read files.content.write",
            },
            "reauth_permissions",
        ),
    ],
    ids=["missing_refresh_token", "missing_scope"],
)
async def test_reauth_confirm_step(
    hass: HomeAssistant,
    mock_config_entry,
    token: dict[str, object],
    expected_step: str,
) -> None:
    """Test reauth shows the correct confirmation step for the broken token."""

    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, "token": token}
    )

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == expected_step

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["step_id"] == "auth"


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.parametrize(
    (
        "new_account_info",
        "expected_reason",
        "expected_setup_calls",
        "expected_access_token",
    ),
    [
        (
            SimpleNamespace(account_id=ACCOUNT_ID, email=ACCOUNT_EMAIL),
            "reauth_successful",
            1,
            "updated-access-token",
        ),
        (
            SimpleNamespace(account_id="dbid:different", email="other@example.com"),
            "wrong_account",
            0,
            "mock-access-token",
        ),
    ],
    ids=["success", "wrong_account"],
)
async def test_reauth_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry,
    mock_dropbox_client,
    mock_setup_entry: AsyncMock,
    new_account_info: SimpleNamespace,
    expected_reason: str,
    expected_setup_calls: int,
    expected_access_token: str,
) -> None:
    """Test reauthentication flow outcomes."""

    mock_config_entry.add_to_hass(hass)

    mock_dropbox_client.get_account_info.return_value = new_account_info

    result = await mock_config_entry.start_reauth_flow(hass)
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

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason
    assert mock_setup_entry.await_count == expected_setup_calls

    assert mock_config_entry.data["token"]["access_token"] == expected_access_token
