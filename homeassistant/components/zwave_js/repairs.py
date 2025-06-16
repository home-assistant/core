"""Repairs for Z-Wave JS."""

from __future__ import annotations

from homeassistant import data_entry_flow
from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN
from .helpers import async_get_node_from_device_id


class DeviceConfigFileChangedFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, data: dict[str, str]) -> None:
        """Initialize."""
        self.description_placeholders: dict[str, str] = {
            "device_name": data["device_name"]
        }
        self.device_id: str = data["device_id"]

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""
        return self.async_show_menu(
            menu_options=["confirm", "ignore"],
            description_placeholders=self.description_placeholders,
        )

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        try:
            node = async_get_node_from_device_id(self.hass, self.device_id)
        except ValueError:
            return self.async_abort(
                reason="cannot_connect",
                description_placeholders=self.description_placeholders,
            )
        self.hass.async_create_task(node.async_refresh_info())
        return self.async_create_entry(title="", data={})

    async def async_step_ignore(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the ignore step of a fix flow."""
        ir.async_get(self.hass).async_ignore(
            DOMAIN, f"device_config_file_changed.{self.device_id}", True
        )
        return self.async_abort(
            reason="issue_ignored",
            description_placeholders=self.description_placeholders,
        )


class MigrateUniqueIDFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, data: dict[str, str]) -> None:
        """Initialize."""
        self.description_placeholders: dict[str, str] = {
            "config_entry_title": data["config_entry_title"],
            "controller_model": data["controller_model"],
            "new_unique_id": data["new_unique_id"],
            "old_unique_id": data["old_unique_id"],
        }
        self._config_entry_id: str = data["config_entry_id"]

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
            config_entry = self.hass.config_entries.async_get_entry(
                self._config_entry_id
            )
            # If config entry was removed, we can ignore the issue.
            if config_entry is not None:
                self.hass.config_entries.async_update_entry(
                    config_entry,
                    unique_id=self.description_placeholders["new_unique_id"],
                )
            return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="confirm",
            description_placeholders=self.description_placeholders,
        )


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, str] | None
) -> RepairsFlow:
    """Create flow."""

    if issue_id.split(".")[0] == "device_config_file_changed":
        assert data
        return DeviceConfigFileChangedFlow(data)
    if issue_id.split(".")[0] == "migrate_unique_id":
        assert data
        return MigrateUniqueIDFlow(data)
    return ConfirmRepairFlow()
