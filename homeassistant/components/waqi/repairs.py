"""Repairs for the World Air Quality Index (WAQI) integration."""

from typing import TYPE_CHECKING

import probatio

from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.core import HomeAssistant


class StationNotFoundRepairFlow(RepairsFlow):
    """Handler to remove a measuring station that can no longer be found."""

    def __init__(self, entry_id: str, subentry_id: str, name: str) -> None:
        """Initialize the flow."""
        self._entry_id = entry_id
        self._subentry_id = subentry_id
        self._name = name

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            entry = self.hass.config_entries.async_get_entry(self._entry_id)
            if TYPE_CHECKING:
                assert entry is not None
            self.hass.config_entries.async_remove_subentry(entry, self._subentry_id)
            return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="confirm",
            data_schema=probatio.Schema({}),
            description_placeholders={"name": self._name},
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str] | None,
) -> RepairsFlow:
    """Create flow."""
    if TYPE_CHECKING:
        assert data is not None
    return StationNotFoundRepairFlow(
        entry_id=data["entry_id"],
        subentry_id=data["subentry_id"],
        name=data["name"],
    )
