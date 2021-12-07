"""Config flow to configure ZWaveMe integration."""

import logging
from dataclasses import asdict
import voluptuous as vol
from homeassistant import config_entries

from .const import CONF_URL, CONF_TOKEN, DOMAIN

_LOGGER = logging.getLogger(__name__)


class ZWaveMeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """ZWaveMe integration config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize flow."""
        self.url = vol.UNDEFINED
        self.token = vol.UNDEFINED

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            if "host" in user_input:
                self.url = user_input["host"]

            else:
                if "url" in user_input:
                    self.url = user_input["url"]
                else:
                    user_input["url"] = self.url
                self.token = user_input["token"]

                if not user_input["url"].startswith("ws://") and not user_input[
                    "url"
                ].startswith("wss://"):
                    user_input["url"] = "ws://" + user_input["url"] + ":8083"
                    self.url = "ws://" + self.url + ":8083"

                await self.async_set_unique_id(DOMAIN + self.url)
                return self.async_create_entry(
                    title=self.url,
                    data=user_input,
                    description_placeholders={
                        "docs_url": "https://zwayhomeautomation.docs.apiary.io/"
                    },
                )
        if self.url != vol.UNDEFINED:
            schema = vol.Schema(
                {
                    vol.Required(CONF_TOKEN): str,
                }
            )
        else:
            schema = vol.Schema(
                {
                    vol.Required(CONF_URL): str,
                    vol.Required(CONF_TOKEN): str,
                }
            )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            description_placeholders={
                "docs_url": "https://zwayhomeautomation.docs.apiary.io/"
            },
            errors=errors,
        )

    async def async_step_zeroconf(self, discovery_info):
        """Handle a discovered Z-Wave accessory.

        This flow is triggered by the discovery component.
        """
        if isinstance(discovery_info, dict):
            return await self.async_step_user(discovery_info)
        else:
            return await self.async_step_user(asdict(discovery_info))
