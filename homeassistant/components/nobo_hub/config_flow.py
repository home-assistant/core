"""Config flow for Nobø Ecohub integration."""

from __future__ import annotations

import socket
from typing import Any

from pynobo import nobo
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_AUTO_DISCOVERED,
    CONF_OVERRIDE_TYPE,
    CONF_SERIAL,
    DOMAIN,
    OVERRIDE_TYPE_CONSTANT,
    OVERRIDE_TYPE_NOW,
)

DATA_NOBO_HUB_IMPL = "nobo_hub_flow_implementation"
DEVICE_INPUT = "device_input"


class NoboHubConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nobø Ecohub."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._discovered_hubs = None
        self._hub = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if self._discovered_hubs is None:
            self._discovered_hubs = dict(await nobo.async_discover_hubs())

        if not self._discovered_hubs:
            # No hubs auto discovered
            return await self.async_step_manual()

        if user_input is not None:
            if user_input["device"] == "manual":
                return await self.async_step_manual()
            self._hub = user_input["device"]
            return await self.async_step_selected()

        hubs = self._hubs()
        hubs["manual"] = "Manual"
        data_schema = vol.Schema(
            {
                vol.Required("device"): vol.In(hubs),
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
        )

    async def async_step_selected(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle configuration of a selected discovered device."""
        errors = {}
        if user_input is not None:
            serial_prefix = self._discovered_hubs[self._hub]
            serial_suffix = user_input["serial_suffix"]
            serial = f"{serial_prefix}{serial_suffix}"
            try:
                return await self._create_configuration(serial, self._hub, True)
            except NoboHubConnectError as error:
                errors["base"] = error.msg

        user_input = user_input or {}
        return self.async_show_form(
            step_id="selected",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "serial_suffix", default=user_input.get("serial_suffix")
                    ): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "hub": self._format_hub(self._hub, self._discovered_hubs[self._hub])
            },
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle configuration of an undiscovered device."""
        errors = {}
        if user_input is not None:
            serial = user_input[CONF_SERIAL]
            ip_address = user_input[CONF_IP_ADDRESS]
            try:
                return await self._create_configuration(serial, ip_address, False)
            except NoboHubConnectError as error:
                errors["base"] = error.msg

        user_input = user_input or {}
        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SERIAL, default=user_input.get(CONF_SERIAL)): str,
                    vol.Required(
                        CONF_IP_ADDRESS, default=user_input.get(CONF_IP_ADDRESS)
                    ): str,
                }
            ),
            errors=errors,
        )

    async def _create_configuration(
        self, serial: str, ip_address: str, auto_discovered: bool
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(serial)
        self._abort_if_unique_id_configured()
        name = await self._test_connection(serial, ip_address)
        return self.async_create_entry(
            title=name,
            data={
                CONF_SERIAL: serial,
                CONF_IP_ADDRESS: ip_address,
                CONF_AUTO_DISCOVERED: auto_discovered,
            },
        )

    async def _test_connection(self, serial: str, ip_address: str) -> str:
        if not len(serial) == 12 or not serial.isdigit():
            raise NoboHubConnectError("invalid_serial")
        try:
            socket.inet_aton(ip_address)
        except OSError as err:
            raise NoboHubConnectError("invalid_ip") from err
        hub = nobo(serial=serial, ip=ip_address, discover=False, synchronous=False)
        if not await hub.async_connect_hub(ip_address, serial):
            raise NoboHubConnectError("cannot_connect")
        name = hub.hub_info["name"]
        await hub.close()
        return name

    @staticmethod
    def _format_hub(ip, serial_prefix):
        return f"{serial_prefix}XXX ({ip})"

    def _hubs(self):
        return {
            ip: self._format_hub(ip, serial_prefix)
            for ip, serial_prefix in self._discovered_hubs.items()
        }

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class NoboHubConnectError(HomeAssistantError):
    """Error with connecting to Nobø Ecohub."""

    def __init__(self, msg) -> None:
        """Instantiate error."""
        super().__init__()
        self.msg = msg


class OptionsFlowHandler(OptionsFlow):
    """Handles options flow for the component."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        """Manage the options."""

        if user_input is not None:
            data = {
                CONF_OVERRIDE_TYPE: user_input.get(CONF_OVERRIDE_TYPE),
            }
            return self.async_create_entry(title="", data=data)

        override_type = self.config_entry.options.get(
            CONF_OVERRIDE_TYPE, OVERRIDE_TYPE_CONSTANT
        )

        schema = vol.Schema(
            {
                vol.Required(CONF_OVERRIDE_TYPE, default=override_type): vol.In(
                    [OVERRIDE_TYPE_CONSTANT, OVERRIDE_TYPE_NOW]
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
