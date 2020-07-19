"""Config flow for RFXCOM RFXtrx integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_COMMAND_OFF, CONF_COMMAND_ON
from homeassistant.core import callback

from . import DOMAIN
from .const import (
    CONF_AUTOMATIC_ADD,
    CONF_DATA_BITS,
    CONF_DEBUG,
    CONF_FIRE_EVENT,
    CONF_OFF_DELAY,
    CONF_SIGNAL_REPETITIONS,
)

_LOGGER = logging.getLogger(__name__)


class OptionsFlow(config_entries.OptionsFlow):
    """Handle Rfxtrx options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize vizio options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_prompt_options()

    async def async_step_prompt_options(self, user_input=None):
        """Prompt for options."""
        if user_input is not None:
            if user_input["selected_option"] == "Add device by id":
                return await self.async_step_device_by_id()
            if user_input["selected_option"] == "Configure device options":
                return await self.async_step_select_device_conf()

        options = ["Add device by id", "Configure device options"]

        options_scheme = {
            vol.Optional(CONF_DEBUG): bool,
            vol.Optional(CONF_AUTOMATIC_ADD): bool,
            vol.Optional("selected_option"): vol.In(options),
        }

        return self.async_show_form(
            step_id="prompt_options", data_schema=vol.Schema(options_scheme)
        )

    async def async_step_device_by_id(self, user_input=None):
        """Prompt for device id."""
        if user_input is not None:
            return await self.async_step_set_device_options()

        data_scheme = {
            vol.Required("device_id"): int,
        }

        return self.async_show_form(
            step_id="device_by_id", data_schema=vol.Schema(data_scheme)
        )

    async def async_step_select_device_conf(self, user_input=None):
        """Select device from list."""
        if user_input is not None:
            return await self.async_step_set_device_options()

        dummy_device_list = ["test1", "test2", "test3"]

        data_scheme = {
            vol.Optional("configured_devices"): vol.In(dummy_device_list),
        }

        return self.async_show_form(
            step_id="select_device_conf", data_schema=vol.Schema(data_scheme)
        )

    async def async_step_set_device_options(self, user_input=None):
        """Manage device options."""
        if user_input is not None:
            return None

        device_class = ["light", "power", "window"]

        data_scheme = {
            vol.Optional("device_class"): vol.In(device_class),
            vol.Optional(CONF_FIRE_EVENT): bool,
            vol.Optional(CONF_OFF_DELAY): int,
            vol.Optional(CONF_DATA_BITS): int,
            vol.Optional(CONF_COMMAND_ON): int,
            vol.Optional(CONF_COMMAND_OFF): int,
            vol.Optional(CONF_SIGNAL_REPETITIONS): int,
        }

        return self.async_show_form(
            step_id="set_device_options", data_schema=vol.Schema(data_scheme)
        )


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RFXCOM RFXtrx."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_import(self, import_config=None):
        """Handle the initial step."""
        entry = await self.async_set_unique_id(DOMAIN)
        if entry and import_config.items() != entry.data.items():
            self.hass.config_entries.async_update_entry(entry, data=import_config)
            return self.async_abort(reason="already_configured")
        return self.async_create_entry(title="RFXTRX", data=import_config)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlow(config_entry)
