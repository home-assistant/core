"""Repair flows for the Synology DSM integration."""

from __future__ import annotations

from contextlib import suppress
import logging
from typing import cast

from synology_dsm.api.file_station.models import SynoFileSharedFolder
import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_BACKUP_PATH,
    CONF_BACKUP_SHARE,
    DOMAIN,
    ISSUE_MISSING_BACKUP_SETUP,
    SYNOLOGY_CONNECTION_EXCEPTIONS,
)
from .coordinator import SynologyDSMConfigEntry

LOGGER = logging.getLogger(__name__)


class MissingBackupSetupRepairFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, entry: SynologyDSMConfigEntry, issue_id: str) -> None:
        """Create flow."""
        self.entry = entry
        self.issue_id = issue_id
        super().__init__()

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""

        return self.async_show_menu(
            menu_options=["confirm", "ignore"],
            description_placeholders={
                "docs_url": "https://www.home-assistant.io/integrations/synology_dsm/#backup-location"
            },
        )

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""

        syno_data = self.entry.runtime_data

        if user_input is not None:
            self.hass.config_entries.async_update_entry(
                self.entry, options={**dict(self.entry.options), **user_input}
            )
            return self.async_create_entry(data={})

        shares: list[SynoFileSharedFolder] | None = None
        if syno_data.api.file_station:
            with suppress(*SYNOLOGY_CONNECTION_EXCEPTIONS):
                shares = await syno_data.api.file_station.get_shared_folders(
                    only_writable=True
                )

        if not shares:
            return self.async_abort(reason="no_shares")

        return self.async_show_form(
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_BACKUP_SHARE,
                        default=self.entry.options[CONF_BACKUP_SHARE],
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=s.path, label=s.name)
                                for s in shares
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        ),
                    ),
                    vol.Required(
                        CONF_BACKUP_PATH,
                        default=self.entry.options[CONF_BACKUP_PATH],
                    ): str,
                }
            ),
        )

    async def async_step_ignore(
        self, _: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        ir.async_ignore_issue(self.hass, DOMAIN, self.issue_id, True)
        return self.async_abort(reason="ignored")


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    entry = None
    if data and (entry_id := data.get("entry_id")):
        entry_id = cast(str, entry_id)
        entry = hass.config_entries.async_get_entry(entry_id)

    if entry and issue_id.startswith(ISSUE_MISSING_BACKUP_SETUP):
        return MissingBackupSetupRepairFlow(entry, issue_id)

    return ConfirmRepairFlow()
