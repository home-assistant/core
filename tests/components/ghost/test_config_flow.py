"""Tests for Ghost config flow."""

from unittest.mock import AsyncMock

from aioghost.exceptions import GhostAuthError, GhostConnectionError
import pytest

from homeassistant.components.ghost.const import (
    CONF_ADMIN_API_KEY,
    CONF_API_URL,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import API_KEY, API_URL, SITE_UUID


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_user(hass: HomeAssistant, mock_ghost_api: AsyncMock) -> None:
    """Test the user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_URL: API_URL,
            CONF_ADMIN_API_KEY: API_KEY,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Ghost"
    assert result["result"].unique_id == SITE_UUID
    assert result["data"] == {
        CONF_API_URL: API_URL,
        CONF_ADMIN_API_KEY: API_KEY,
    }


async def test_form_invalid_api_key_format(hass: HomeAssistant) -> None:
    """Test error on invalid API key format."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_URL: API_URL,
            CONF_ADMIN_API_KEY: "invalid-no-colon",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_api_key"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_already_configured(
    hass: HomeAssistant, mock_config_entry, mock_ghost_api: AsyncMock
) -> None:
    """Test error when already configured."""
    # Add existing entry to hass
    mock_config_entry.add_to_hass(hass)

    # Try to configure a second entry with same URL
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_URL: API_URL,
            CONF_ADMIN_API_KEY: API_KEY,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "error_key"),
    [
        (GhostAuthError("Invalid API key"), "invalid_auth"),
        (GhostConnectionError("Connection failed"), "cannot_connect"),
        (RuntimeError("Unexpected"), "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_errors_can_recover(
    hass: HomeAssistant,
    mock_ghost_api: AsyncMock,
    side_effect: Exception,
    error_key: str,
) -> None:
    """Test errors and recovery during setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_ghost_api.get_site.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_URL: API_URL,
            CONF_ADMIN_API_KEY: API_KEY,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_key}

    mock_ghost_api.get_site.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_URL: API_URL,
            CONF_ADMIN_API_KEY: API_KEY,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Ghost"
    assert result["result"].unique_id == SITE_UUID
    assert result["data"] == {
        CONF_API_URL: API_URL,
        CONF_ADMIN_API_KEY: API_KEY,
    }
