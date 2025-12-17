"""Config flow for OpenEVSE integration."""

import openevsewifi
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST

from .const import DOMAIN


class OpenEVSEConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """OpenEVSE config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    async def check_status(self, host: str) -> bool:
        """Check if we can connect to the OpenEVSE charger."""

        try:
            charger = openevsewifi.Charger(host)
            result = await self.hass.async_add_executor_job(charger.getStatus)
        except AttributeError:
            return False
        else:
            return result is not None

    async def async_step_user(self, user_input=None) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_HOST])
            self._abort_if_unique_id_configured()

            if not await self.check_status(user_input[CONF_HOST]):
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
                    errors={CONF_HOST: "cannot_connect"},
                )

            return self.async_create_entry(
                title=f"OpenEVSE {user_input[CONF_HOST]}",
                data={
                    CONF_HOST: user_input[CONF_HOST],
                },
            )
        return self.async_show_form(
            step_id="user", data_schema=vol.Schema({vol.Required(CONF_HOST): str})
        )
