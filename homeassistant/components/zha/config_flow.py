"""Config flow for ZHA."""
import asyncio
from collections import OrderedDict
import os

from bellows.zigbee.application import CONF_PARAM_SRC_RTG
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .core.const import (
    CONF_ADDRESS_TABLE_SIZE,
    CONF_NEIGHBOR_TABLE_SIZE,
    CONF_RADIO_TYPE,
    CONF_SOURCE_ROUTE_TABLE_SIZE,
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
        self.config_entry = config_entry
        self.options = dict(config_entry.options)
        self.radio_specific_options = {
            RadioType.ezsp.name: {
                vol.Optional(
                    CONF_SOURCE_ROUTE_TABLE_SIZE,
                    default=self.config_entry.options.get(
                        CONF_SOURCE_ROUTE_TABLE_SIZE, 8
                    ),
                ): vol.All(int, vol.Range(min=0, max=254)),
                vol.Optional(
                    CONF_ADDRESS_TABLE_SIZE,
                    default=self.config_entry.options.get(CONF_ADDRESS_TABLE_SIZE, 16),
                ): vol.All(int, vol.Range(min=0, max=254)),
                vol.Optional(
                    CONF_NEIGHBOR_TABLE_SIZE,
                    default=self.config_entry.options.get(CONF_NEIGHBOR_TABLE_SIZE, 8),
                ): vol.All(int, vol.Range(min=8, max=16)),
            }
        }

    async def async_step_init(self, user_input=None):
        """Manage the ZHA options."""
        return await self.async_step_zha_network_options()

    async def async_step_zha_network_options(self, user_input=None):
        """Manage the Zigpy configuration options for ZHA."""
        if user_input is not None:
            self.options.update(user_input)
            return self.async_create_entry(title="", data=self.options)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_PARAM_SRC_RTG,
                    default=self.config_entry.options.get(CONF_PARAM_SRC_RTG, False),
                ): bool
            }
        )
        schema = schema.extend(
            self.radio_specific_options.get(
                self.config_entry.data.get(CONF_RADIO_TYPE), {}
            )
        )
        return self.async_show_form(step_id="zha_network_options", data_schema=schema)


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
