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

    Scheduled via ``async_create_task`` because the rollback removes this very
    config entry, which would tear down the repair flow mid-step if awaited
    inline. The ``migration_rollback_available`` issue is already deleted by
    the time this runs (see ``MigrationRollbackRepairFlow.async_step_rollback``),
    so a failure here would otherwise only surface as a log entry with no
    UI-visible signal that the rollback didn't actually happen; raising a
    second, non-fixable issue closes that gap.

    Migration-rollback-specific: the broad ``except Exception`` is this
    coroutine's whole purpose (turning an untracked task's crash into a
    logged, actionable message), not a generic error-swallowing helper —
    don't reuse it for other background tasks.
    """
    try:
        await async_rollback_to_legacy(hass, entry)
    except Exception:
        _LOGGER.exception(
            "TrueNAS CE migration rollback failed for entry %s (%s)",
            entry.entry_id,
            entry.title,
        )
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
    """Confirm-gated rollback of the Community-Edition migration.

    Replaces the old one-tap diagnostic button: the user must open the issue and
    deliberately pick "roll back" (or dismiss it), so an accidental click can no
    longer tear the integration down without confirmation.
    """

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

        Only the issue is removed (no permanent suppression): pressing the
        rollback button again re-opens it while the legacy entry still exists.
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

    Each issue id is ``<key>_<entry_id>``; the entry id is parsed back out so the
    flow can act on the right coordinator/config entry.
    """
    if issue_id.startswith(f"{ISSUE_MIGRATION_ROLLBACK}_"):
        entry_id = issue_id.removeprefix(f"{ISSUE_MIGRATION_ROLLBACK}_")
        return MigrationRollbackRepairFlow(entry_id)
    raise ValueError(f"Unknown TrueNAS repair issue id: {issue_id}")
