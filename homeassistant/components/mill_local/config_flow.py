"""Adds config flow for Mill integration."""
from mill_local import Mill
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

DATA_SCHEMA = vol.Schema({vol.Required(CONF_IP_ADDRESS): str})


class MillConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Mill integration."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=DATA_SCHEMA,
                errors={},
            )

        ip_address = user_input[CONF_IP_ADDRESS]

        mill_data_connection = Mill(
            ip_address,
            websession=async_get_clientsession(self.hass),
        )

        errors = {}

        if not await mill_data_connection.get_status():
            errors["cannot_connect"] = "cannot_connect"
            return self.async_show_form(
                step_id="user",
                data_schema=DATA_SCHEMA,
                errors=errors,
            )

        await self.async_set_unique_id(ip_address)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=ip_address,
            data={CONF_IP_ADDRESS: ip_address},
        )
