"""Config flow for ZHA."""
from collections import OrderedDict

import voluptuous as vol

from homeassistant import config_entries

from . import DOMAIN


@config_entries.HANDLERS.register(DOMAIN)
class UvcFlowHandler(config_entries.ConfigFlow):
    """Flow handler."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """User step callback."""
        errors = {}

        fields = OrderedDict()
        fields[vol.Required("nvr")] = str
        fields[vol.Optional("port", default=7080)] = int
        fields[vol.Required("key")] = str
        fields[vol.Optional("password", default="ubnt")] = str
        fields[vol.Optional("ssl", default=False)] = bool

        if user_input is not None:
            self.handler = "camera"
            return self.__finalize(user_input)

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(fields), errors=errors
        )

    async def async_step_import(self, import_info):
        """Import callback."""
        return self.__finalize(import_info)

    def __finalize(self, info):
        self.handler = "camera"  # is later used to specify domain
        return self.async_create_entry(
            title=info["nvr"], data={**info, "platform": DOMAIN}
        )
