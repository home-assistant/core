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

from . import DOMAIN, get_device_id, get_rfx_object
from .binary_sensor import supported as binary_supported
from .const import (
    CONF_AUTOMATIC_ADD,
    CONF_DATA_BITS,
    CONF_DEBUG,
    CONF_FIRE_EVENT,
    CONF_OFF_DELAY,
    CONF_SIGNAL_REPETITIONS,
    DEVICE_PACKET_TYPE_LIGHTING4,
)
from .cover import supported as cover_supported
from .light import supported as light_supported
from .switch import supported as switch_supported

_LOGGER = logging.getLogger(__name__)

CONF_OFF_DELAY_ENABLED = CONF_OFF_DELAY + "_enabled"


class OptionsFlow(config_entries.OptionsFlow):
    """Handle Rfxtrx options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize vizio options flow."""
        self._config_entry = config_entry
        self._global_options = None
        self._selected_device = None
        self._selected_device_event_code = None
        self._rfxobj = None
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
                    ]
                    return await self.async_step_set_device_options()
            if CONF_DEVICE_ID in user_input:
                self._selected_device_event_code = user_input[CONF_DEVICE_ID]
                self._selected_device = {}
                return await self.async_step_set_device_options()

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
        errors = {}

        if user_input is not None:
            device_id = get_device_id(
                self._rfxobj.device, data_bits=user_input.get(CONF_DATA_BITS)
            )
            try:
                command_on = (
                    int(user_input.get(CONF_COMMAND_ON), 16)
                    if user_input.get(CONF_COMMAND_ON)
                    else None
                )
                command_off = (
                    int(user_input.get(CONF_COMMAND_OFF), 16)
                    if user_input.get(CONF_COMMAND_OFF)
                    else None
                )
            except NameError:
                errors = {"base": "invalid_input_2262"}

            if not errors:
                data = {
                    CONF_DEVICES: {
                        self._selected_device_event_code: {
                            CONF_DEVICE: device_id,
                            CONF_FIRE_EVENT: user_input.get(CONF_FIRE_EVENT),
                            CONF_OFF_DELAY: user_input.get(CONF_OFF_DELAY)
                            if user_input.get(CONF_OFF_DELAY_ENABLED)
                            else None,
                            CONF_SIGNAL_REPETITIONS: user_input.get(
                                CONF_SIGNAL_REPETITIONS
                            ),
                            CONF_DATA_BITS: user_input.get(CONF_DATA_BITS),
                            CONF_COMMAND_ON: command_on,
                            CONF_COMMAND_OFF: command_off,
                        }
                    }
                }

                self.update_config_data(data)

                return self.async_create_entry(title="", data={})

        device_data = self._selected_device

        if self._rfxobj is None:
            self._rfxobj = get_rfx_object(self._selected_device_event_code)

        data_scheme = {
            vol.Optional(
                CONF_FIRE_EVENT, default=device_data.get(CONF_FIRE_EVENT, False)
            ): bool,
        }

        if binary_supported(self._rfxobj):
            data_scheme.update(
                {
                    vol.Optional(
                        CONF_OFF_DELAY_ENABLED,
                        default=device_data.get(CONF_OFF_DELAY) is not None,
                    ): bool,
                    vol.Optional(
                        CONF_OFF_DELAY, default=device_data.get(CONF_OFF_DELAY, 0)
                    ): int,
                }
            )

        if (
            binary_supported(self._rfxobj)
            or cover_supported(self._rfxobj)
            or light_supported(self._rfxobj)
            or switch_supported(self._rfxobj)
        ):
            data_scheme.update(
                {
                    vol.Optional(
                        CONF_SIGNAL_REPETITIONS,
                        default=device_data.get(CONF_SIGNAL_REPETITIONS),
                    ): int,
                }
            )

        if self._rfxobj.device.packettype == DEVICE_PACKET_TYPE_LIGHTING4:
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
            step_id="set_device_options",
            data_schema=vol.Schema(data_scheme),
            errors=errors,
        )

    @callback
    def update_config_data(self, data):
        """Update data in ConfigEntry."""
        entry_data = self._config_entry.data.copy()
        entry_data.update(data)
        self.hass.config_entries.async_update_entry(self._config_entry, data=entry_data)
        self.hass.async_create_task(async_update_options(self.hass, self._config_entry))


async def async_update_options(hass, config_entry: ConfigEntry):
    """Update options."""
    await hass.config_entries.async_reload(config_entry.entry_id)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RFXCOM RFXtrx."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_import(self, import_config=None):
        """Handle the initial step."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="RFXTRX", data=import_config)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlow(config_entry)
