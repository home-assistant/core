"""Config flow for ZHA."""
from __future__ import annotations

import os
from typing import Any

import serial.tools.list_ports
import voluptuous as vol
from zigpy.config import CONF_DEVICE, CONF_DEVICE_PATH

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.typing import DiscoveryInfoType

from .core.const import (
    CONF_BAUDRATE,
    CONF_FLOWCONTROL,
    CONF_RADIO_TYPE,
    DOMAIN,
    RadioType,
)

CONF_MANUAL_PATH = "Enter Manually"
SUPPORTED_PORT_SETTINGS = (
    CONF_BAUDRATE,
    CONF_FLOWCONTROL,
)


class ZhaFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 2

    def __init__(self):
        """Initialize flow instance."""
        self._device_path = None
        self._radio_type = None

    async def async_step_user(self, user_input=None):
        """Handle a zha config flow start."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        ports = await self.hass.async_add_executor_job(serial.tools.list_ports.comports)
        list_of_ports = [
            f"{p}, s/n: {p.serial_number or 'n/a'}"
            + (f" - {p.manufacturer}" if p.manufacturer else "")
            for p in ports
        ]

        if not list_of_ports:
            return await self.async_step_pick_radio()

        list_of_ports.append(CONF_MANUAL_PATH)

        if user_input is not None:
            user_selection = user_input[CONF_DEVICE_PATH]
            if user_selection == CONF_MANUAL_PATH:
                return await self.async_step_pick_radio()

            port = ports[list_of_ports.index(user_selection)]
            dev_path = await self.hass.async_add_executor_job(
                get_serial_by_id, port.device
            )
            auto_detected_data = await detect_radios(dev_path)
            if auto_detected_data is not None:
                title = f"{port.description}, s/n: {port.serial_number or 'n/a'}"
                title += f" - {port.manufacturer}" if port.manufacturer else ""
                return self.async_create_entry(
                    title=title,
                    data=auto_detected_data,
                )

            # did not detect anything
            self._device_path = dev_path
            return await self.async_step_pick_radio()

        schema = vol.Schema({vol.Required(CONF_DEVICE_PATH): vol.In(list_of_ports)})
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_pick_radio(self, user_input=None):
        """Select radio type."""

        if user_input is not None:
            self._radio_type = RadioType.get_by_description(user_input[CONF_RADIO_TYPE])
            return await self.async_step_port_config()

        schema = {vol.Required(CONF_RADIO_TYPE): vol.In(sorted(RadioType.list()))}
        return self.async_show_form(
            step_id="pick_radio",
            data_schema=vol.Schema(schema),
        )

    async def async_step_zeroconf(self, discovery_info: DiscoveryInfoType):
        """Handle zeroconf discovery."""
        # Hostname is format: livingroom.local.
        local_name = discovery_info["hostname"][:-1]
        node_name = local_name[: -len(".local")]
        host = discovery_info[CONF_HOST]
        device_path = f"socket://{host}:6638"

        await self.async_set_unique_id(node_name)
        self._abort_if_unique_id_configured(
            updates={
                CONF_DEVICE: {CONF_DEVICE_PATH: device_path},
            }
        )

        # Check if already configured
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        self.context["title_placeholders"] = {
            CONF_NAME: node_name,
        }

        self._device_path = device_path
        self._radio_type = (
            RadioType.ezsp.name if "efr32" in local_name else RadioType.znp.name
        )

        return await self.async_step_port_config()

    async def async_step_port_config(self, user_input=None):
        """Enter port settings specific for this type of radio."""
        errors = {}
        app_cls = RadioType[self._radio_type].controller

        if user_input is not None:
            self._device_path = user_input.get(CONF_DEVICE_PATH)
            if await app_cls.probe(user_input):
                serial_by_id = await self.hass.async_add_executor_job(
                    get_serial_by_id, user_input[CONF_DEVICE_PATH]
                )
                user_input[CONF_DEVICE_PATH] = serial_by_id
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
        radio_schema = app_cls.SCHEMA_DEVICE.schema
        if isinstance(radio_schema, vol.Schema):
            radio_schema = radio_schema.schema

        source = self.context.get("source")
        for param, value in radio_schema.items():
            if param in SUPPORTED_PORT_SETTINGS:
                schema[param] = value
                if source == config_entries.SOURCE_ZEROCONF and param == CONF_BAUDRATE:
                    schema[param] = 115200

        return self.async_show_form(
            step_id="port_config",
            data_schema=vol.Schema(schema),
            errors=errors,
        )


async def detect_radios(dev_path: str) -> dict[str, Any] | None:
    """Probe all radio types on the device port."""
    for radio in RadioType:
        dev_config = radio.controller.SCHEMA_DEVICE({CONF_DEVICE_PATH: dev_path})
        if await radio.controller.probe(dev_config):
            return {CONF_RADIO_TYPE: radio.name, CONF_DEVICE: dev_config}

    return None


def get_serial_by_id(dev_path: str) -> str:
    """Return a /dev/serial/by-id match for given device if available."""
    by_id = "/dev/serial/by-id"
    if not os.path.isdir(by_id):
        return dev_path

    for path in (entry.path for entry in os.scandir(by_id) if entry.is_symlink()):
        if os.path.realpath(path) == dev_path:
            return path
    return dev_path
