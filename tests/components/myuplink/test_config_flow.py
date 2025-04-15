"""Test the myUplink config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.myuplink.const import (
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from .const import CLIENT_ID, UNIQUE_ID

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

REDIRECT_URL = "https://example.com/auth/external/callback"
CURRENT_SCOPE = "WRITESYSTEM READSYSTEM offline_access"


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    access_token: str,
    setup_credentials,
) -> None:
    """Check full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT_URL,
        },
    )

    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URL}"
        f"&state={state}"
        f"&scope={CURRENT_SCOPE.replace(' ', '+')}"
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
        f"homeassistant.components.{DOMAIN}.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1

    assert result["data"]["auth_implementation"] == DOMAIN
    assert result["data"]["token"]["refresh_token"] == "mock-refresh-token"
    assert result["result"].unique_id == UNIQUE_ID


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.parametrize(
    ("unique_id", "scope", "expected_reason"),
    [
        (
            UNIQUE_ID,
            CURRENT_SCOPE,
            "reauth_successful",
        ),
        (
            "wrong_uid",
            CURRENT_SCOPE,
            "account_mismatch",
        ),
        (
            UNIQUE_ID,
            "READSYSTEM offline_access",
            "reauth_successful",
        ),
    ],
    ids=["reauth_only", "account_mismatch", "wrong_scope"],
)
async def test_flow_reauth_abort(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    setup_credentials: None,
    mock_config_entry: MockConfigEntry,
    access_token: str,
    expires_at: float,
    unique_id: str,
    scope: str,
    expected_reason: str,
) -> None:
    """Test reauth step with correct params and mismatches."""

    CURRENT_TOKEN = {
        "auth_implementation": DOMAIN,
        "token": {
            "access_token": access_token,
            "scope": scope,
            "expires_in": 86399,
            "refresh_token": "3012bc9f-7a65-4240-b817-9154ffdcc30f",
            "token_type": "Bearer",
            "expires_at": expires_at,
        },
    }
    assert hass.config_entries.async_update_entry(
        mock_config_entry, data=CURRENT_TOKEN, unique_id=unique_id
    )
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["step_id"] == "auth"

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT_URL,
        },
    )
    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URL}"
        f"&state={state}"
        f"&scope={CURRENT_SCOPE.replace(' ', '+')}"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "updated-refresh-token",
            "access_token": access_token,
            "type": "Bearer",
            "expires_in": "60",
            "scope": CURRENT_SCOPE,
        },
    )

    with patch(
        f"homeassistant.components.{DOMAIN}.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == expected_reason

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.parametrize(
    ("unique_id", "scope", "expected_reason"),
    [
        (
            UNIQUE_ID,
            CURRENT_SCOPE,
            "reconfigure_successful",
        ),
        (
            "wrong_uid",
            CURRENT_SCOPE,
            "account_mismatch",
        ),
    ],
    ids=["reauth_only", "account_mismatch"],
)
async def test_flow_reconfigure_abort(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    setup_credentials: None,
    mock_config_entry: MockConfigEntry,
    access_token: str,
    expires_at: float,
    unique_id: str,
    scope: str,
    expected_reason: str,
) -> None:
    """Test reauth step with correct params and mismatches."""

    CURRENT_TOKEN = {
        "auth_implementation": DOMAIN,
        "token": {
            "access_token": access_token,
            "scope": scope,
            "expires_in": 86399,
            "refresh_token": "3012bc9f-7a65-4240-b817-9154ffdcc30f",
            "token_type": "Bearer",
            "expires_at": expires_at,
        },
    }
    assert hass.config_entries.async_update_entry(
        mock_config_entry, data=CURRENT_TOKEN, unique_id=unique_id
    )
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["step_id"] == "auth"

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT_URL,
        },
    )
    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URL}"
        f"&state={state}"
        f"&scope={CURRENT_SCOPE.replace(' ', '+')}"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "updated-refresh-token",
            "access_token": access_token,
            "type": "Bearer",
            "expires_in": "60",
            "scope": CURRENT_SCOPE,
        },
    )

    with patch(
        f"homeassistant.components.{DOMAIN}.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == expected_reason

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
