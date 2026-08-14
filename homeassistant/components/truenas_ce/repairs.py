"""Repairs for the TrueNAS integration."""

from typing import Any

from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import issue_registry as ir

from .const import (
    CONF_STATISTICS_CLEANUP_IGNORED,
    DOMAIN,
    ISSUE_MIGRATION_ROLLBACK,
    ISSUE_STATISTICS_ORPHANED,
    MIGRATION_RECORDS,
)
from .coordinator import get_truenas_coordinator
from .migration import async_rollback_to_legacy

# Upper bound on ids rendered into the repair dialog. A chain of renames can
# leave dozens behind; the remainder is summarised so the dialog stays readable
# (the full list goes to the debug log during detection).
MAX_LISTED_ORPHANS = 20


def _format_statistic_ids(statistic_ids: list[str]) -> str:
    """Render statistic ids as a Markdown list for the repair dialog."""
    shown = statistic_ids[:MAX_LISTED_ORPHANS]
    lines = [f"- `{statistic_id}`" for statistic_id in shown]
    if remaining := len(statistic_ids) - len(shown):
        # Language-neutral on purpose: placeholder content is not translated.
        lines.append(f"- … (+{remaining})")
    return "\n".join(lines)


class StatisticsCleanupRepairFlow(RepairsFlow):
    """Repair flow for orphaned statistics: delete them or ignore the issue."""

    def __init__(self, entry_id: str) -> None:
        """Remember which config entry this issue belongs to."""
        self._entry_id = entry_id

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show the fix/ignore menu listing the affected statistic ids.

        Metadata-only orphans (no data points left) get their own wording: they
        cannot be found in Developer Tools → Statistics, so pointing the user
        there would send them looking for something that isn't displayed.
        """
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        coordinator = get_truenas_coordinator(entry)
        if coordinator is None:
            orphans: list[str] = []
            with_data = 0
        else:
            # Already sorted by the coordinator; copied so the dialog keeps the
            # snapshot it renders even if the next poll rebuilds the list.
            orphans = list(coordinator.orphaned_statistics)
            with_data = await coordinator.async_count_orphans_with_data()

        return self.async_show_menu(
            step_id="init" if with_data else "init_metadata_only",
            menu_options=["fix", "ignore"],
            description_placeholders={
                "count": str(len(orphans)),
                "with_data": str(with_data),
                "entities": _format_statistic_ids(orphans),
            },
        )

    async def async_step_fix(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Delete the orphaned statistics."""
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        coordinator = get_truenas_coordinator(entry)
        if coordinator is not None:
            await coordinator.async_clear_orphaned_statistics()
        return self.async_create_entry(title="", data={})

    async def async_step_ignore(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Suppress the issue for this config entry."""
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry is not None:
            self.hass.config_entries.async_update_entry(
                entry,
                options={**entry.options, CONF_STATISTICS_CLEANUP_IGNORED: True},
            )
        ir.async_delete_issue(
            self.hass, DOMAIN, f"{ISSUE_STATISTICS_ORPHANED}_{self._entry_id}"
        )
        return self.async_create_entry(title="", data={})


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
    ) -> FlowResult:
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
    ) -> FlowResult:
        """Hand the adopted entities (and history) back to the legacy entry."""
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry is not None:
            # Scheduled as a task because the rollback removes this very config
            # entry; doing it inline would tear down the flow mid-step.
            self.hass.async_create_task(async_rollback_to_legacy(self.hass, entry))
        ir.async_delete_issue(
            self.hass, DOMAIN, f"{ISSUE_MIGRATION_ROLLBACK}_{self._entry_id}"
        )
        return self.async_create_entry(title="", data={})

    async def async_step_ignore(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
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
    entry_id = issue_id.removeprefix(f"{ISSUE_STATISTICS_ORPHANED}_")
    return StatisticsCleanupRepairFlow(entry_id)
