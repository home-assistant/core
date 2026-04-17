"""Repairs for the Home Assistant Hardware integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.repairs import RepairsFlow
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

ISSUE_MULTI_PAN_MIGRATION = "multi_pan_migration"


@callback
def _multi_pan_issue_id(config_entry: ConfigEntry) -> str:
    """Return the issue id for the multi-PAN migration issue of an entry."""
    return f"{ISSUE_MULTI_PAN_MIGRATION}_{config_entry.entry_id}"


@callback
def async_create_multi_pan_migration_issue(
    hass: HomeAssistant,
    domain: str,
    config_entry: ConfigEntry,
) -> None:
    """Create a repair issue to guide migration away from Multi-PAN."""
    ir.async_create_issue(
        hass,
        domain=domain,
        issue_id=_multi_pan_issue_id(config_entry),
        is_fixable=True,
        is_persistent=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_MULTI_PAN_MIGRATION,
        translation_placeholders={"hardware_name": config_entry.title},
        data={"entry_id": config_entry.entry_id},
    )


@callback
def async_delete_multi_pan_migration_issue(
    hass: HomeAssistant,
    domain: str,
    config_entry: ConfigEntry,
) -> None:
    """Delete the multi-PAN migration repair issue for this entry."""
    ir.async_delete_issue(hass, domain, _multi_pan_issue_id(config_entry))


class MultiPanMigrationRepairFlow(RepairsFlow):
    """Reuse the multi-PAN options flow uninstall steps as a repair flow.

    Subclass this together with the hardware-specific
    ``MultiPanOptionsFlowHandler`` in each hardware integration's repairs
    module.

    The repair flow runs in the repairs flow manager where ``self.handler``
    is the integration domain rather than the hardware config entry id, so
    the ``config_entry`` accessor of ``OptionsFlow`` must be overridden.
    """

    _repair_config_entry: ConfigEntry

    @property
    def config_entry(self) -> ConfigEntry:
        """Return the hardware config entry to migrate."""
        return self._repair_config_entry

    async def _async_step_start_migration(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Jump straight into the uninstall step of the migration flow."""
        return await self.async_step_uninstall_addon(user_input)  # type: ignore[attr-defined, no-any-return]
