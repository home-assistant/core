"""Repairs for the TrueNAS CE integration."""

from logging import getLogger
from typing import Any

from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import (
    DOMAIN,
    ISSUE_MIGRATION_ROLLBACK,
    ISSUE_MIGRATION_ROLLBACK_FAILED,
    MIGRATION_RECORDS,
)
from .migration import async_rollback_to_legacy

_LOGGER = getLogger(__name__)


async def _async_rollback_and_log_errors(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Run the legacy rollback, surfacing (not raising) any failure.

    Scheduled as a task because rollback deletes this config entry, which
    would tear down the flow if awaited inline.
    """
    rolled_back = False
    try:
        rolled_back = await async_rollback_to_legacy(hass, entry)
    except Exception:  # broad on purpose: only path to report a crashed task
        _LOGGER.exception(
            "TrueNAS CE migration rollback failed for entry %s (%s)",
            entry.entry_id,
            entry.title,
        )
    if not rolled_back:
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"{ISSUE_MIGRATION_ROLLBACK_FAILED}_{entry.entry_id}",
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key=ISSUE_MIGRATION_ROLLBACK_FAILED,
            translation_placeholders={"name": entry.title},
        )


class MigrationRollbackRepairFlow(RepairsFlow):
    """Confirm-gated rollback of the Community-Edition migration."""

    def __init__(self, entry_id: str) -> None:
        """Remember which config entry this issue belongs to."""
        self._entry_id = entry_id

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Show the rollback/dismiss menu with the adopted-entity count."""
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        count = len(entry.data.get(MIGRATION_RECORDS, [])) if entry else 0
        return self.async_show_menu(
            step_id="init",
            menu_options=["rollback", "ignore"],
            description_placeholders={"count": str(count)},
        )

    async def async_step_rollback(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Hand the adopted entities (and history) back to the legacy entry."""
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry is not None:
            self.hass.async_create_task(
                _async_rollback_and_log_errors(self.hass, entry)
            )
        ir.async_delete_issue(
            self.hass, DOMAIN, f"{ISSUE_MIGRATION_ROLLBACK}_{self._entry_id}"
        )
        return self.async_create_entry(title="", data={})

    async def async_step_ignore(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Keep TrueNAS CE and close the dialog.

        No permanent suppression: rollback re-opens this issue on demand.
        """
        ir.async_delete_issue(
            self.hass, DOMAIN, f"{ISSUE_MIGRATION_ROLLBACK}_{self._entry_id}"
        )
        return self.async_create_entry(title="", data={})


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, Any] | None,
) -> RepairsFlow:
    """Create the fix flow matching the issue id.

    Issue ids are ``<key>_<entry_id>``; the entry id is parsed back out here.
    """
    if issue_id.startswith(f"{ISSUE_MIGRATION_ROLLBACK}_"):
        entry_id = issue_id.removeprefix(f"{ISSUE_MIGRATION_ROLLBACK}_")
        return MigrationRollbackRepairFlow(entry_id)
    raise ValueError(f"Unknown TrueNAS repair issue id: {issue_id}")
