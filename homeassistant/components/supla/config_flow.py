"""Config flow to configure zone component."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import callback
from homeassistant.util import slugify

from .const import DOMAIN


@callback
def configured_host(hass):
    """Return a set of the configured hosts."""
    return set(
        (slugify(entry.data[CONF_HOST]))
        for entry in hass.config_entries.async_entries(DOMAIN)
    )


@config_entries.HANDLERS.register(DOMAIN)
class SuplaFlowHandler(config_entries.ConfigFlow):
    """Supla config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize zone configuration flow."""
        pass

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        # if self._async_current_entries():
        #     return self.async_abort(reason='single_instance_allowed')
        return await self.async_step_confirm(user_input)

    async def async_step_confirm(self, user_input=None):
        """Handle a flow start."""
        errors = {}
        if user_input is not None:
            return await self.async_step_init(user_input=None)
        return self.async_show_form(step_id="confirm", errors=errors)

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        errors = {}
        if user_input is not None:
            l_valid = True
            user_input[CONF_HOST]

            if l_valid:
                # change host name
                await self.hass.services.async_call(
                    "ais_ai_service",
                    "say_it",
                    {
                        "text": "Aktualizuje nazwę hosta. Zrestartuj urządzenie żeby zobaczyć zmiany."
                    },
                )

            """Finish config flow"""
            if l_valid:
                # return self.async_create_entry(
                #     title=user_input[CONF_NAME],
                #     data=user_input
                # )
                return self.async_abort(reason="do_the_restart")

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )
