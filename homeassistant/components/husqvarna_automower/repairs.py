"""Repairs for the Husqvarna Automower integration."""

import probatio

from homeassistant.components.repairs import (
    ConfirmRepairFlow,
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

ISSUE_ID_PREFIX = "migrate_could_not_auth_"


class MigrationRepairFlow(RepairsFlow):
    """Handle retrying a failed config entry migration."""

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm(user_input)

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Retry the migration after confirmation."""
        if user_input is not None:
            entry_id = self.data.get("entry_id") if self.data else None
            if isinstance(entry_id, str):
                await self.hass.config_entries.async_retry_migration(entry_id)
                entry = self.hass.config_entries.async_get_known_entry(entry_id)
                if entry.state is not ConfigEntryState.MIGRATION_ERROR:
                    return self.async_create_entry(data={})

        return self.async_show_form(step_id="confirm", data_schema=probatio.Schema({}))


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create a repair flow."""
    if issue_id.startswith(ISSUE_ID_PREFIX):
        return MigrationRepairFlow()

    return ConfirmRepairFlow()
