"""Config flow for easyEnergy integration."""

from typing import Any

from easyenergy import EasyEnergy, EasyEnergyConnectionError

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import DOMAIN


class EasyEnergyFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for easyEnergy integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            easyenergy = EasyEnergy(session=async_get_clientsession(self.hass))
            today = dt_util.now().date()
            try:
                await easyenergy.energy_prices(start_date=today, end_date=today)
            except EasyEnergyConnectionError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title="easyEnergy",
                    data={},
                )

        return self.async_show_form(step_id="user", errors=errors)
