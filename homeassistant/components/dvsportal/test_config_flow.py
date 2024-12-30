"""Test of config."""

from unittest.mock import AsyncMock, patch

from dvsportal import DVSPortalAuthError
import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import DOMAIN

pytestmark = pytest.mark.asyncio

# Mocked valid user input
VALID_USER_INPUT = {
    CONF_HOST: "test-host",
    CONF_USERNAME: "test-user",
    CONF_PASSWORD: "test-pass",
    "user_agent": "HomeAssistant",
}

# Mock unique ID
UNIQUE_ID = "test-host.test-user"


async def test_full_flow_success(hass: HomeAssistant) -> None:
    """Test the successful user config flow."""
    with (
        patch(
            "homeassistant.components.dvsportal.config_flow.DVSPortal.token",
            return_value=True,
        ) as mock_token,
        patch(
            "homeassistant.components.dvsportal.config_flow.DVSPortal.close",
            new=AsyncMock(),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], VALID_USER_INPUT
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "test-user"
        assert result["data"] == VALID_USER_INPUT
        mock_token.assert_called_once()


async def test_invalid_auth(hass: HomeAssistant) -> None:
    """Test invalid authentication during user config flow."""
    with (
        patch(
            "homeassistant.components.dvsportal.config_flow.DVSPortal.token",
            side_effect=DVSPortalAuthError,
        ),
        patch(
            "homeassistant.components.dvsportal.config_flow.DVSPortal.close",
            new=AsyncMock(),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], VALID_USER_INPUT
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}


async def test_duplicate_entry(hass: HomeAssistant) -> None:
    """Test duplicate config entry prevention."""
    with (
        patch(
            "homeassistant.components.dvsportal.config_flow.DVSPortal.token",
            return_value=True,
        ),
        patch(
            "homeassistant.components.dvsportal.config_flow.DVSPortal.close",
            new=AsyncMock(),
        ),
    ):
        # First entry
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], VALID_USER_INPUT
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY

        # Duplicate entry
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], VALID_USER_INPUT
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_unknown_exception(hass: HomeAssistant) -> None:
    """Test unknown exception handling in config flow."""
    with (
        patch(
            "homeassistant.components.dvsportal.config_flow.DVSPortal.token",
            side_effect=Exception("Unknown error"),
        ),
        patch(
            "homeassistant.components.dvsportal.config_flow.DVSPortal.close",
            new=AsyncMock(),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], VALID_USER_INPUT
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}
