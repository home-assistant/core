"""Config flow for Nobø Ecohub integration."""
from __future__ import annotations

import logging
import socket
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from pynobo import nobo

from ...const import CONF_COMMAND_OFF, CONF_COMMAND_ON, CONF_IP_ADDRESS
from ...exceptions import HomeAssistantError
from .const import CONF_SERIAL, DOMAIN, HUB

DATA_NOBO_HUB_IMPL = "nobo_hub_flow_implementation"
DEVICE_INPUT = "device_input"

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nobø Ecohub."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

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
                serial = user_input.get(CONF_SERIAL)
                ip = user_input.get(CONF_IP_ADDRESS)
                if serial is None or not len(serial) == 12 or not serial.isdigit():
                    raise InvalidSerial()
                if ip is not None:
                    try:
                        socket.inet_aton(ip)
                    except OSError:
                        raise InvalidIP()
                else:
                    for (discovered_ip, serial_prefix) in self.discovered_hubs:
                        if serial.startswith(serial_prefix):
                            ip = discovered_ip
                            break
                    if ip is None:
                        raise DeviceNotFound()
                # Test connection
                hub = nobo(serial=serial, ip=ip, discover=False, loop=self.hass.loop)
                if await hub.async_connect_hub(ip, serial):
                    await hub.close()
                    await self.async_set_unique_id(serial, raise_on_progress=False)
                    self._abort_if_unique_id_configured(
                        reload_on_update=False, updates=user_input
                    )
                    return self.async_create_entry(
                        title=hub.hub_info["name"], data=user_input
                    )
                else:
                    raise CannotConnect()
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

    def _devices_str(self):
        return ", ".join(
            [f"`{serial}XXX ({ip})`" for (ip, serial) in self.discovered_hubs]
        )

    def _prefill_identifier(self):
        for (ip, serial) in self.discovered_hubs:
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

        hub = self.hass.data[DOMAIN][self.config_entry.entry_id][HUB]

        if user_input is not None:
            off_command = (
                ""
                if user_input.get(CONF_COMMAND_OFF) == "Default"
                else user_input.get(CONF_COMMAND_OFF)
            )

            on_commands = {}
            for k, v in user_input.items():
                if k.startswith(CONF_COMMAND_ON + "_zone_") and v != "Default":
                    zone = k.removeprefix(CONF_COMMAND_ON + "_zone_")
                    on_commands[hub.zones[zone]["name"].replace("\xa0", " ")] = v

            data = {CONF_COMMAND_OFF: off_command, CONF_COMMAND_ON: on_commands}

            return self.async_create_entry(title="", data=data)

        off_command = self.config_entry.options.get(CONF_COMMAND_OFF)
        on_commands = self.config_entry.options.get(CONF_COMMAND_ON)
        if on_commands is None:
            on_commands = {}

        profileNames = [
            k["name"].replace("\xa0", " ") for k in hub.week_profiles.values()
        ]
        profileNames.insert(0, "")
        profiles = vol.Schema(vol.In(profileNames))

        schema = vol.Schema(
            {
                vol.Optional(CONF_COMMAND_OFF, default=off_command): profiles,
            }
        )

        placeholder = ""
        for zone in hub.zones:
            name = hub.zones[zone]["name"].replace("\xa0", " ")
            on_command = on_commands[name] if name in on_commands else ""
            schema = schema.extend(
                {
                    vol.Optional(
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
