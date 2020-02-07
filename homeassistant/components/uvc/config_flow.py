"""Config flow for ZHA."""
from collections import OrderedDict

import voluptuous as vol

from homeassistant import config_entries

from . import (
    CONF_KEY,
    CONF_NVR,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    DEFAULT_PASSWORD,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DOMAIN,
)


@config_entries.HANDLERS.register(DOMAIN)
class UvcFlowHandler(config_entries.ConfigFlow):
    """Flow handler."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """User step callback."""
        errors = {}

        fields = OrderedDict()
        fields[vol.Required(CONF_NVR)] = str
        fields[vol.Optional(CONF_PORT, default=DEFAULT_PORT)] = int
        fields[vol.Required(CONF_KEY)] = str
        fields[vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD)] = str
        fields[vol.Optional(CONF_SSL, default=DEFAULT_SSL)] = bool

        if user_input is not None:
            return self.__finalize(user_input)

        return self.async_show_form(
            step_id=CONF_NVR, data_schema=vol.Schema(fields), errors=errors
        )

    async def async_step_import(self, import_info):
        """Import callback."""
        return self.__finalize(import_info)

    def __finalize(self, info):
        return self.async_create_entry(
            title=info["nvr"], data={**info, "platform": DOMAIN}
        )
