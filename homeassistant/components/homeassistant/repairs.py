"""Repairs for Home Assistant."""

from __future__ import annotations

from homeassistant import data_entry_flow
from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.core import HomeAssistant


class IntegrationNotFoundFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, data: dict[str, str]) -> None:
        """Initialize."""
        self.description_placeholders: dict[str, str] = {
            "device_name": data["device_name"]
        }

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""
        return self.async_show_menu(
            menu_options=["confirm", "ignore"],
            description_placeholders=self.description_placeholders,
        )


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, str] | None
) -> RepairsFlow:
    """Create flow."""

    if issue_id.split(".")[0] == "integration_not_found":
        assert data
        return IntegrationNotFoundFlow(data)
    return ConfirmRepairFlow()
