"""Test config flow for Swing2Sleep Smarla integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.smarla.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import MOCK_SERIAL_NUMBER, MOCK_USER_INPUT

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_setup_entry", "mock_connection")
async def test_config_flow(hass: HomeAssistant) -> None:
    """Test creating a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_SERIAL_NUMBER
    assert result["data"] == MOCK_USER_INPUT
    assert result["result"].unique_id == MOCK_SERIAL_NUMBER


@pytest.mark.usefixtures("mock_setup_entry", "mock_connection")
async def test_malformed_token(hass: HomeAssistant) -> None:
    """Test we show user form on malformed token input."""
    with patch(
        "homeassistant.components.smarla.config_flow.Connection", side_effect=ValueError
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "malformed_token"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_invalid_auth(hass: HomeAssistant, mock_connection: MagicMock) -> None:
    """Test we show user form on invalid auth."""
    with patch.object(
        mock_connection, "refresh_token", new=AsyncMock(return_value=False)
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry", "mock_connection")
async def test_device_exists_abort(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we abort config flow if Smarla device already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=MOCK_USER_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
