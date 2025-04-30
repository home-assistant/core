"""Repairs flow for Shelly."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aioshelly.exceptions import DeviceConnectionError, RpcCallError
from aioshelly.rpc_device import RpcDevice
import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir


class BleScannerFirmwareUpdateFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, device: RpcDevice) -> None:
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

        issue_registry = ir.async_get(self.hass)
        description_placeholders = None
        if issue := issue_registry.async_get_issue(self.handler, self.issue_id):
            description_placeholders = issue.translation_placeholders

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders=description_placeholders,
        )

    async def async_step_update_firmware(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        if not self._device.status["sys"]["available_updates"]:
            return self.async_abort(reason="update_not_available")
        try:
            await self._device.trigger_ota_update()
        except (DeviceConnectionError, RpcCallError):
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(title="", data={})


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, str] | None
) -> RepairsFlow:
    """Create flow."""
    if TYPE_CHECKING:
        assert isinstance(data, dict)

    entry_id = data["entry_id"]
    entry = hass.config_entries.async_get_entry(entry_id)

    if TYPE_CHECKING:
        assert entry is not None

    device = entry.runtime_data.rpc.device
    return BleScannerFirmwareUpdateFlow(device)
