"""Test the homelink config flow."""

from http import HTTPStatus
from unittest.mock import AsyncMock

import botocore.exceptions
import pytest

from homeassistant.components.gentex_homelink.const import DOMAIN, OAUTH2_TOKEN_URL
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    INVALID_TEST_ACCESS_JWT,
    INVALID_TEST_CREDENTIALS,
    TEST_ACCESS_JWT,
    TEST_CREDENTIALS,
    TEST_UNIQUE_ID,
    setup_integration,
)

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
        user_input=TEST_CREDENTIALS,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "auth_implementation": "gentex_homelink",
        "token": {
            "access_token": TEST_ACCESS_JWT,
            "refresh_token": "refresh",
            "expires_in": 3600,
            "token_type": "bearer",
            "expires_at": result["data"]["token"]["expires_at"],
        },
    }
    assert result["result"].unique_id == TEST_UNIQUE_ID
    assert result["title"] == "HomeLink"


async def test_unique_configurations(
    hass: HomeAssistant,
    mock_srp_auth: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Check full flow."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_CREDENTIALS,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


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

    mock_srp_auth.async_get_access_token.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_CREDENTIALS,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_srp_auth.async_get_access_token.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_CREDENTIALS,
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
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_reauth_successful(
    hass: HomeAssistant,
    mock_srp_auth: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reauth flow."""
    await setup_integration(hass, mock_config_entry)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_CREDENTIALS,
    )
    assert result["reason"] == "reauth_successful"
    assert result["type"] is FlowResultType.ABORT


@pytest.mark.parametrize("mock_srp_access_token", [INVALID_TEST_ACCESS_JWT])
async def test_reauth_error(
    hass: HomeAssistant,
    mock_srp_auth: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reauth flow."""
    await setup_integration(hass, mock_config_entry)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=INVALID_TEST_CREDENTIALS,
    )
    assert result["reason"] == "unique_id_mismatch"
    assert result["type"] is FlowResultType.ABORT
