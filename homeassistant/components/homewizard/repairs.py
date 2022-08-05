"""Repairs platform for the HomeWizard integration."""
from __future__ import annotations

from typing import cast

from homewizard_energy import HomeWizardEnergy
from homewizard_energy.errors import DisabledError
import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_DEVICE_NAME


class HomeWizardEnergyEnableApi(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, hass: HomeAssistant, host: str | None, name: str | None) -> None:
        """Set variabled for repair context."""
        self.host = host
        self.name = name

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
                api = HomeWizardEnergy(
                    self.host, clientsession=async_get_clientsession(self.hass)
                )
                await api.device()
            except DisabledError:
                return self.async_abort(
                    reason="api_not_enabled"
                )  # Gives a blank "All OK"

            return self.async_create_entry(title="Fixed issue", data={})

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={
                CONF_IP_ADDRESS: self.host,
                CONF_DEVICE_NAME: self.name,
            },
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> HomeWizardEnergyEnableApi:
    """Create flow."""

    if data is None:
        data = {}

    return HomeWizardEnergyEnableApi(
        hass,
        cast(str, data.get(CONF_IP_ADDRESS)),
        cast(str, data.get(CONF_DEVICE_NAME)),
    )
