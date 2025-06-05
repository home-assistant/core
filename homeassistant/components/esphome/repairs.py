"""Repairs implementation for the esphome integration."""

from __future__ import annotations

from typing import cast

import voluptuous as vol

from homeassistant import data_entry_flow
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
        issue = issue_registry.async_get_issue(self.handler, self.issue_id)
        assert issue is not None
        return issue.translation_placeholders or {}


class DeviceConflictRepair(ESPHomeRepair):
    """Handler for an issue fixing device conflict."""

    @property
    def entry_id(self) -> str:
        """Return the config entry id."""
        assert isinstance(self._data, dict)
        return cast(str, self._data["entry_id"])

    @property
    def mac(self) -> str:
        """Return the MAC address of the new device."""
        assert isinstance(self._data, dict)
        return cast(str, self._data["mac"])

    @property
    def stored_mac(self) -> str:
        """Return the MAC address of the stored device."""
        assert isinstance(self._data, dict)
        return cast(str, self._data["stored_mac"])

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["migrate", "manual"],
            description_placeholders=self._async_get_placeholders(),
        )

    async def async_step_migrate(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the migrate step of a fix flow."""
        if user_input is None:
            return self.async_show_form(
                step_id="migrate",
                data_schema=vol.Schema({}),
                description_placeholders=self._async_get_placeholders(),
            )
        entry_id = self.entry_id
        await async_replace_device(self.hass, entry_id, self.stored_mac, self.mac)
        self.hass.config_entries.async_schedule_reload(entry_id)
        return self.async_create_entry(data={})

    async def async_step_manual(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the manual step of a fix flow."""
        if user_input is None:
            return self.async_show_form(
                step_id="manual",
                data_schema=vol.Schema({}),
                description_placeholders=self._async_get_placeholders(),
            )
        self.hass.config_entries.async_schedule_reload(self.entry_id)
        return self.async_create_entry(data={})


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    if issue_id.startswith("device_conflict"):
        return DeviceConflictRepair(data)
    # If ESPHome adds confirm-only repairs in the future, this should be changed
    # to return a ConfirmRepairFlow instead of raising a ValueError
    raise ValueError(f"unknown repair {issue_id}")
