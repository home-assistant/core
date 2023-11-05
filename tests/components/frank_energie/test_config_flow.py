"""Test the Frank Energie config flow."""
from unittest.mock import AsyncMock, patch

import pytest
from python_frank_energie.exceptions import AuthException
from python_frank_energie.models import Authentication
from syrupy.assertion import SnapshotAssertion

from homeassistant import config_entries
from homeassistant.components.frank_energie.const import DOMAIN
from homeassistant.const import CONF_AUTHENTICATION, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.mark.usefixtures("mock_setup_entry")
async def test_flow_anonymous(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, snapshot: SnapshotAssertion
) -> None:
    """Test config flow handles non-authenticated setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AUTHENTICATION: False}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result == snapshot

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_setup_entry")
async def test_flow_authenticated(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, snapshot: SnapshotAssertion
) -> None:
    """Test config flow handles authenticated setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AUTHENTICATION: True}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "login"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.frank_energie.config_flow.FrankEnergie.login",
        return_value=Authentication("auth_token", "refresh_token"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "username@example.com",
                CONF_PASSWORD: "CorrectHorseBatteryStaple",
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result == snapshot

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_flow_authentication_failed(hass: HomeAssistant) -> None:
    """Test config flow handles authenticated setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AUTHENTICATION: True}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "login"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.frank_energie.config_flow.FrankEnergie.login",
        side_effect=AuthException,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "username@example.com",
                CONF_PASSWORD: "IncorrectHorseBatteryStaple",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "login"
    assert result["errors"] == {"base": "invalid_auth"}
