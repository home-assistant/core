"""Repairs for the IoTaWatt integration."""

import probatio

from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.core import HomeAssistant

from .const import CONF_LEGACY_ENERGY


class LegacyEnergyRepairFlow(RepairsFlow):
    """Handler to switch an entry to the lifetime energy sensors."""

    def __init__(self, entry_id: str) -> None:
        """Initialize."""
        self._entry_id = entry_id

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the confirm step of a fix flow."""
        # The entry can be removed while the flow is open.
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry is None:
            return self.async_abort(reason="entry_removed")

        if user_input is not None:
            self.hass.config_entries.async_update_entry(
                entry,
                options={**entry.options, CONF_LEGACY_ENERGY: False},
            )
            self.hass.config_entries.async_schedule_reload(entry.entry_id)
            return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="confirm",
            data_schema=probatio.Schema({}),
            description_placeholders={"name": entry.title},
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create a fix flow."""
    assert data
    return LegacyEnergyRepairFlow(str(data["entry_id"]))
