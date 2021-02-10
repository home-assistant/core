"""Config flow for Garages Amsterdam integration."""
import garages_amsterdam
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN  # pylint:disable=unused-import


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Garages Amsterdam."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    _options = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if self._options is None:
            self._options = []
            api_data = await garages_amsterdam.get_garages(
                aiohttp_client.async_get_clientsession(self.hass)
            )
            for garage in sorted(api_data, key=lambda garage: garage.garage_name):
                self._options.append(garage.garage_name)

        if user_input is not None:
            await self.async_set_unique_id(user_input["garage_name"])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input["garage_name"], data=user_input
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required("garage_name"): vol.In(self._options)}
            ),
            errors=errors,
        )
