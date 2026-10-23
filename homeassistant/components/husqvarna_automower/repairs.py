"""Repairs for the Husqvarna Automower integration."""

import probatio

from homeassistant.components.repairs import (
    ConfirmRepairFlow,
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import MIGRATION_AUTH_ISSUE_ID_PREFIX


class MigrationRepairFlow(RepairsFlow):
    """Reauthenticate and retry a failed config entry migration."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the repair flow."""
        self.entry = entry

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of the repair flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Start reauthentication after confirmation."""
        if user_input is not None:
            self.entry.async_start_reauth(self.hass)
            return self.async_create_entry(data={})

        return self.async_show_form(step_id="confirm", data_schema=probatio.Schema({}))


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create the repair flow."""
    if data is not None and isinstance(entry_id := data.get("entry_id"), str):
        if issue_id.startswith(MIGRATION_AUTH_ISSUE_ID_PREFIX) and (
            entry := hass.config_entries.async_get_entry(entry_id)
        ):
            return MigrationRepairFlow(entry)

    return ConfirmRepairFlow()
