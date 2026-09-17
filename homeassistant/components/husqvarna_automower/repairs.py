"""Repairs for the Husqvarna Automower integration."""

from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .const import DOMAIN

ISSUE_ID_PREFIX = "migrate_could_not_auth_"


class MigrationRepairFlow(RepairsFlow):
    """Handle retrying a failed config entry migration."""

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm(user_input)

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Retry the migration after confirmation."""
        if user_input is None:
            return self.async_show_form(step_id="confirm", data_schema={})

        entry_id = self.data.get("entry_id") if self.data else None
        if not isinstance(entry_id, str):
            return self.async_abort(reason="retry_failed")

        await self.hass.config_entries.async_retry_migration(entry_id)
        entry = self.hass.config_entries.async_get_known_entry(entry_id)
        if entry.state is ConfigEntryState.MIGRATION_ERROR:
            return self.async_abort(reason="retry_failed")

        return self.async_create_entry(data={})


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create a repair flow."""
    if issue_id.startswith(ISSUE_ID_PREFIX):
        return MigrationRepairFlow()

    raise ValueError(f"Unknown issue ID: {issue_id}")
