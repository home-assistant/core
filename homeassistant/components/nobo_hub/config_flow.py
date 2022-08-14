"""Config flow for Nobø Ecohub integration."""
from __future__ import annotations

from collections import OrderedDict
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


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nobø Ecohub."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._discovered_hubs = None

    @staticmethod
    def _device(hub):
        (ip, serial_prefix) = hub
        return {"ip": ip, "serial_prefix": serial_prefix}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if self._discovered_hubs is None:
            self._discovered_hubs = list(
                map(self._device, await nobo.async_discover_hubs(loop=self.hass.loop))
            )

        if len(self._discovered_hubs) == 0:
            # No hubs auto discovered
            return await self.async_step_manual()

        errors = {}
        serial_suffix = ""
        if user_input is not None:
            if "manual" in user_input:
                return await self.async_step_manual()
            serial, ip_address = None, None
            if "serial_suffix" not in user_input or user_input["serial_suffix"] == "":
                errors["base"] = "missing_serial_suffix"
            else:
                hub = self._discovered_hubs[user_input["device"]]
                serial_prefix = hub["serial_prefix"]
                serial_suffix = user_input["serial_suffix"]
                serial = f"{serial_prefix}{serial_suffix}"
                if "store_ip" in user_input and user_input["store_ip"]:
                    ip_address = hub["ip"]

            if not errors:
                try:
                    return await self._create_configuration(serial, ip_address)
                except NoboHubConnectError as error:
                    errors["base"] = error.msg

        data_schema = vol.Schema(
            {
                vol.Optional("manual"): bool,
                vol.Required("device"): vol.In(self._hubs()),
                vol.Optional("serial_suffix", default=serial_suffix): str,
                vol.Optional("store_ip"): bool,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual configuration. Triggered if no devices are discovered or by user."""
        errors = {}
        serial, ip_address = None, None
        if user_input is not None:
            serial = user_input.get(CONF_SERIAL)
            ip_address = user_input.get(CONF_IP_ADDRESS)
            try:
                return await self._create_configuration(serial, ip_address)
            except NoboHubConnectError as error:
                errors["base"] = error.msg

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SERIAL, default=serial): str,
                    vol.Required(CONF_IP_ADDRESS, default=ip_address): str,
                }
            ),
            errors=errors,
        )

    async def _create_configuration(self, serial, ip_address) -> FlowResult:
        await self.async_set_unique_id(serial)
        self._abort_if_unique_id_configured()
        name = await self._test_connection(serial, ip_address)
        return self.async_create_entry(
            title=name, data={"serial": serial, "ip_address": ip_address}
        )

    async def _test_connection(self, serial, ip_address):
        if serial is None or not len(serial) == 12 or not serial.isdigit():
            raise NoboHubConnectError("invalid_serial")
        if ip_address is not None:
            try:
                socket.inet_aton(ip_address)
            except OSError:
                raise NoboHubConnectError("invalid_ip") from OSError
        else:
            for hub in self._discovered_hubs:
                if serial.startswith(hub["serial_prefix"]):
                    ip_address = hub["ip"]
                    break

        hub = nobo(serial=serial, ip=ip_address, discover=False, loop=self.hass.loop)
        if not await hub.async_connect_hub(ip_address, serial):
            raise NoboHubConnectError("cannot_connect")

        name = hub.hub_info["name"]
        await hub.close()
        return name

    def _hubs(self):
        def _hub(hub):
            return hub[0], f"{hub[1]['serial_prefix']}XXX ({hub[1]['ip']})"

        return OrderedDict(map(_hub, enumerate(self._discovered_hubs)))

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class NoboHubConnectError(HomeAssistantError):
    """Error with connecting to Nobø Ecohub."""

    def __init__(self, msg) -> None:
        """Instantiate error."""
        super().__init__()
        self.msg = msg


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handles options flow for the component."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
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
        on_commands = self.config_entry.options.get(CONF_COMMAND_ON)  # type: ignore[assignment]
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
