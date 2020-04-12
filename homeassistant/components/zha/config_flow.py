"""Config flow for ZHA."""
from typing import Any, Dict, Optional

import serial.tools.list_ports
import voluptuous as vol
from zigpy.config import CONF_DEVICE, CONF_DEVICE_PATH

from homeassistant import config_entries

from .core.const import CONF_RADIO_TYPE, CONTROLLER, DOMAIN, RadioType
from .core.registries import RADIO_TYPES

CONF_MANUAL_PATH = "Enter Manually"


class ZhaFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize flow instance."""
        self._device_path = None
        self._radio_type = None

    async def async_step_user(self, user_input=None):
        """Handle a zha config flow start."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        ports = serial.tools.list_ports.comports()
        list_of_ports = [
            f"{p}, s/n: {p.serial_number} - {p.manufacturer}" for p in ports
        ]
        list_of_ports.append(CONF_MANUAL_PATH)

        if user_input is not None:
            user_selection = user_input[CONF_DEVICE_PATH]
            if user_selection == CONF_MANUAL_PATH:
                return await self.async_step_pick_radio()

            dev_path = ports[list_of_ports.index(user_selection)].device
            auto_detected_data = await self.detect_radios(dev_path)
            if auto_detected_data is not None:
                return self.async_create_entry(
                    title=user_selection, data=auto_detected_data,
                )

            # did not detect anything
            self._device_path = dev_path
            return await self.async_step_pick_radio()

        schema = vol.Schema({vol.Required(CONF_DEVICE_PATH): vol.In(list_of_ports)})
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_import(self, import_info):
        """Handle a zha config import."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(
            title=import_info[CONF_DEVICE][CONF_DEVICE_PATH], data=import_info
        )

    async def async_step_pick_radio(self, user_input=None):
        """Select radio type."""

        if user_input is not None:
            self._radio_type = user_input[CONF_RADIO_TYPE]
            return await self.async_step_port_config()

        schema = {vol.Required(CONF_RADIO_TYPE): vol.In(sorted(RadioType.list()))}
        return self.async_show_form(
            step_id="pick_radio", data_schema=vol.Schema(schema),
        )

    async def async_step_port_config(self, user_input=None):
        """Enter port settings specific for this type of radio."""
        errors = {}
        app_cls = RADIO_TYPES[self._radio_type][CONTROLLER]

        if user_input is not None:
            self._device_path = user_input.get(CONF_DEVICE_PATH)
            if await app_cls.probe(user_input):
                return self.async_create_entry(
                    title=user_input[CONF_DEVICE_PATH],
                    data={CONF_DEVICE: user_input, CONF_RADIO_TYPE: self._radio_type},
                )
            errors["base"] = "cannot_connect"

        schema = {
            vol.Required(
                CONF_DEVICE_PATH, default=self._device_path or vol.UNDEFINED
            ): str
        }
        return self.async_show_form(
            step_id="port_config",
            data_schema=app_cls.SCHEMA_DEVICE.extend(schema),
            errors=errors,
        )

    @staticmethod
    async def detect_radios(dev_path: str) -> Optional[Dict[str, Any]]:
        """Probe all radio types on the device port."""
        for radio in RadioType.list():
            app_cls = RADIO_TYPES[radio][CONTROLLER]
            dev_config = app_cls.SCHEMA_DEVICE({CONF_DEVICE_PATH: dev_path})
            if await app_cls.probe(dev_config):
                return {CONF_RADIO_TYPE: radio, CONF_DEVICE: dev_config}

        return None
