"""Tests for the Pinecil config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.iron_os import DOMAIN
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import DEFAULT_NAME, PINECIL_SERVICE_INFO, USER_INPUT


async def test_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, discovery: MagicMock
) -> None:
    """Test the user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == {}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_no_device_discovered(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    discovery: MagicMock,
) -> None:
    """Test setup with no device discoveries."""
    discovery.return_value = []
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_async_step_bluetooth(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth.."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=PINECIL_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == {}
    assert result["result"].unique_id == "c0:ff:ee:c0:ff:ee"
