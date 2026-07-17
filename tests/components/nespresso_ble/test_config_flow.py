"""Test the Nespresso config flow."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.nespresso_ble.const import DOMAIN
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import ADDRESS, SERVICE_INFO

from tests.common import MockConfigEntry


async def test_bluetooth_discovery(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test discovery via bluetooth creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=SERVICE_INFO
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == ADDRESS
    assert len(mock_setup_entry.mock_calls) == 1


async def test_bluetooth_discovery_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test discovery aborts when already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=SERVICE_INFO
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test the user flow with a discovered device."""
    with _patch_discovered([SERVICE_INFO]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_ADDRESS: ADDRESS}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == ADDRESS
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_no_devices(hass: HomeAssistant) -> None:
    """Test the user flow aborts with no discovered devices."""
    with _patch_discovered([]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


def _patch_discovered(service_infos):
    """Patch async_discovered_service_info."""
    return patch(
        "homeassistant.components.nespresso_ble.config_flow.async_discovered_service_info",
        return_value=service_infos,
    )
