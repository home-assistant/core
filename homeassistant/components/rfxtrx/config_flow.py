"""Config flow for RFXCOM RFXtrx integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_DEVICE,
    CONF_DEVICE_ID,
)
from homeassistant.core import callback
from homeassistant.helpers.device_registry import (
    async_entries_for_config_entry,
    async_get_registry,
)

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
            return None

        device_registry = await async_get_registry(self.hass)
        device_entries = async_entries_for_config_entry(
            device_registry, self.config_entry.entry_id
        )

        devices = {
            entry.id: entry.name_by_user if entry.name_by_user else entry.name
            for entry in device_entries
        }

        options = {
            vol.Optional(CONF_DEBUG): bool,
            vol.Optional(CONF_AUTOMATIC_ADD): bool,
            vol.Optional(CONF_DEVICE_ID): str,
            vol.Optional(CONF_DEVICE): vol.In(devices),
        }

        return self.async_show_form(
            step_id="prompt_options", data_schema=vol.Schema(options)
        )

    async def async_step_set_device_options(self, user_input=None):
        """Manage device options."""
        if user_input is not None:
            return None

        data_scheme = {
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
