"""Test the Foreca config flow."""

from unittest.mock import AsyncMock, MagicMock

from pyforeca import ForecaAuthError, ForecaConnectionError
import pytest

from homeassistant.components.foreca.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

USER_INPUT = {
    CONF_API_KEY: "test-key",
    CONF_LOCATION: {CONF_LATITUDE: 60.17, CONF_LONGITUDE: 24.94},
}


@pytest.mark.usefixtures("mock_foreca_client", "mock_setup_entry")
async def test_full_flow(hass: HomeAssistant) -> None:
    """Test the full user flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Helsinki"
    assert result["result"].unique_id == "60.1700-24.9400"
    assert result["data"] == {
        CONF_API_KEY: "test-key",
        CONF_LATITUDE: 60.17,
        CONF_LONGITUDE: 24.94,
    }


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("exception", "error"),
    [
        pytest.param(ForecaAuthError, "invalid_auth", id="invalid_auth"),
        pytest.param(ForecaConnectionError, "cannot_connect", id="cannot_connect"),
        pytest.param(ValueError, "unknown", id="unknown"),
    ],
)
async def test_form_errors_recover(
    hass: HomeAssistant,
    mock_foreca_client: MagicMock,
    exception: Exception,
    error: str,
) -> None:
    """Test the form shows an error and recovers on retry."""
    mock_foreca_client.location_info.side_effect = exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_foreca_client.location_info.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_foreca_client", "mock_setup_entry")
async def test_duplicate_entry_aborts(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test configuring the same location twice aborts."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_entry_title_falls_back_without_location_name(
    hass: HomeAssistant, mock_foreca_client: MagicMock
) -> None:
    """Test the entry title falls back when the API returns no location name."""
    mock_foreca_client.location_info = AsyncMock(
        return_value=type("L", (), {"name": None})()
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Foreca"
