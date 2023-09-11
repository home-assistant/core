"""Repairs for Z-Wave JS."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.core import HomeAssistant

from .helpers import async_get_node_from_device_id


class DeviceConfigFileChangedFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, data: dict[str, str]) -> None:
        """Initialize."""
        self.device_name: str = data["device_name"]
        self.device_id: str = data["device_id"]

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
            try:
                node = async_get_node_from_device_id(self.hass, self.device_id)
            except ValueError:
                return self.async_abort(
                    reason="cannot_connect",
                    description_placeholders={"device_name": self.device_name},
                )
            self.hass.async_create_task(node.async_refresh_info())
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={"device_name": self.device_name},
        )


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, str] | None
) -> RepairsFlow:
    """Create flow."""

    if issue_id.split(".")[0] == "device_config_file_changed":
        assert data
        return DeviceConfigFileChangedFlow(data)
    return ConfirmRepairFlow()
