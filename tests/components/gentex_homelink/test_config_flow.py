"""Test the homelink config flow."""

from unittest.mock import AsyncMock

import botocore.exceptions
import pytest

from homeassistant.components.gentex_homelink.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


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

    mock_srp_auth.async_get_access_token.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_EMAIL: "test@test.com", CONF_PASSWORD: "SomePassword"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_srp_auth.async_get_access_token.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_EMAIL: "test@test.com", CONF_PASSWORD: "SomePassword"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
