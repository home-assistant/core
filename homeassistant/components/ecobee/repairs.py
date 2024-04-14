"""Repairs support for Ecobee."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant import data_entry_flow
from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_MIGRATE_NOTIFY


class NotifyMigration(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize repair flow."""
        self.entry = entry
        super().__init__()

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
            new_options = dict(self.entry.options or {})
            new_options[CONF_MIGRATE_NOTIFY] = 1
            self.hass.config_entries.async_update_entry(self.entry, options=new_options)
            return self.async_create_entry(data={})

        return self.async_show_menu(menu_options=["confirm", "ignore"])

    async def async_step_ignore(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the ignore step of a fix flow."""
        return self.async_abort(reason="issue_ignored")


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    if TYPE_CHECKING:
        assert data is not None
        assert isinstance(data["entry_id"], str)

    entry = hass.config_entries.async_get_entry(data["entry_id"])
    if TYPE_CHECKING:
        assert entry is not None

    if issue_id == "migrate_notify":
        return NotifyMigration(entry)

    return ConfirmRepairFlow()
