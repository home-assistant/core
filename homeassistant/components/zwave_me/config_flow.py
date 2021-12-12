"""Config flow to configure ZWaveMe integration."""

import logging

import voluptuous as vol

from homeassistant import config_entries

from .const import CONF_TOKEN, CONF_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class ZWaveMeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """ZWaveMe integration config flow."""

    def __init__(self):
        """Initialize flow."""
        self.url = vol.UNDEFINED
        self.token = vol.UNDEFINED

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}
        schema = vol.Schema(
            {
                vol.Required(CONF_URL): str,
                vol.Required(CONF_TOKEN): str,
            }
        )

        if user_input is not None:
            if self.url == vol.UNDEFINED:
                self.url = user_input["url"]
            self.token = user_input["token"]

            if not self.url.startswith(("ws://", "wss://")):
                self.url = f"ws://{self.url}:8083"

            await self.async_set_unique_id(DOMAIN + self.url)
            return self.async_create_entry(
                title=self.url,
                data=user_input,
            )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_zeroconf(self, discovery_info):
        """Handle a discovered Z-Wave accessory.

        This flow is triggered by the discovery component.
        """
        errors = {}
        self.url = discovery_info.host
        schema = vol.Schema(
            {
                vol.Required(CONF_TOKEN): str,
            }
        )
        entry = await self.async_set_unique_id(DOMAIN + self.url)
        if entry is None:
            return self.async_show_form(
                step_id="user", data_schema=schema, errors=errors
            )
