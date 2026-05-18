"""Tests for the Lepro config flow."""

from __future__ import annotations

from unittest.mock import patch

import aiohttp
import pytest

from homeassistant.components.lepro.const import (
    CONF_ACCOUNT,
    CONF_API_HOST,
    DOMAIN,
    REGION_API_URL,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from .conftest import ACCOUNT, API_HOST

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

REGION_RESPONSE = {
    "code": 0,
    "data": {"apiHost": "api-us-iot.lepro.com"},
}

TOKEN_RESPONSE = {
    "access_token": "mock-access-token",
    "refresh_token": "mock-refresh-token",
    "token_type": "Bearer",
    "expires_in": int(__import__("time").time()) + 3600,
}


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a complete successful config flow."""
    aioclient_mock.post(
        REGION_API_URL,
        json=REGION_RESPONSE,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ACCOUNT: ACCOUNT},
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
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200

    aioclient_mock.post(
        f"{API_HOST}/oauth2/token",
        json=TOKEN_RESPONSE,
    )

    with patch(
        "homeassistant.components.lepro.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Lepro"
    assert result["data"][CONF_API_HOST] == API_HOST
    assert result["data"][CONF_ACCOUNT] == ACCOUNT
    assert len(mock_setup.mock_calls) == 1


@pytest.mark.usefixtures("current_request_with_host")
async def test_user_step_cannot_connect(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the user step returns an error when the region API is unreachable."""
    aioclient_mock.post(
        REGION_API_URL,
        exc=aiohttp.ClientError,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ACCOUNT: ACCOUNT},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.usefixtures("current_request_with_host")
async def test_already_configured(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a duplicate configuration is aborted."""
    mock_config_entry.add_to_hass(hass)

    aioclient_mock.post(
        REGION_API_URL,
        json=REGION_RESPONSE,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ACCOUNT: ACCOUNT},
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
        f"{API_HOST}/oauth2/token",
        json=TOKEN_RESPONSE,
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("current_request_with_host")
async def test_extra_authorize_data_includes_account(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that the OAuth2 authorization URL carries the account from the user step."""
    aioclient_mock.post(REGION_API_URL, json=REGION_RESPONSE)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ACCOUNT: ACCOUNT},
    )

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert f"account={ACCOUNT}" in result["url"]
