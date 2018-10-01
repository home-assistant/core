"""Config flow for ZHA."""
from collections import OrderedDict

import voluptuous as vol

from homeassistant import config_entries

from .const import (
    DOMAIN, CONF_BAUDRATE, CONF_DATABASE, CONF_RADIO_TYPE, CONF_USB_PATH
)


@config_entries.HANDLERS.register(DOMAIN)
class ZhaFlowHandler(config_entries.ConfigFlow):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason='single_instance_allowed')

        return await self.async_step_init()

    async def async_step_init(self, user_input=None):
        """Handle a zha config flow start."""
        if self._async_current_entries():
            return self.async_abort(reason='single_instance_allowed')

        errors = {}

        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_USB_PATH], data=user_input)

        fields = OrderedDict()
        fields[vol.Required(CONF_DATABASE)] = str
        fields[vol.Required(CONF_USB_PATH)] = str
        fields[vol.Optional(CONF_RADIO_TYPE, default='ezsp')] = str
        fields[vol.Optional(CONF_BAUDRATE, default=57600)] = vol.Coerce(int)

        return self.async_show_form(
            step_id='init', data_schema=vol.Schema(fields), errors=errors
        )

    async def async_step_import(self, import_info):
        """Handle a zha config import."""
        if self._async_current_entries():
            return self.async_abort(reason='single_instance_allowed')

        import_info[CONF_RADIO_TYPE] = import_info[CONF_RADIO_TYPE].name
        return self.async_create_entry(
            title=import_info[CONF_USB_PATH],
            data=import_info
        )
