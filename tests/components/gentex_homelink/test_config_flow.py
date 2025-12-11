"""Test the homelink config flow."""

from http import HTTPStatus
import time
from unittest.mock import AsyncMock

import botocore.exceptions
import pytest

from homeassistant.components.gentex_homelink.const import DOMAIN, OAUTH2_TOKEN_URL
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry
from tests.conftest import AiohttpClientMocker


async def test_full_flow(
    hass: HomeAssistant, mock_srp_auth: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Check full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_EMAIL: "test@test.com", CONF_PASSWORD: "SomePassword"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "auth_implementation": "gentex_homelink",
        "token": {
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_in": 3600,
            "token_type": "bearer",
            "expires_at": result["data"]["token"]["expires_at"],
        },
    }
    assert result["title"] == "SRPAuth"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (
            botocore.exceptions.ClientError({"Error": {}}, "Some operation"),
            "srp_auth_failed",
        ),
        (Exception("Some error"), "unknown"),
    ],
)
async def test_exceptions(
    hass: HomeAssistant,
    mock_srp_auth: AsyncMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test exceptions are handled correctly."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_srp_auth.async_get_access_token.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_EMAIL: "test@test.com", CONF_PASSWORD: "SomePassword"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_auth_error(
    hass: HomeAssistant, mock_srp_auth: AsyncMock, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test if the auth server returns an error refreshing the token."""
    aioclient_mock.clear_requests()
    aioclient_mock.post(OAUTH2_TOKEN_URL, status=HTTPStatus.UNAUTHORIZED)

    assert len(aioclient_mock.mock_calls) == 0
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"email": "test@test.com", "password": "SomePassword"},
    )
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[0][0] == "POST"


async def test_reauth_flow(
    hass: HomeAssistant, mock_srp_auth: AsyncMock, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the reauth flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@test.com",
        version=1,
        data={
            "auth_implementation": "gentex_homelink",
            "token": {
                "expires_at": time.time() + 10000,
                "access_token": "",
                "refresh_token": "",
            },
            "last_update_id": None,
        },
        state=ConfigEntryState.LOADED,
    )
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    assert result["type"] == FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"email": "test@test.com", "password": "SomePassword"},
    )
    assert result["reason"] == "reauth_successful"
