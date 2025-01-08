"""Test the LetPot config flow."""

from typing import Any
from unittest.mock import AsyncMock, patch

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


async def test_full_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test full flow with success."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.letpot.config_flow.LetPotClient.login",
        return_value=AUTHENTICATION,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "email@example.com",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

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
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test flow with exception during login and recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.letpot.config_flow.LetPotClient.login",
        side_effect=exception,
    ):
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
    with patch(
        "homeassistant.components.letpot.config_flow.LetPotClient.login",
        return_value=AUTHENTICATION,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "email@example.com",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    _assert_result_success(result)
    assert len(mock_setup_entry.mock_calls) == 1


async def test_flow_duplicate(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_config_entry: MockConfigEntry
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

    with patch(
        "homeassistant.components.letpot.config_flow.LetPotClient.login",
        return_value=AUTHENTICATION,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "email@example.com",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(mock_setup_entry.mock_calls) == 0
