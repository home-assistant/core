"""Provide repairs for the backup integration."""

from __future__ import annotations

from typing import cast

from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import issue_registry as ir

from .const import DATA_MANAGER, DOMAIN

AUTOMATIC_BACKUP_AGENTS_NOT_LOADED_ISSUE_ID = "automatic_backup_agents_not_loaded"


@callback
def create_automatic_backup_agents_not_loaded_issue(
    hass: HomeAssistant, agent_id: str
) -> None:
    """Create automatic backup agents not loaded issue."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"{AUTOMATIC_BACKUP_AGENTS_NOT_LOADED_ISSUE_ID}_{agent_id}",
        data={"agent_id": agent_id},
        is_fixable=True,
        learn_more_url="homeassistant://config/backup",
        severity=ir.IssueSeverity.WARNING,
        translation_key="automatic_backup_agents_not_loaded",
        translation_placeholders={"agent_id": agent_id},
    )


@callback
def delete_automatic_backup_agents_not_loaded_issue(
    hass: HomeAssistant, agent_id: str
) -> None:
    """Delete automatic backup agents not loaded issue."""
    ir.async_delete_issue(
        hass, DOMAIN, f"{AUTOMATIC_BACKUP_AGENTS_NOT_LOADED_ISSUE_ID}_{agent_id}"
    )


class AutomaticBackupAgentsNotLoaded(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, agent_id: str) -> None:
        """Initialize."""
        self._agent_id = agent_id

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            manager = self.hass.data[DATA_MANAGER]
            configured_agent_ids = set(manager.config.data.create_backup.agent_ids)
            configured_agent_ids.discard(self._agent_id)
            await manager.config.update(
                create_backup={"agent_ids": list(configured_agent_ids)}
            )

            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="confirm", description_placeholders={"agent_id": self._agent_id}
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    if AUTOMATIC_BACKUP_AGENTS_NOT_LOADED_ISSUE_ID in issue_id:
        assert data
        agent_id = cast(str, data["agent_id"])
        return AutomaticBackupAgentsNotLoaded(agent_id=agent_id)
    return ConfirmRepairFlow()
