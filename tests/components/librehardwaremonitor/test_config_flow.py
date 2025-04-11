"""Test the LibreHardwareMonitor config flow."""

from unittest.mock import AsyncMock, patch

from librehardwaremonitor_api import (
    LibreHardwareMonitorConnectionError,
    LibreHardwareMonitorNoDevicesError,
)

from homeassistant.components.librehardwaremonitor.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_DEVICES, CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr

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
    mock_lhm_client.get_main_hardware_devices.side_effect = (
        LibreHardwareMonitorConnectionError()
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=VALID_CONFIG
    )

    assert result
    assert result["errors"] == {"base": "cannot_connect"}


async def test_no_devices_error(
    hass: HomeAssistant, mock_lhm_client: AsyncMock
) -> None:
    """Test that the no devices error is shown."""
    mock_lhm_client.get_main_hardware_devices.side_effect = (
        LibreHardwareMonitorNoDevicesError()
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=VALID_CONFIG
    )

    assert result
    assert result["errors"] == {"base": "no_devices"}


async def test_lhm_server_already_exists(hass: HomeAssistant) -> None:
    """Test we only allow a single entry per server."""
    await init_integration(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=VALID_CONFIG,
    )

    assert result
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_no_device_selected(
    hass: HomeAssistant, mock_lhm_client: AsyncMock
) -> None:
    """Test that the no devices selected error is shown."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=VALID_CONFIG
    )

    selected_devices = {"devices": []}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=selected_devices
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_devices"
    assert result["errors"] == {"base": "no_devices_selected"}


async def test_full_flow_with_device_selection(
    hass: HomeAssistant, mock_lhm_client: AsyncMock
) -> None:
    """Test that a complete config entry is created."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=VALID_CONFIG
    )

    assert result
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_devices"
    assert result.get("errors") is None

    selected_devices = {
        "devices": ["AMD Ryzen 7 7800X3D", "NVIDIA GeForce RTX 4080 SUPER"]
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=selected_devices
    )

    assert result
    assert result["type"] is FlowResultType.CREATE_ENTRY

    config_entry = result["result"]
    assert config_entry.title == f"{VALID_CONFIG[CONF_HOST]}:{VALID_CONFIG[CONF_PORT]}"
    assert config_entry.data == {
        CONF_HOST: VALID_CONFIG[CONF_HOST],
        CONF_PORT: VALID_CONFIG[CONF_PORT],
        CONF_SCAN_INTERVAL: VALID_CONFIG[CONF_SCAN_INTERVAL],
    }
    assert config_entry.options == {
        CONF_DEVICES: ["AMD Ryzen 7 7800X3D", "NVIDIA GeForce RTX 4080 SUPER"]
    }


async def test_reconfiguration_flow(
    hass: HomeAssistant, mock_lhm_client: AsyncMock
) -> None:
    """Test that reconfiguration adapts config entry correctly and deletes old devices."""
    mock_entry = await init_integration(hass)
    assert mock_entry.state is ConfigEntryState.LOADED

    result = await mock_entry.start_reconfigure_flow(hass)

    assert result
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    updated_config = VALID_CONFIG
    updated_config[CONF_SCAN_INTERVAL] = 10
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=updated_config
    )

    assert result
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_devices"

    selected_devices = {
        "devices": ["AMD Ryzen 7 7800X3D", "NVIDIA GeForce RTX 4080 SUPER"]
    }

    device_registry = dr.async_get(hass)
    orphaned_device = device_registry.async_get_or_create(
        config_entry_id=mock_entry.entry_id,
        identifiers={(DOMAIN, "MSI MAG B650M MORTAR WIFI (MS-7D76)")},
    )

    with patch.object(
        device_registry,
        "async_remove_device",
        wraps=device_registry.async_remove_device,
    ) as mock_remove:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=selected_devices
        )
        mock_remove.assert_called_once_with(orphaned_device.id)

    assert result
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_entry.data == updated_config
    assert mock_entry.options[CONF_DEVICES] == [
        "AMD Ryzen 7 7800X3D",
        "NVIDIA GeForce RTX 4080 SUPER",
    ]

    await hass.config_entries.async_unload(mock_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.state is ConfigEntryState.NOT_LOADED
