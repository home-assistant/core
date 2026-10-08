"""Repairs for the control4 integration."""

import probatio

from homeassistant.components.repairs import (
    ConfirmRepairFlow,
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.const import ATTR_CONFIG_ENTRY_ID, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service import async_get_config_entry

from .const import DOMAIN


class RemoveCustomPollingRepairFlow(RepairsFlow):
    """Handler for custom polling fixing flow."""

    def __init__(self, data: dict[str, str]) -> None:
        """Initialize."""
        self.entry_id = data[ATTR_CONFIG_ENTRY_ID]

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Init repair flow."""

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Confirm repair flow."""
        if user_input is not None:
            entry = async_get_config_entry(self.hass, DOMAIN, self.entry_id)
            options = dict(entry.options)
            options.pop(CONF_SCAN_INTERVAL, None)
            self.hass.config_entries.async_update_entry(
                entry, options=options, minor_version=2
            )

            return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="confirm",
            data_schema=probatio.Schema({}),
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str],
) -> RepairsFlow:
    """Create flow."""
    if issue_id.startswith("user_configurable_polling_removed"):
        return RemoveCustomPollingRepairFlow(data)
    return ConfirmRepairFlow()
