"""Tests for the gridX config flow."""

from unittest.mock import AsyncMock

from gridx_connector import GridXAuthenticationError, GridXConnectionError
import pytest

from homeassistant.components.gridx.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import PASSWORD, USERNAME

from tests.common import MockConfigEntry

USER_INPUT = {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}


@pytest.mark.usefixtures("mock_connector", "mock_setup_entry")
async def test_full_flow(hass: HomeAssistant) -> None:
    """Test the full user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == USERNAME
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == USERNAME


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (GridXAuthenticationError("denied"), "invalid_auth"),
        (GridXConnectionError("offline"), "cannot_connect"),
        (ValueError("boom"), "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_flow_errors(
    hass: HomeAssistant,
    mock_connector: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test errors are shown and the flow can recover."""
    mock_connector.initialize.side_effect = exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_connector.initialize.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_flow_no_systems(hass: HomeAssistant, mock_connector: AsyncMock) -> None:
    """Test an account without systems cannot be set up."""
    mock_connector.systems = {}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_systems"}


@pytest.mark.usefixtures("mock_connector", "mock_setup_entry")
async def test_flow_already_configured_updates_password(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test re-adding an account aborts and updates the stored password."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: USERNAME.upper(), CONF_PASSWORD: "new"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_PASSWORD] == "new"
