"""Tests for the Voltie Charger config flow."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from voltie import VoltieAuthenticationError, VoltieConnectionError, VoltieError

from homeassistant.components.voltie_charger.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import CHARGER_ID, HOST, PORT


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow(hass: HomeAssistant, mock_voltie: MagicMock) -> None:
    """Test the full user flow, with credentials and a custom port."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: HOST,
            CONF_PORT: 8080.0,
            CONF_USERNAME: "api",
            CONF_PASSWORD: "secret",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Voltie Charger 4335"
    assert result["data"] == {
        CONF_HOST: HOST,
        CONF_PORT: 8080,
        CONF_USERNAME: "api",
        CONF_PASSWORD: "secret",
    }
    assert result["result"].unique_id == CHARGER_ID


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_without_credentials(
    hass: HomeAssistant, mock_voltie: MagicMock
) -> None:
    """Test the user flow for a charger without authentication."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PORT: PORT}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: HOST, CONF_PORT: PORT}
    assert result["result"].unique_id == CHARGER_ID


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (VoltieAuthenticationError, "invalid_auth"),
        (VoltieConnectionError, "cannot_connect"),
        (VoltieError, "unknown"),
        (Exception, "unknown"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_voltie: MagicMock,
    side_effect: type[Exception],
    error: str,
) -> None:
    """Test the user flow shows errors and recovers from them."""
    mock_voltie.status.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PORT: PORT}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_voltie.status.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PORT: PORT}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == CHARGER_ID


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_incomplete_credentials(
    hass: HomeAssistant, mock_voltie: MagicMock
) -> None:
    """Test a username without a password is refused before connecting."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PORT: PORT, CONF_USERNAME: "api"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "incomplete_credentials"}
    mock_voltie.status.assert_not_called()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            CONF_USERNAME: "api",
            CONF_PASSWORD: "secret",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == CHARGER_ID


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_unsupported_firmware(
    hass: HomeAssistant, mock_voltie: MagicMock
) -> None:
    """Test firmware with an HTTP API older than version 5 is refused."""
    mock_voltie.api_version.side_effect = [4, 5]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PORT: PORT}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unsupported_firmware"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PORT: PORT}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_voltie")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a charger can only be added once."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "voltiecharger-4335.local", CONF_PORT: PORT}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
