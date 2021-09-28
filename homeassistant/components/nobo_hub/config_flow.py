"""Config flow for Nobø Ecohub integration."""
from __future__ import annotations

import logging
import socket
from typing import Any

from pynobo import nobo
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_COMMAND_OFF, CONF_COMMAND_ON, CONF_IP_ADDRESS
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_OVERRIDE_TYPE,
    CONF_OVERRIDE_TYPE_CONSTANT,
    CONF_OVERRIDE_TYPE_NOW,
    CONF_SERIAL,
    CONF_WEEK_PROFILE_NONE,
    DOMAIN,
)

DATA_NOBO_HUB_IMPL = "nobo_hub_flow_implementation"
DEVICE_INPUT = "device_input"

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nobø Ecohub."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self.discovered_hubs = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if self.discovered_hubs is None:
            self.discovered_hubs = await nobo.async_discover_hubs(loop=self.hass.loop)

        errors = {}
        if user_input is not None:
            try:
                return await self._test_connection(user_input)
            except InvalidSerial:
                errors["base"] = "invalid_serial"
            except InvalidIP:
                errors["base"] = "invalid_ip"
            except DeviceNotFound:
                errors["base"] = "device_not_found"
            except CannotConnect:
                errors["base"] = "cannot_connect"

        default_suggestion = self._prefill_identifier()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SERIAL, default=default_suggestion): str,
                    vol.Optional(CONF_IP_ADDRESS): str,
                }
            ),
            errors=errors,
            description_placeholders={"devices": self._devices_str()},
        )

    async def _test_connection(self, user_input):
        serial = user_input.get(CONF_SERIAL)
        ip_address = user_input.get(CONF_IP_ADDRESS)
        if serial is None or not len(serial) == 12 or not serial.isdigit():
            raise InvalidSerial()
        if ip_address is not None:
            try:
                socket.inet_aton(ip_address)
            except OSError:
                raise InvalidIP() from OSError
        else:
            for (discovered_ip, serial_prefix) in self.discovered_hubs:
                if serial.startswith(serial_prefix):
                    ip_address = discovered_ip
                    break
            if ip_address is None:
                raise DeviceNotFound()

        await self.async_set_unique_id(serial)
        self._abort_if_unique_id_configured()

        # Test connection
        hub = nobo(serial=serial, ip=ip_address, discover=False, loop=self.hass.loop)
        if await hub.async_connect_hub(ip_address, serial):
            await hub.close()
            await self.async_set_unique_id(serial, raise_on_progress=False)
            self._abort_if_unique_id_configured(
                reload_on_update=False, updates=user_input
            )
            return self.async_create_entry(title=hub.hub_info["name"], data=user_input)
        raise CannotConnect()

    def _devices_str(self):
        return ", ".join(
            [f"`{serial}XXX ({ip})`" for (ip, serial) in self.discovered_hubs]
        )

    def _prefill_identifier(self):
        for (_, serial) in self.discovered_hubs:
            return serial + "XXX"
        return ""

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class CannotConnect(HomeAssistantError):
    """Unable to connect to Nobø Ecohub."""


class InvalidIP(HomeAssistantError):
    """Invalid IP address."""


class InvalidSerial(HomeAssistantError):
    """Invalid serial number."""


class DeviceNotFound(HomeAssistantError):
    """No device found."""


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handles options flow for the component."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initializr the options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""

        hub = self.hass.data[DOMAIN][self.config_entry.entry_id]
        profile_names = sorted(
            k["name"].replace("\xa0", " ") for k in hub.week_profiles.values()
        )

        if user_input is not None:
            off_command = user_input.get(CONF_COMMAND_OFF)
            if off_command not in profile_names:
                off_command = None
            on_commands = {}
            for key, on_command in user_input.items():
                if key.startswith(CONF_COMMAND_ON + "_zone_"):
                    zone = key[16:]
                    if on_command not in profile_names:
                        on_command = None
                    on_commands[
                        hub.zones[zone]["name"].replace("\xa0", " ")
                    ] = on_command

            data = {
                CONF_OVERRIDE_TYPE: user_input.get(CONF_OVERRIDE_TYPE),
                CONF_COMMAND_OFF: off_command,
                CONF_COMMAND_ON: on_commands,
            }

            return self.async_create_entry(title="", data=data)

        override_type = self.config_entry.options.get(CONF_OVERRIDE_TYPE)
        if override_type != CONF_OVERRIDE_TYPE_NOW:
            override_type = CONF_OVERRIDE_TYPE_CONSTANT

        profile_names.insert(0, CONF_WEEK_PROFILE_NONE)
        profiles = vol.Schema(vol.In(profile_names))

        off_command = self.config_entry.options.get(CONF_COMMAND_OFF)
        if off_command not in profile_names:
            off_command = CONF_WEEK_PROFILE_NONE
        schema = vol.Schema(
            {
                vol.Required(CONF_OVERRIDE_TYPE, default=override_type): vol.In(
                    [CONF_OVERRIDE_TYPE_CONSTANT, CONF_OVERRIDE_TYPE_NOW]
                ),
                # Ideally we should use vol.Optional, but resetting the field in the UI
                # will default to the old value instead of setting to None.
                vol.Required(CONF_COMMAND_OFF, default=off_command): profiles,
            }
        )

        placeholder = ""
        on_commands = self.config_entry.options.get(CONF_COMMAND_ON)
        if on_commands is None:
            on_commands = {}
        for zone in hub.zones:
            name = hub.zones[zone]["name"].replace("\xa0", " ")
            on_command = (
                on_commands[name]
                if name in on_commands and on_commands[name] in profile_names
                else CONF_WEEK_PROFILE_NONE
            )
            schema = schema.extend(
                {
                    vol.Required(
                        CONF_COMMAND_ON + "_zone_" + zone, default=on_command
                    ): profiles
                }
            )
            placeholder += zone + ": " + name + "\r"

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            description_placeholders={"zones": placeholder},
        )
