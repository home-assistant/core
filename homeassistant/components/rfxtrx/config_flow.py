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
    CONF_DEVICES,
)
from homeassistant.core import callback
from homeassistant.helpers.device_registry import (
    async_entries_for_config_entry,
    async_get_registry,
)

from . import DOMAIN, get_rfx_object
from .binary_sensor import supported as binary_supported
from .const import (
    CONF_AUTOMATIC_ADD,
    CONF_DATA_BITS,
    CONF_DEBUG,
    CONF_FIRE_EVENT,
    CONF_OFF_DELAY,
    CONF_SIGNAL_REPETITIONS,
)
from .cover import supported as cover_supported
from .light import supported as light_supported
from .switch import supported as switch_supported

_LOGGER = logging.getLogger(__name__)


class OptionsFlow(config_entries.OptionsFlow):
    """Handle Rfxtrx options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize vizio options flow."""
        self._config_entry = config_entry
        self._global_options = None
        self._selected_device = None
        self._selected_device_event_code = None
        self._device_entries = None

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_prompt_options()

    async def async_step_prompt_options(self, user_input=None):
        """Prompt for options."""
        errors = {}

        if user_input is not None:
            self._global_options = {
                CONF_DEBUG: user_input[CONF_DEBUG],
                CONF_AUTOMATIC_ADD: user_input[CONF_AUTOMATIC_ADD],
            }
            if CONF_DEVICE in user_input:
                event_code = None
                for entry in self._device_entries:
                    if entry.id == user_input[CONF_DEVICE]:
                        device_id = next(iter(entry.identifiers))[1:]
                        for packet_id, entity_info in self._config_entry.data[
                            CONF_DEVICES
                        ].items():
                            if entity_info.get(CONF_DEVICE_ID) == device_id:
                                event_code = packet_id
                                break
                        break
                if not event_code:
                    errors = {"base": "unknown_event_code"}
                else:
                    self._selected_device_event_code = event_code
                    self._selected_device = self._config_entry.data[CONF_DEVICES][
                        event_code
                    ].copy()
                    return await self.async_step_set_device_options()
            if CONF_DEVICE_ID in user_input:
                return None

            if not errors:
                self.update_config_data(self._global_options)

                return self.async_create_entry(title="", data={})

        device_registry = await async_get_registry(self.hass)
        device_entries = async_entries_for_config_entry(
            device_registry, self._config_entry.entry_id
        )
        self._device_entries = device_entries

        devices = {
            entry.id: entry.name_by_user if entry.name_by_user else entry.name
            for entry in device_entries
        }

        options = {
            vol.Optional(CONF_DEBUG, default=self._config_entry.data[CONF_DEBUG]): bool,
            vol.Optional(
                CONF_AUTOMATIC_ADD, default=self._config_entry.data[CONF_AUTOMATIC_ADD],
            ): bool,
            vol.Optional(CONF_DEVICE_ID): str,
            vol.Optional(CONF_DEVICE): vol.In(devices),
        }

        return self.async_show_form(
            step_id="prompt_options", data_schema=vol.Schema(options), errors=errors
        )

    async def async_step_set_device_options(self, user_input=None):
        """Manage device options."""
        if user_input is not None:
            return None

        device_data = self._selected_device

        rfx_obj = get_rfx_object(self._selected_device_event_code)

        data_scheme = {
            vol.Optional(
                CONF_FIRE_EVENT, default=device_data.get(CONF_FIRE_EVENT, False)
            ): bool,
        }

        if binary_supported(rfx_obj):
            data_scheme.update(
                {
                    vol.Optional(
                        CONF_OFF_DELAY, default=device_data.get(CONF_OFF_DELAY, 0)
                    ): int,
                }
            )

        if (
            binary_supported(rfx_obj)
            or cover_supported(rfx_obj)
            or light_supported(rfx_obj)
            or switch_supported(rfx_obj)
        ):
            data_scheme.update(
                {
                    vol.Optional(
                        CONF_SIGNAL_REPETITIONS,
                        default=device_data.get(CONF_SIGNAL_REPETITIONS),
                    ): int,
                }
            )

        if rfx_obj.device.type_string == "PT2262":
            data_scheme.update(
                {
                    vol.Optional(
                        CONF_DATA_BITS, default=device_data.get(CONF_DATA_BITS, 0)
                    ): int,
                    vol.Optional(
                        CONF_COMMAND_ON,
                        default=hex(device_data.get(CONF_COMMAND_ON, 0)),
                    ): str,
                    vol.Optional(
                        CONF_COMMAND_OFF,
                        default=hex(device_data.get(CONF_COMMAND_OFF, 0)),
                    ): str,
                }
            )

        return self.async_show_form(
            step_id="set_device_options", data_schema=vol.Schema(data_scheme)
        )

    @callback
    def update_config_data(self, data):
        """Update data in ConfigEntry."""
        entry_data = self._config_entry.data.copy()
        entry_data.update(data)
        self.hass.config_entries.async_update_entry(self._config_entry, data=entry_data)
        self.hass.async_create_task(async_update_options(self.hass, self._config_entry))


@callback
def async_update_options(hass, config_entry: ConfigEntry):
    """Update options."""
    hass.config_entries.async_reload(config_entry.entry_id)


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
