"""Config flow for Vera."""
import re
from typing import List

import pyvera as pv
from requests.exceptions import RequestException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EXCLUDE, CONF_LIGHTS

from .const import CONF_CONTROLLER, DOMAIN

LIST_REGEX = re.compile("[^0-9]+")


def parse_int_list(data: str) -> List[int]:
    """Parse a string into a list of ints."""
    return [int(s) for s in LIST_REGEX.split(data) if len(s) > 0]


class VeraFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Vera config flow."""

    async def async_step_user(self, config: dict = None):
        """Handle user initiated flow."""
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason="already_setup")

        if config:
            new_config = {
                CONF_CONTROLLER: config.get(CONF_CONTROLLER),
                CONF_LIGHTS: parse_int_list(config.get(CONF_LIGHTS, "")),
                CONF_EXCLUDE: parse_int_list(config.get(CONF_EXCLUDE, "")),
            }
            return await self.async_step_finish(new_config)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CONTROLLER): str,
                    vol.Optional(CONF_LIGHTS): str,
                    vol.Optional(CONF_EXCLUDE): str,
                }
            ),
        )

    async def async_step_import(self, config: dict):
        """Handle a flow initialized by import."""
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason="already_setup")

        return await self.async_step_finish(config)

    async def async_step_finish(self, config: dict):
        """Validate and create config entry."""
        base_url = config.get(CONF_CONTROLLER)

        try:
            controller = pv.VeraController(base_url)
            await self.hass.async_add_job(controller.refresh_data)
        except RequestException:
            return self.async_abort(
                reason="cannot_connect", description_placeholders={"base_url": base_url}
            )

        return self.async_create_entry(title=base_url, data=config)
