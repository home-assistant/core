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
    CONF_REMOVE_DEVICE,
    CONF_SIGNAL_REPETITIONS,
    DEVICE_PACKET_TYPE_LIGHTING4,
)
from .cover import supported as cover_supported
from .light import supported as light_supported
from .switch import supported as switch_supported

_LOGGER = logging.getLogger(__name__)

CONF_EVENT_CODE = "event_code"


def none_or_int(value, base):
    """Check if strin is one otherwise convert to int."""
    if value is None:
        return None
    return int(value, base)


class OptionsFlow(config_entries.OptionsFlow):
    """Handle Rfxtrx options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize rfxtrx options flow."""
        self._config_entry = config_entry
        self._global_options = None
        self._selected_device = None
        self._selected_device_event_code = None
        self._selected_device_object = None
        self._device_entries = None
        self._device_registry = None

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
                device_data = self._get_device_data(user_input[CONF_DEVICE])
                event_code = device_data[CONF_EVENT_CODE]
                self._selected_device_event_code = event_code
                self._selected_device = self._config_entry.data[CONF_DEVICES][
                    event_code
                ]
                self._selected_device_object = get_rfx_object(event_code)
                return await self.async_step_set_device_options()
            if CONF_REMOVE_DEVICE in user_input:
                entry_id = user_input[CONF_REMOVE_DEVICE]
                device_data = self._get_device_data(entry_id)

                event_code = device_data[CONF_EVENT_CODE]
                device_id = device_data[CONF_DEVICE_ID]
                self.hass.helpers.dispatcher.async_dispatcher_send(
                    f"{DOMAIN}_{CONF_REMOVE_DEVICE}_{device_id}"
                )
                self._device_registry.async_remove_device(entry_id)
                devices = {event_code: None}
                self.update_config_data(
                    global_options=self._global_options, devices=devices
                )

                return self.async_create_entry(title="", data={})
            if CONF_EVENT_CODE in user_input:
                self._selected_device_event_code = user_input[CONF_EVENT_CODE]
                self._selected_device = {}
                selected_device_object = get_rfx_object(
                    self._selected_device_event_code
                )
                if selected_device_object is None:
                    errors[CONF_EVENT_CODE] = "invalid_event_code"
                else:
                    self._selected_device_object = selected_device_object
                    return await self.async_step_set_device_options()

            if not errors:
                self.update_config_data(global_options=self._global_options)

                return self.async_create_entry(title="", data={})

        device_registry = await async_get_registry(self.hass)
        device_entries = async_entries_for_config_entry(
            device_registry, self._config_entry.entry_id
        )
        self._device_registry = device_registry
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
            vol.Optional(CONF_EVENT_CODE): str,
            vol.Optional(CONF_DEVICE): vol.In(devices),
            vol.Optional(CONF_REMOVE_DEVICE): vol.In(devices),
        }

        return self.async_show_form(
            step_id="prompt_options", data_schema=vol.Schema(options), errors=errors
        )

    async def async_step_set_device_options(self, user_input=None):
        """Manage device options."""
        errors = {}

        if user_input is not None:
            device_id = get_device_id(
                self._selected_device_object.device,
                data_bits=user_input.get(CONF_DATA_BITS),
            )

            try:
                command_on = none_or_int(user_input.get(CONF_COMMAND_ON), 16)
            except ValueError:
                errors[CONF_COMMAND_ON] = "invalid_input_2262_on"

            try:
                command_off = none_or_int(user_input.get(CONF_COMMAND_OFF), 16)
            except ValueError:
                errors[CONF_COMMAND_OFF] = "invalid_input_2262_off"

            try:
                off_delay = none_or_int(user_input.get(CONF_OFF_DELAY), 10)
            except ValueError:
                errors[CONF_OFF_DELAY] = "invalid_input_off_delay"

            if not errors:
                devices = {}
                device = {
                    CONF_DEVICE_ID: device_id,
                    CONF_FIRE_EVENT: user_input.get(CONF_FIRE_EVENT, False),
                    CONF_SIGNAL_REPETITIONS: user_input.get(CONF_SIGNAL_REPETITIONS, 1),
                }

                devices[self._selected_device_event_code] = device

                if off_delay:
                    device[CONF_OFF_DELAY] = off_delay
                if user_input.get(CONF_DATA_BITS):
                    device[CONF_DATA_BITS] = user_input[CONF_DATA_BITS]
                if command_on:
                    device[CONF_COMMAND_ON] = command_on
                if command_off:
                    device[CONF_COMMAND_OFF] = command_off

                self.update_config_data(
                    global_options=self._global_options, devices=devices
                )

                return self.async_create_entry(title="", data={})

        device_data = self._selected_device

        data_schema = {
            vol.Optional(
                CONF_FIRE_EVENT, default=device_data.get(CONF_FIRE_EVENT, False)
            ): bool,
        }

        if binary_supported(self._selected_device_object):
            if device_data.get(CONF_OFF_DELAY):
                off_delay_schema = {
                    vol.Optional(
                        CONF_OFF_DELAY,
                        description={"suggested_value": device_data[CONF_OFF_DELAY]},
                    ): str,
                }
            else:
                off_delay_schema = {
                    vol.Optional(CONF_OFF_DELAY): str,
                }
            data_schema.update(off_delay_schema)

        if (
            binary_supported(self._selected_device_object)
            or cover_supported(self._selected_device_object)
            or light_supported(self._selected_device_object)
            or switch_supported(self._selected_device_object)
        ):
            data_schema.update(
                {
                    vol.Optional(
                        CONF_SIGNAL_REPETITIONS,
                        default=device_data.get(CONF_SIGNAL_REPETITIONS, 1),
                    ): int,
                }
            )

        if (
            self._selected_device_object.device.packettype
            == DEVICE_PACKET_TYPE_LIGHTING4
        ):
            data_schema.update(
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
            data_schema=vol.Schema(data_schema),
            errors=errors,
        )

    def _get_device_data(self, entry_id):
        """Get event code based on device identifier."""
        event_code = None
        device_id = None
        entry = self._device_registry.async_get(entry_id)
        device_id = next(iter(entry.identifiers))[1:]
        for packet_id, entity_info in self._config_entry.data[CONF_DEVICES].items():
            if tuple(entity_info.get(CONF_DEVICE_ID)) == device_id:
                event_code = packet_id
                break

        data = {CONF_EVENT_CODE: event_code, CONF_DEVICE_ID: device_id}

        return data

    @callback
    def update_config_data(self, global_options=None, devices=None):
        """Update data in ConfigEntry."""
        entry_data = self._config_entry.data.copy()
        if global_options:
            entry_data.update(global_options)
        if devices:
            for event_code, options in devices.items():
                if options is None:
                    entry_data[CONF_DEVICES].pop(event_code)
                else:
                    entry_data[CONF_DEVICES][event_code] = options
        self.hass.config_entries.async_update_entry(self._config_entry, data=entry_data)
        self.hass.async_create_task(
            self.hass.config_entries.async_reload(self._config_entry.entry_id)
        )


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
