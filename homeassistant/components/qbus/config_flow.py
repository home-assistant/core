"""Config flow for Qbus."""

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult

from .const import CONF_SERIAL, DOMAIN


class QbusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""

        if user_input is not None:
            serial = user_input.get(CONF_SERIAL)
            valid = True

            if valid:
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=f"CTD {serial}", data=user_input)

        config_schema = {vol.Required(CONF_SERIAL): str}

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(config_schema)
        )
