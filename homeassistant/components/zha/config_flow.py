"""Config flow for ZHA."""
from __future__ import annotations

from typing import Any

import serial.tools.list_ports
import voluptuous as vol
from zigpy.config import CONF_DEVICE, CONF_DEVICE_PATH

from homeassistant import config_entries
from homeassistant.components import usb, zeroconf
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult

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
DECONZ_DOMAIN = "deconz"


class ZhaFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 3

    def __init__(self):
        """Initialize flow instance."""
        self._device_path = None
        self._radio_type = None
        self._title = None

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
                usb.get_serial_by_id, port.device
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

    async def async_step_usb(self, discovery_info: usb.UsbServiceInfo) -> FlowResult:
        """Handle usb discovery."""
        vid = discovery_info.vid
        pid = discovery_info.pid
        serial_number = discovery_info.serial_number
        device = discovery_info.device
        manufacturer = discovery_info.manufacturer
        description = discovery_info.description
        dev_path = await self.hass.async_add_executor_job(usb.get_serial_by_id, device)
        unique_id = f"{vid}:{pid}_{serial_number}_{manufacturer}_{description}"
        if current_entry := await self.async_set_unique_id(unique_id):
            self._abort_if_unique_id_configured(
                updates={
                    CONF_DEVICE: {
                        **current_entry.data.get(CONF_DEVICE, {}),
                        CONF_DEVICE_PATH: dev_path,
                    },
                }
            )
        # Check if already configured
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        # If they already have a discovery for deconz
        # we ignore the usb discovery as they probably
        # want to use it there instead
        if self.hass.config_entries.flow.async_progress_by_handler(DECONZ_DOMAIN):
            return self.async_abort(reason="not_zha_device")
        for entry in self.hass.config_entries.async_entries(DECONZ_DOMAIN):
            if entry.source != config_entries.SOURCE_IGNORE:
                return self.async_abort(reason="not_zha_device")

        self._device_path = dev_path
        self._title = usb.human_readable_device_name(
            dev_path,
            serial_number,
            manufacturer,
            description,
            vid,
            pid,
        )
        self._set_confirm_only()
        self.context["title_placeholders"] = {CONF_NAME: self._title}
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None):
        """Confirm a discovery."""
        if user_input is not None:
            auto_detected_data = await detect_radios(self._device_path)
            if auto_detected_data is None:
                # This path probably will not happen now that we have
                # more precise USB matching unless there is a problem
                # with the device
                return self.async_abort(reason="usb_probe_failed")
            return self.async_create_entry(
                title=self._title,
                data=auto_detected_data,
            )

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={CONF_NAME: self._title},
            data_schema=vol.Schema({}),
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""
        # Hostname is format: livingroom.local.
        local_name = discovery_info.hostname[:-1]
        node_name = local_name[: -len(".local")]
        host = discovery_info.host
        device_path = f"socket://{host}:6638"

        if current_entry := await self.async_set_unique_id(node_name):
            self._abort_if_unique_id_configured(
                updates={
                    CONF_DEVICE: {
                        **current_entry.data.get(CONF_DEVICE, {}),
                        CONF_DEVICE_PATH: device_path,
                    },
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
                    usb.get_serial_by_id, user_input[CONF_DEVICE_PATH]
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
        probe_result = await radio.controller.probe(dev_config)
        if probe_result:
            if isinstance(probe_result, dict):
                return {CONF_RADIO_TYPE: radio.name, CONF_DEVICE: probe_result}
            return {CONF_RADIO_TYPE: radio.name, CONF_DEVICE: dev_config}

    return None
