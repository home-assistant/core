"""Test the LetPot config flow."""

import dataclasses
from typing import Any
from unittest.mock import AsyncMock

from letpot.exceptions import LetPotAuthenticationException, LetPotConnectionException
import pytest

from homeassistant.components.letpot.const import (
    CONF_ACCESS_TOKEN_EXPIRES,
    CONF_REFRESH_TOKEN,
    CONF_REFRESH_TOKEN_EXPIRES,
    CONF_USER_ID,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import AUTHENTICATION

from tests.common import MockConfigEntry


def _assert_result_success(result: Any) -> None:
    """Assert successful end of flow result, creating an entry."""
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == AUTHENTICATION.email
    assert result["data"] == {
        CONF_ACCESS_TOKEN: AUTHENTICATION.access_token,
        CONF_ACCESS_TOKEN_EXPIRES: AUTHENTICATION.access_token_expires,
        CONF_REFRESH_TOKEN: AUTHENTICATION.refresh_token,
        CONF_REFRESH_TOKEN_EXPIRES: AUTHENTICATION.refresh_token_expires,
        CONF_USER_ID: AUTHENTICATION.user_id,
        CONF_EMAIL: AUTHENTICATION.email,
    }
    assert result["result"].unique_id == AUTHENTICATION.user_id


async def test_full_flow(
    hass: HomeAssistant, mock_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test full flow with success."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "email@example.com",
            CONF_PASSWORD: "test-password",
        },
    )

    _assert_result_success(result)
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (LetPotAuthenticationException, "invalid_auth"),
        (LetPotConnectionException, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_flow_exceptions(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test flow with exception during login and recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_client.login.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "email@example.com",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    # Retry to show recovery.
    mock_client.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "email@example.com",
            CONF_PASSWORD: "test-password",
        },
    )

    _assert_result_success(result)
    assert len(mock_setup_entry.mock_calls) == 1


async def test_flow_duplicate(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test flow aborts when trying to add a previously added account."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "email@example.com",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(mock_setup_entry.mock_calls) == 0


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow with success."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    updated_auth = dataclasses.replace(
        AUTHENTICATION,
        access_token="new_access_token",
        refresh_token="new_refresh_token",
    )
    mock_client.login.return_value = updated_auth
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "new-password"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_ACCESS_TOKEN: "new_access_token",
        CONF_ACCESS_TOKEN_EXPIRES: AUTHENTICATION.access_token_expires,
        CONF_REFRESH_TOKEN: "new_refresh_token",
        CONF_REFRESH_TOKEN_EXPIRES: AUTHENTICATION.refresh_token_expires,
        CONF_USER_ID: AUTHENTICATION.user_id,
        CONF_EMAIL: AUTHENTICATION.email,
    }
    assert len(hass.config_entries.async_entries()) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (LetPotAuthenticationException, "invalid_auth"),
        (LetPotConnectionException, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_reauth_exceptions(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    error: str,
) -> None:
    """Test reauth flow with exception during login and recovery."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_client.login.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "new-password"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    # Retry to show recovery.
    updated_auth = dataclasses.replace(
        AUTHENTICATION,
        access_token="new_access_token",
        refresh_token="new_refresh_token",
    )
    mock_client.login.return_value = updated_auth
    mock_client.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "new-password"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_ACCESS_TOKEN: "new_access_token",
        CONF_ACCESS_TOKEN_EXPIRES: AUTHENTICATION.access_token_expires,
        CONF_REFRESH_TOKEN: "new_refresh_token",
        CONF_REFRESH_TOKEN_EXPIRES: AUTHENTICATION.refresh_token_expires,
        CONF_USER_ID: AUTHENTICATION.user_id,
        CONF_EMAIL: AUTHENTICATION.email,
    }
    assert len(hass.config_entries.async_entries()) == 1


async def test_reauth_different_user_id_new(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow with different, new user ID updating the existing entry."""
    mock_config_entry.add_to_hass(hass)
    config_entries = hass.config_entries.async_entries()
    assert len(config_entries) == 1
    assert config_entries[0].unique_id == AUTHENTICATION.user_id

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    updated_auth = dataclasses.replace(AUTHENTICATION, user_id="new_user_id")
    mock_client.login.return_value = updated_auth
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "new-password"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_ACCESS_TOKEN: AUTHENTICATION.access_token,
        CONF_ACCESS_TOKEN_EXPIRES: AUTHENTICATION.access_token_expires,
        CONF_REFRESH_TOKEN: AUTHENTICATION.refresh_token,
        CONF_REFRESH_TOKEN_EXPIRES: AUTHENTICATION.refresh_token_expires,
        CONF_USER_ID: "new_user_id",
        CONF_EMAIL: AUTHENTICATION.email,
    }
    config_entries = hass.config_entries.async_entries()
    assert len(config_entries) == 1
    assert config_entries[0].unique_id == "new_user_id"


async def test_reauth_different_user_id_existing(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow with different, existing user ID aborting."""
    mock_config_entry.add_to_hass(hass)
    mock_other = MockConfigEntry(
        domain=DOMAIN, title="email2@example.com", data={}, unique_id="other_user_id"
    )
    mock_other.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    updated_auth = dataclasses.replace(AUTHENTICATION, user_id="other_user_id")
    mock_client.login.return_value = updated_auth
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "new-password"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries()) == 2
