"""Repairs implementation for the esphome integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.assist_pipeline.repair_flows import (
    AssistInProgressDeprecatedRepairFlow,
)
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .manager import async_replace_device


class ESPHomeRepair(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, data: dict[str, str | int | float | None] | None) -> None:
        """Initialize."""
        self._data = data
        super().__init__()

    @callback
    def _async_get_placeholders(self) -> dict[str, str]:
        issue_registry = ir.async_get(self.hass)
        description_placeholders: dict[str, str] = {}
        if issue := issue_registry.async_get_issue(self.handler, self.issue_id):
            return issue.translation_placeholders or {}
        return description_placeholders


class DeviceConflictRepair(ESPHomeRepair):
    """Handler for an issue fixing device conflict."""

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_start()

    async def async_step_start(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the start step of a fix flow."""
        if user_input is None:
            return self.async_show_form(
                step_id="start",
                data_schema=vol.Schema(
                    {
                        vol.Required("action"): vol.In(
                            {"replace": "Replace", "ignore": "Ignore"}
                        )
                    }
                ),
                description_placeholders=self._async_get_placeholders(),
            )
        if user_input["action"] == "replace":
            return await self.async_step_confirm()
        return await self.async_step_ignored()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is None:
            return self.async_show_form(
                step_id="confirm",
                data_schema=vol.Schema({}),
                description_placeholders=self._async_get_placeholders(),
            )
        assert isinstance(self._data, dict)
        entry_id = self._data["entry_id"]
        mac = self._data["mac"]
        assert isinstance(entry_id, str)
        assert isinstance(mac, str)
        async_replace_device(self.hass, entry_id, mac)
        self.hass.config_entries.async_schedule_reload(entry_id)
        return self.async_create_entry(data={})

    async def async_step_ignored(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the ignored step of a fix flow."""
        if user_input is None:
            return self.async_show_form(
                step_id="ignored",
                data_schema=vol.Schema({}),
                description_placeholders=self._async_get_placeholders(),
            )
        return self.async_create_entry(data={})


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    if issue_id.startswith("assist_in_progress_deprecated"):
        return AssistInProgressDeprecatedRepairFlow(data)
    if issue_id.startswith("device_conflict"):
        return DeviceConflictRepair(data)
    # If ESPHome adds confirm-only repairs in the future, this should be changed
    # to return a ConfirmRepairFlow instead of raising a ValueError
    raise ValueError(f"unknown repair {issue_id}")
