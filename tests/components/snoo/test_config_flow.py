"""Test the Happiest Baby Snoo config flow."""

from unittest.mock import AsyncMock

import pytest
from python_snoo.exceptions import InvalidSnooAuth, SnooAuthException

from homeassistant import config_entries
from homeassistant.components.snoo.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import create_entry
from .conftest import MockedSnoo


async def test_config_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, bypass_api: MockedSnoo
) -> None:
    """Test we create the entry successfully."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-username"
    assert result["data"] == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert result["result"].unique_id == "123e4567-e89b-12d3-a456-426614174000"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error_msg"),
    [
        (InvalidSnooAuth, "invalid_auth"),
        (SnooAuthException, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_auth_issues(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    bypass_api: MockedSnoo,
    exception,
    error_msg,
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    # Set Authorize to fail.
    bypass_api.set_auth_error(exception)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    # Reset auth back to the original
    bypass_api.set_auth_error(None)
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": error_msg}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-username"
    assert result["data"] == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_account_already_configured(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, bypass_api
) -> None:
    """Ensure we abort if the config flow already exists."""
    create_entry(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
