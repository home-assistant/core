"""Repairs flow for Shelly."""

from __future__ import annotations

from aioshelly.exceptions import DeviceConnectionError, RpcCallError
from aioshelly.rpc_device import RpcDevice
import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.core import HomeAssistant


class BleScannerFirmwareUpdateFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    _device: RpcDevice

    def __init__(self, *, device: RpcDevice) -> None:
        """Initialize."""
        self._device = device

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            return await self.async_step_update_firmware()

        return self.async_show_form(step_id="confirm", data_schema=vol.Schema({}))

    async def async_step_update_firmware(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        try:
            await self._device.trigger_ota_update()
        except RpcCallError as err:
            if "Resource unavailable: No update info!" in str(err):
                return self.async_abort(reason="update_not_available")
            return self.async_abort(reason="cannot_connect")
        except DeviceConnectionError:
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(title="", data={})


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, str] | None
) -> RepairsFlow:
    """Create flow."""
    if issue_id.startswith("ble_scanner_firmware_unsupported"):
        if (
            data is not None
            and (entry_id := data.get("entry_id")) is not None
            and (entry := hass.config_entries.async_get_entry(entry_id)) is not None
        ):
            device = entry.runtime_data.rpc.device
            return BleScannerFirmwareUpdateFlow(device=device)

    return ConfirmRepairFlow()
