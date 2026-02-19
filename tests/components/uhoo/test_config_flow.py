"""Test the Uhoo config flow."""

from unittest.mock import AsyncMock

import pytest
from uhooapi.errors import UhooError, UnauthorizedError

from homeassistant.components.uhoo.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user_flow(
    hass: HomeAssistant, mock_uhoo_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test a complete user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "valid-api-key-12345"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "uHoo (12345)"
    assert result["data"] == {CONF_API_KEY: "valid-api-key-12345"}

    mock_setup_entry.assert_called_once()


async def test_user_duplicate_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test duplicate entry aborts."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "valid-api-key-12345"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception", "error_type"),
    [
        (UhooError("asd"), "cannot_connect"),
        (UnauthorizedError("Invalid credentials"), "invalid_auth"),
        (Exception(), "unknown"),
    ],
)
async def test_user_flow_exceptions(
    hass: HomeAssistant,
    mock_uhoo_client: AsyncMock,
    exception: Exception,
    error_type: str,
) -> None:
    """Test form when client raises various exceptions."""
    mock_uhoo_client.login.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "test-api-key"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error_type}

    mock_uhoo_client.login.assert_called_once()
    mock_uhoo_client.login.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "test-api-key"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
