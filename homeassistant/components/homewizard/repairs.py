"""Repairs platform for the HomeWizard integration."""
from __future__ import annotations

from homewizard_energy.errors import DisabledError
import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant


class HomeWizardEnergyEnableApi(RepairsFlow):
    """Handler for an issue fixing flow."""

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            try:
                # Try to reach the API here, (via coordinator or directly)
                pass  # await coordinator.api.device()
            except DisabledError:
                return self.async_abort(
                    reason="api_not_enabled"
                )  # Gives a blank "All OK"

            return self.async_create_entry(title="Fixed issue", data={})

        return self.async_show_form(step_id="confirm", data_schema=vol.Schema({}))


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str
) -> HomeWizardEnergyEnableApi:
    """Create flow."""
    return HomeWizardEnergyEnableApi()
