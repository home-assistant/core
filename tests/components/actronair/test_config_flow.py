"""Tests for ActronAir OAuth2 Config Flow."""

from unittest.mock import patch

import pytest

from homeassistant.components.actronair.config_flow import OAuth2FlowHandler
from homeassistant.components.actronair.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.mark.asyncio
async def test_config_flow_initialization(hass: HomeAssistant) -> None:
    """Test initializing the OAuth2 config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


@pytest.mark.asyncio
async def test_oauth2_authorization_url(hass: HomeAssistant) -> None:
    """Test OAuth2 authorization URL generation."""
    flow = OAuth2FlowHandler()
    expected_scope = {"scope": "ac-system-access"}

    assert flow.extra_authorize_data == expected_scope


@pytest.mark.asyncio
async def test_config_flow_successful_auth(hass: HomeAssistant) -> None:
    """Test completing the OAuth2 authentication successfully."""
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.AbstractOAuth2FlowHandler.async_create_entry"
    ) as mock_create_entry:
        result = await hass.config_entries.flow.async_configure("test_flow_id", {})

        assert result["type"] == FlowResultType.CREATE_ENTRY
        mock_create_entry.assert_called_once()
