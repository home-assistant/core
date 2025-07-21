"""Test the LibreHardwareMonitor config flow."""

from unittest.mock import AsyncMock

from librehardwaremonitor_api import (
    LibreHardwareMonitorConnectionError,
    LibreHardwareMonitorNoDevicesError,
)

from homeassistant.components.libre_hardware_monitor.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import VALID_CONFIG

from tests.common import MockConfigEntry


async def test_create_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_lhm_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a complete config entry is created."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=VALID_CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id is None

    mock_config_entry = result["result"]
    assert (
        mock_config_entry.title
        == f"{VALID_CONFIG[CONF_HOST]}:{VALID_CONFIG[CONF_PORT]}"
    )
    assert mock_config_entry.data == VALID_CONFIG

    assert mock_setup_entry.call_count == 1


async def test_errors_and_flow_recovery(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_lhm_client: AsyncMock
) -> None:
    """Test that errors are shown as expected."""
    mock_lhm_client.get_data.side_effect = LibreHardwareMonitorConnectionError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=VALID_CONFIG
    )

    assert result["errors"] == {"base": "cannot_connect"}
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_lhm_client.get_data.side_effect = LibreHardwareMonitorNoDevicesError()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=VALID_CONFIG
    )

    assert result["errors"] == {"base": "no_devices"}
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_lhm_client.get_data.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=VALID_CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    assert mock_setup_entry.call_count == 1


async def test_lhm_server_already_exists(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test we only allow a single entry per server."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=VALID_CONFIG
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert mock_setup_entry.call_count == 0
