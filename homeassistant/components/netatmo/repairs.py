"""Repairs for the Netatmo integration."""

from typing import TYPE_CHECKING, Any

from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .device import async_hide_schedule_select_instead


class LegacyClimateDeviceRepairFlow(RepairsFlow):
    """Enable a home that was disabled to hide its schedule select."""

    def __init__(self, device_id: str, entity_id: str) -> None:
        """Initialize the repair flow."""
        self._device_id = device_id
        self._entity_id = entity_id

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of the repair flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Enable the home and hide its schedule select once confirmed."""
        if (device := dr.async_get(self.hass).async_get(self._device_id)) is None:
            return self.async_abort(reason="home_removed")

        if user_input is not None:
            # The id outlives a rename of the entity, which the user may have done
            entity = er.async_get(self.hass).async_get(self._entity_id)
            async_hide_schedule_select_instead(
                self.hass, device.id, entity.entity_id if entity else None
            )
            return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "home_name": device.name_by_user or device.name or ""
            },
        )


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, Any] | None
) -> RepairsFlow:
    """Create the repair flow for an issue."""
    if TYPE_CHECKING:
        # The only fixable issue is persistent and always carries its data
        assert data is not None
    return LegacyClimateDeviceRepairFlow(data["device_id"], data["entity_id"])
