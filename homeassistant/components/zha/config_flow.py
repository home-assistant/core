"""Config flow for ZHA."""
import asyncio
from collections import OrderedDict
import copy
import os

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .core.const import (
    CONF_ENABLE_SOURCE_ROUTING,
    CONF_RADIO_TYPE,
    CONF_USB_PATH,
    CONTROLLER,
    DEFAULT_BAUDRATE,
    DEFAULT_DATABASE_NAME,
    DOMAIN,
    ZHA_GW_RADIO,
    RadioType,
)
from .core.registries import RADIO_TYPES


@config_entries.HANDLERS.register(DOMAIN)
class ZhaFlowHandler(config_entries.ConfigFlow):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return ZHAOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle a zha config flow start."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors = {}

        fields = OrderedDict()
        fields[vol.Required(CONF_USB_PATH)] = str
        fields[vol.Optional(CONF_RADIO_TYPE, default="ezsp")] = vol.In(RadioType.list())

        if user_input is not None:
            database = os.path.join(self.hass.config.config_dir, DEFAULT_DATABASE_NAME)
            test = await check_zigpy_connection(
                user_input[CONF_USB_PATH], user_input[CONF_RADIO_TYPE], database
            )
            if test:
                return self.async_create_entry(
                    title=user_input[CONF_USB_PATH], data=user_input
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
            title=import_info[CONF_USB_PATH], data=import_info
        )


class ZHAOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle ZHA options."""

    def __init__(self, config_entry):
        """Initialize ZHA options flow."""
        self.options = copy.deepcopy(config_entry.options)
        self.options[CONF_ENABLE_SOURCE_ROUTING] = config_entry.options.get(
            CONF_ENABLE_SOURCE_ROUTING, False
        )

    async def async_step_init(self, user_input=None):
        """Manage the ZHA options."""
        return await self.async_step_zha_network_options()

    async def async_step_zha_network_options(self, user_input=None):
        """Manage the Zigpy configuration options for ZHA."""
        if user_input is not None:
            self.options[CONF_ENABLE_SOURCE_ROUTING] = user_input[
                CONF_ENABLE_SOURCE_ROUTING
            ]
            return self.async_create_entry(title="", data=self.options)

        return self.async_show_form(
            step_id="zha_network_options",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ENABLE_SOURCE_ROUTING,
                        default=self.options[CONF_ENABLE_SOURCE_ROUTING],
                    ): bool
                }
            ),
        )


async def check_zigpy_connection(usb_path, radio_type, database_path):
    """Test zigpy radio connection."""
    try:
        radio = RADIO_TYPES[radio_type][ZHA_GW_RADIO]()
        controller_application = RADIO_TYPES[radio_type][CONTROLLER]
    except KeyError:
        return False
    try:
        await radio.connect(usb_path, DEFAULT_BAUDRATE)
        controller = controller_application(radio, database_path)
        await asyncio.wait_for(controller.startup(auto_form=True), timeout=30)
        await controller.shutdown()
    except Exception:  # pylint: disable=broad-except
        return False
    return True
