"""Config flow for TechnoVE."""

from typing import Any

from technove import Station as TechnoVEStation, TechnoVE, TechnoVEConnectionError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN


class TechnoVEConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TechnoVE."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}
        if user_input is not None:
            try:
                station = await self._async_get_station(user_input[CONF_HOST])
            except TechnoVEConnectionError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(station.info.mac_address)
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: user_input[CONF_HOST]}
                )
                return self.async_create_entry(
                    title=station.info.name,
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    async def _async_get_station(self, host: str) -> TechnoVEStation:
        """Get information from a TechnoVE station."""
        api = TechnoVE(host, session=async_get_clientsession(self.hass))
        return await api.update()
