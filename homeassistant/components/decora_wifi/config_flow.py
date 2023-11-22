"""Will write later."""

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_DEVICES, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class DecoreWifiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Will write later."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Will write later."""

        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input["username"]
            pwd = user_input["password"]

            await self.async_set_unique_id(username.lower())
            self._abort_if_unique_id_configured()

            # Abode example
            # existing_entry = await self.async_set_unique_id(self._username)

            # if existing_entry:
            #     self.hass.config_entries.async_update_entry(
            #         existing_entry, data=config_data
            #     )
            #     # Reload the Abode config entry otherwise devices will remain unavailable
            #     self.hass.async_create_task(
            #         self.hass.config_entries.async_reload(existing_entry.entry_id)
            #     )

            return self.async_create_entry(
                title=username,
                data={
                    CONF_USERNAME: username,
                    CONF_PASSWORD: pwd,
                    CONF_DEVICES: [],
                },
            )

        data_schema = {
            vol.Required("username"): str,
            vol.Required("password"): str,
        }
        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(data_schema), errors=errors
        )
