"""Repairs for the BTHome integration."""

from __future__ import annotations

from typing import Any

from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from . import get_encryption_issue_id
from .const import CONF_BINDKEY, DOMAIN


class EncryptionRemovedRepairFlow(RepairsFlow):
    """Handle the repair flow when encryption is disabled."""

    def __init__(self, entry_id: str, entry_title: str) -> None:
        """Initialize the repair flow."""
        self._entry_id = entry_id
        self._entry_title = entry_title

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the initial step of the repair flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle confirmation, remove the bindkey, and reload the entry."""
        if user_input is not None:
            entry = self.hass.config_entries.async_get_entry(self._entry_id)
            if not entry:
                return self.async_abort(reason="entry_removed")

            new_data = {k: v for k, v in entry.data.items() if k != CONF_BINDKEY}
            self.hass.config_entries.async_update_entry(entry, data=new_data)

            ir.async_delete_issue(
                self.hass, DOMAIN, get_encryption_issue_id(self._entry_id)
            )

            await self.hass.config_entries.async_reload(self._entry_id)

            return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"name": self._entry_title},
        )


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, Any] | None
) -> RepairsFlow:
    """Create the repair flow for removing the encryption key."""
    if not data or "entry_id" not in data:
        raise ValueError("Missing data for repair flow")
    entry_id = data["entry_id"]
    entry = hass.config_entries.async_get_entry(entry_id)
    entry_title = entry.title if entry else "Unknown device"
    return EncryptionRemovedRepairFlow(entry_id, entry_title)
