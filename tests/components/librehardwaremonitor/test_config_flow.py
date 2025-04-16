"""Test the LibreHardwareMonitor config flow."""

from unittest.mock import AsyncMock

from librehardwaremonitor_api import (
    LibreHardwareMonitorConnectionError,
    LibreHardwareMonitorNoDevicesError,
)

from homeassistant.components.librehardwaremonitor.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import VALID_CONFIG, init_integration


async def test_show_configuration_form(hass: HomeAssistant) -> None:
    """Test that the configuration form is shown."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_connection_error(
    hass: HomeAssistant, mock_lhm_client: AsyncMock
) -> None:
    """Test that the no connection error is shown."""
    mock_lhm_client.get_data.side_effect = LibreHardwareMonitorConnectionError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=VALID_CONFIG
    )

    assert result
    assert result["errors"] == {"base": "cannot_connect"}


async def test_no_devices_error(
    hass: HomeAssistant, mock_lhm_client: AsyncMock
) -> None:
    """Test that the no devices error is shown."""
    mock_lhm_client.get_data.side_effect = LibreHardwareMonitorNoDevicesError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=VALID_CONFIG
    )

    assert result
    assert result["errors"] == {"base": "no_devices"}


async def test_lhm_server_already_exists(hass: HomeAssistant) -> None:
    """Test we only allow a single entry per server."""
    await init_integration(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=VALID_CONFIG
    )

    assert result
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_create_entry(hass: HomeAssistant, mock_lhm_client: AsyncMock) -> None:
    """Test that a complete config entry is created."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=VALID_CONFIG
    )

    assert result
    assert result["type"] is FlowResultType.CREATE_ENTRY

    config_entry = result["result"]
    assert config_entry.title == f"{VALID_CONFIG[CONF_HOST]}:{VALID_CONFIG[CONF_PORT]}"
    assert config_entry.data == {
        CONF_HOST: VALID_CONFIG[CONF_HOST],
        CONF_PORT: VALID_CONFIG[CONF_PORT],
    }
