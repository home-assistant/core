"""Test the SystemNexa2 config flow."""

from unittest.mock import MagicMock

from homeassistant.components.systemnexa2 import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_DEVICE_ID, CONF_HOST, CONF_MODEL, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_full_flow(
    hass: HomeAssistant,
    mock_system_nexa_2_device: MagicMock,
) -> None:
    """Test full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "10.0.0.131"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Device (Test Model)"
    assert result["data"] == {
        CONF_HOST: "10.0.0.131",
        CONF_NAME: "Test Device",
        CONF_DEVICE_ID: "test_device_id",
        CONF_MODEL: "Test Model",
    }


async def test_connection_timeout(
    hass: HomeAssistant, mock_system_nexa_2_device_timeout: MagicMock
) -> None:
    """Test connection timeout handling."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "10.0.0.131"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_connection"
    assert result["description_placeholders"] == {"host": "10.0.0.131"}


async def test_unsupported_device(
    hass: HomeAssistant, mock_system_nexa_2_device_unsupported: MagicMock
) -> None:
    """Test unsupported device model handling."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "10.0.0.131"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unsupported_model"
    assert result["description_placeholders"] == {
        "model": "Test Model",
        "version": "Test Model Version",
    }
