"""Repair issues for the Actron Air Neo integration."""

from __future__ import annotations

from homeassistant.components.repairs import RepairsFlow
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN


class StaleAuthRepairFlow(RepairsFlow):
    """Handler for authentication issue fixing flow."""

    def __init__(self, entry_id: str) -> None:
        """Initialize."""
        super().__init__()
        self.entry_id = entry_id

    async def async_step_init(self, user_input=None):
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None):
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            # Trigger reauthentication for the config entry
            try:
                await self.hass.config_entries.async_reload(self.entry_id)
                return self.async_create_entry(title="", data={})
            except HomeAssistantError:
                return self.async_abort(reason="reauth_failed")

        return self.async_show_form(
            step_id="confirm",
            data_schema=None,
            description_placeholders={"config_entry_id": self.entry_id},
        )


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, str]
) -> RepairsFlow:
    """Create flow."""
    if data.get("domain") != DOMAIN:
        raise ValueError(f"Incorrect domain {data.get('domain')}")

    issue_type = data.get("issue_type")
    if issue_type == "stale_auth":
        return StaleAuthRepairFlow(data["entry_id"])

    raise ValueError(f"Unknown issue type {issue_type}")


async def async_register_stale_auth_issue(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Register an issue for stale authentication."""
    ir.async_create_issue(
        hass,
        domain=DOMAIN,
        issue_id=f"stale_auth_{entry.entry_id}",
        is_fixable=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key="stale_auth",
        translation_placeholders={"name": entry.title},
        data={"domain": DOMAIN, "issue_type": "stale_auth", "entry_id": entry.entry_id},
    )
