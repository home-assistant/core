"""Tests for Ghost config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import config_entries
from homeassistant.components.ghost.const import (
    CONF_ADMIN_API_KEY,
    CONF_API_URL,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import API_KEY, API_URL

from tests.common import MockConfigEntry


async def test_form_user(hass: HomeAssistant, mock_ghost_api: AsyncMock) -> None:
    """Test the user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.ghost.config_flow.GhostAdminAPI",
        return_value=mock_ghost_api,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_URL: API_URL,
                CONF_ADMIN_API_KEY: API_KEY,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Ghost"
    assert result["data"] == {
        CONF_API_URL: API_URL,
        CONF_ADMIN_API_KEY: API_KEY,
    }


async def test_form_invalid_api_key_format(hass: HomeAssistant) -> None:
    """Test error on invalid API key format."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
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


async def test_form_invalid_auth(
    hass: HomeAssistant, mock_ghost_api_auth_error: AsyncMock
) -> None:
    """Test error on invalid authentication."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ghost.config_flow.GhostAdminAPI",
        return_value=mock_ghost_api_auth_error,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_URL: API_URL,
                CONF_ADMIN_API_KEY: API_KEY,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_ghost_api_connection_error: AsyncMock
) -> None:
    """Test error on connection failure."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ghost.config_flow.GhostAdminAPI",
        return_value=mock_ghost_api_connection_error,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_URL: API_URL,
                CONF_ADMIN_API_KEY: API_KEY,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_already_configured(
    hass: HomeAssistant, mock_config_entry, mock_ghost_api: AsyncMock
) -> None:
    """Test error when already configured."""
    # Add existing entry to hass
    mock_config_entry.add_to_hass(hass)

    # Try to configure a second entry with same URL
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.ghost.config_flow.GhostAdminAPI",
        return_value=mock_ghost_api,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_URL: API_URL,
                CONF_ADMIN_API_KEY: API_KEY,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow(
    hass: HomeAssistant, mock_ghost_api: AsyncMock, mock_config_entry
) -> None:
    """Test the reauth flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    new_api_key = (
        "newid:newsecret1234567890abcdef1234567890abcdef1234567890abcdef12345678"
    )

    with patch(
        "homeassistant.components.ghost.config_flow.GhostAdminAPI",
        return_value=mock_ghost_api,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADMIN_API_KEY: new_api_key},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_ADMIN_API_KEY] == new_api_key


async def test_reauth_flow_invalid_auth(
    hass: HomeAssistant, mock_ghost_api_auth_error: AsyncMock, mock_config_entry
) -> None:
    """Test the reauth flow with invalid credentials."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )

    with patch(
        "homeassistant.components.ghost.config_flow.GhostAdminAPI",
        return_value=mock_ghost_api_auth_error,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADMIN_API_KEY: API_KEY},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_reauth_flow_invalid_api_key_format(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test the reauth flow with invalid API key format (no colon)."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )

    # Try with API key that has no colon
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ADMIN_API_KEY: "invalidkeynocolor"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_api_key"}


async def test_reauth_flow_connection_error(
    hass: HomeAssistant, mock_ghost_api_connection_error: AsyncMock, mock_config_entry
) -> None:
    """Test the reauth flow with connection error."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )

    with patch(
        "homeassistant.components.ghost.config_flow.GhostAdminAPI",
        return_value=mock_ghost_api_connection_error,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADMIN_API_KEY: API_KEY},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test handling of unexpected exception during setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_api = MagicMock()
    mock_api.get_site = AsyncMock(side_effect=RuntimeError("Unexpected"))
    mock_api.close = AsyncMock()

    with patch(
        "homeassistant.components.ghost.config_flow.GhostAdminAPI",
        return_value=mock_api,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_URL: API_URL,
                CONF_ADMIN_API_KEY: API_KEY,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_reconfigure_flow(
    hass: HomeAssistant, mock_ghost_api: AsyncMock, mock_config_entry
) -> None:
    """Test the reconfigure flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    new_api_url = "https://new-ghost.example.com"

    with patch(
        "homeassistant.components.ghost.config_flow.GhostAdminAPI",
        return_value=mock_ghost_api,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_URL: new_api_url},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_API_URL] == new_api_url


async def test_reconfigure_flow_invalid_auth(
    hass: HomeAssistant, mock_ghost_api_auth_error: AsyncMock, mock_config_entry
) -> None:
    """Test the reconfigure flow with invalid auth (API key doesn't work with new URL)."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    with patch(
        "homeassistant.components.ghost.config_flow.GhostAdminAPI",
        return_value=mock_ghost_api_auth_error,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_URL: "https://new-ghost.example.com"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_reconfigure_flow_connection_error(
    hass: HomeAssistant, mock_ghost_api_connection_error: AsyncMock, mock_config_entry
) -> None:
    """Test the reconfigure flow with connection error."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    with patch(
        "homeassistant.components.ghost.config_flow.GhostAdminAPI",
        return_value=mock_ghost_api_connection_error,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_URL: "https://new-ghost.example.com"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reconfigure_flow_already_configured(
    hass: HomeAssistant, mock_ghost_api: AsyncMock, mock_config_entry
) -> None:
    """Test reconfigure flow aborts when URL changes to already configured site."""
    mock_config_entry.add_to_hass(hass)

    # Set up another config entry with a different URL
    other_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Other Ghost",
        data={
            CONF_API_URL: "https://other-ghost.example.com",
            CONF_ADMIN_API_KEY: API_KEY,
        },
        unique_id="https://other-ghost.example.com",
    )
    other_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    with patch(
        "homeassistant.components.ghost.config_flow.GhostAdminAPI",
        return_value=mock_ghost_api,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_URL: "https://other-ghost.example.com"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_flow_unknown_error(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test the reconfigure flow with an unexpected error."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    mock_api = MagicMock()
    mock_api.get_site = AsyncMock(side_effect=RuntimeError("Unexpected"))

    with patch(
        "homeassistant.components.ghost.config_flow.GhostAdminAPI",
        return_value=mock_api,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_URL: "https://new-ghost.example.com"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}
