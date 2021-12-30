"""Config flow to configure ZWaveMe integration."""

import logging

from url_normalize import url_normalize
import voluptuous as vol

from homeassistant import config_entries

from . import get_uuid
from .const import CONF_TOKEN, CONF_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class ZWaveMeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """ZWaveMe integration config flow."""

    def __init__(self):
        """Initialize flow."""
        self.url = None
        self.token = None
        self.uuid = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user or started with zeroconf."""
        errors = {}
        if self.url is None:
            schema = vol.Schema(
                {
                    vol.Required(CONF_URL): str,
                    vol.Required(CONF_TOKEN): str,
                }
            )
        else:
            schema = vol.Schema(
                {
                    vol.Required(CONF_TOKEN): str,
                }
            )

        if user_input is not None:
            if self.url is None:
                self.url = user_input["url"]

            self.token = user_input["token"]
            if not self.url.startswith(("ws://", "wss://")):
                self.url = f"ws://{self.url}"
            self.url = url_normalize(self.url, default_scheme="ws")
            if "://" not in self.url:
                errors[CONF_URL] = "invalid_url"
                self.url = None
                return self.async_show_form(
                    step_id="user",
                    data_schema=schema,
                    errors=errors,
                )
            if self.uuid is None:
                self.uuid = await get_uuid(self.url, self.token)
                if self.uuid is not None:
                    await self.async_set_unique_id(self.uuid + self.url)
                    self._abort_if_unique_id_configured()
                errors[CONF_URL] = "could_not_retrieve_data"
            return self.async_create_entry(
                title=self.url,
                data={"url": self.url, "token": self.token},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_zeroconf(self, discovery_info):
        """
        Handle a discovered Z-Wave accessory - get url to pass into user step.

        This flow is triggered by the discovery component.
        """
        self.url = discovery_info.host
        self.uuid = await get_uuid(self.url, self.token)
        if self.uuid is not None:
            await self.async_set_unique_id(self.uuid + self.url)
            self._abort_if_unique_id_configured()

        return await self.async_step_user()
