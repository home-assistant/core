"""Config flow for ZHA."""
import asyncio
from collections import OrderedDict
import os

import voluptuous as vol
from zigpy.config import CONF_DATABASE, CONF_DEVICE, CONF_DEVICE_PATH

from homeassistant import config_entries

from .core.const import (
    CONF_RADIO_TYPE,
    CONTROLLER,
    DEFAULT_DATABASE_NAME,
    DOMAIN,
    RadioType,
)
from .core.registries import RADIO_TYPES


@config_entries.HANDLERS.register(DOMAIN)
class ZhaFlowHandler(config_entries.ConfigFlow):
    """Handle a config flow."""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Handle a zha config flow start."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors = {}

        fields = OrderedDict()
        fields[vol.Required(CONF_DEVICE_PATH)] = str
        fields[vol.Optional(CONF_RADIO_TYPE, default="ezsp")] = vol.In(RadioType.list())

        if user_input is not None:
            database = os.path.join(self.hass.config.config_dir, DEFAULT_DATABASE_NAME)
            test = await check_zigpy_connection(
                user_input[CONF_DEVICE_PATH], user_input[CONF_RADIO_TYPE], database
            )
            if test:
                return self.async_create_entry(
                    title=user_input[CONF_DEVICE_PATH],
                    data={
                        CONF_DEVICE: {CONF_DEVICE_PATH: user_input[CONF_DEVICE_PATH]},
                        CONF_RADIO_TYPE: user_input[CONF_RADIO_TYPE],
                    },
                )
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(fields), errors=errors
        )

    async def async_step_import(self, import_info):
        """Handle a zha config import."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(
            title=import_info[CONF_DEVICE][CONF_DEVICE_PATH], data=import_info
        )


async def check_zigpy_connection(usb_path, radio_type, database_path):
    """Test zigpy radio connection."""
    try:
        controller_application = RADIO_TYPES[radio_type][CONTROLLER]
    except KeyError:
        return False
    try:
        config = controller_application.SCHEMA(
            {CONF_DEVICE: {CONF_DEVICE_PATH: usb_path}, CONF_DATABASE: database_path}
        )
        controller = await asyncio.wait_for(
            controller_application.new(config), timeout=30
        )
        await controller.shutdown()
    except Exception:  # pylint: disable=broad-except
        return False
    return True
