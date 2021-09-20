"""Config flow to configure the Twinkly integration."""

import asyncio
import logging

from aiohttp import ClientError
import twinkly_client
from voluptuous import Required, Schema

from homeassistant import config_entries
from homeassistant.const import CONF_HOST

from .const import (
    CONF_ENTRY_HOST,
    CONF_ENTRY_ID,
    CONF_ENTRY_MODEL,
    CONF_ENTRY_NAME,
    DEV_ID,
    DEV_MODEL,
    DEV_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class TwinklyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle twinkly config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle config steps."""
        host = user_input[CONF_HOST] if user_input else None

        schema = {Required(CONF_HOST, default=host): str}
        errors = {}

        if host is not None:
            try:
                device_info = await twinkly_client.TwinklyClient(host).get_device_info()

                await self.async_set_unique_id(device_info[DEV_ID])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=device_info[DEV_NAME],
                    data={
                        CONF_ENTRY_HOST: host,
                        CONF_ENTRY_ID: device_info[DEV_ID],
                        CONF_ENTRY_NAME: device_info[DEV_NAME],
                        CONF_ENTRY_MODEL: device_info[DEV_MODEL],
                    },
                )
            except (asyncio.TimeoutError, ClientError) as err:
                _LOGGER.info("Cannot reach Twinkly '%s' (client)", host, exc_info=err)
                errors[CONF_HOST] = "cannot_connect"

        return self.async_show_form(
            step_id="user", data_schema=Schema(schema), errors=errors
        )
