"""Config flow for Airtouch 5 integration."""

from __future__ import annotations

import logging
from typing import Any

from airtouch5py.airtouch5_simple_client import Airtouch5SimpleClient
from airtouch5py.discovery import AirtouchDevice, AirtouchDiscovery
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


class AirTouch5ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Airtouch 5."""

    VERSION = 2
    devices: list[AirtouchDevice] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        AirtouchDiscovery_instance = AirtouchDiscovery()
        await AirtouchDiscovery_instance.establish_server()
        devices = await AirtouchDiscovery_instance.discover()

        options = {
            f"{device.system_id:}": f"{device.name} - {device.ip}" for device in devices
        }
        options["manual"] = "Manual Entry"  # Placeholder option

        self.devices = devices

        schema = vol.Schema({vol.Required("Select Device"): vol.In(options)})
        return self.async_show_form(step_id="choose", data_schema=schema)

    async def async_step_choose(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the device selection step."""
        errors: dict[str, str] | None = None
        if user_input is not None:
            if user_input.get("Select Device") != "manual":
                selected_device_id = user_input.get("Select Device")
                # Find the device with the selected ID
                for device in self.devices:
                    if str(device.system_id) == selected_device_id:
                        client = Airtouch5SimpleClient(device)
                        try:
                            await client.test_connection()
                        except Exception:
                            _LOGGER.exception("Unexpected exception")
                            errors = {"base": "cannot_connect"}
                        else:
                            user_input = {CONF_HOST: device.ip}
                            await self.async_set_unique_id(device.system_id)
                            self._abort_if_unique_id_configured()
                            return self.async_create_entry(
                                title=f"{device.name} ({device.system_id})",
                                data={
                                    "system_id": device.system_id,
                                    "host": device.ip,
                                    "model": device.model,
                                    "console_id": device.console_id,
                                    "name": device.name,
                                },
                            )
            # Manual entry selected, show manual entry form
        else:
            raise ValueError("user_input cannot be None here")
        return self.async_show_form(
            step_id="manual", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the manual entry step."""
        errors: dict[str, str] | None = None
        host = user_input.get(CONF_HOST) if user_input else None
        if not host:
            # No input yet, show the manual entry form
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
            )

        host_str = str(host)
        client = Airtouch5SimpleClient(host_str)
        try:
            await client.test_connection()
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors = {"base": "cannot_connect"}
        else:
            await self.async_set_unique_id(host_str)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=host_str, data={CONF_HOST: host_str})
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
