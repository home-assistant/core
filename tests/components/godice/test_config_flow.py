"""Test the godice config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.godice.const import CONF_SHELL, DOMAIN
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import GODICE_DEVICE_SERVICE_INFO


async def test_async_step_bluetooth_valid_device(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth with a valid device."""
    config_flow = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=GODICE_DEVICE_SERVICE_INFO,
    )
    assert config_flow["type"] == FlowResultType.FORM
    assert config_flow["step_id"] == "discovery_confirm"
    dice_shell = "D6"
    with patch("homeassistant.components.godice.async_setup_entry", return_value=True):
        config_entry = await hass.config_entries.flow.async_configure(
            config_flow["flow_id"], user_input={CONF_SHELL: dice_shell}
        )
    assert config_entry["type"] == FlowResultType.CREATE_ENTRY
    assert config_entry["title"] == GODICE_DEVICE_SERVICE_INFO.name
    assert config_entry["result"].unique_id == GODICE_DEVICE_SERVICE_INFO.address
    assert config_entry["data"] == {
        CONF_NAME: GODICE_DEVICE_SERVICE_INFO.name,
        CONF_ADDRESS: GODICE_DEVICE_SERVICE_INFO.address,
        CONF_SHELL: dice_shell,
    }


async def test_async_step_user_abort(hass: HomeAssistant) -> None:
    """Test manual setup is not supported."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "auto_discovery_only"
