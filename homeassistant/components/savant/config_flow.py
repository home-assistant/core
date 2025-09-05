"""Config flow for the Savant Home Automation integration."""

import logging
import typing

from pysavant.switch import AudioSwitch, Switch, VideoSwitch
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import SOURCE_RECONFIGURE, ConfigFlowResult
from homeassistant.data_entry_flow import section
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.selector import selector
from homeassistant.util.network import is_ipv4_address, is_ipv6_address

from .const import DOMAIN

logger = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required("name"): str,
        vol.Required("ip"): str,
        vol.Required("type"): selector({"select": {"options": ["Audio", "Video"]}}),
    }
)


class SavantConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Example config flow."""

    # The schema version of the entries that it creates
    # Home Assistant will call your migrate method if the version changes
    VERSION = 1
    MINOR_VERSION = 1

    input_state: dict[str, typing.Any]
    output_state: dict[str, typing.Any]
    entry_data: dict[str, typing.Any]

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """User input step - takes the ip address, name, and type (audio/video) of the switch."""
        errors = {}
        if user_input is not None:
            ip = user_input.get("ip", "")
            if is_ipv4_address(ip) or is_ipv6_address(ip):
                switch = Switch(ip)
                switch_info = await switch.get_info()
                identifier = switch_info["savantID"]
                await self.async_set_unique_id(identifier)
                self._abort_if_unique_id_configured()
                self.entry_data = {
                    "ip": ip,
                    "name": user_input["name"],
                    "type": user_input["type"],
                }

                return await self.async_step_ports()
            logger.error("%s is not an ip", ip)
            errors["invalid_ip"] = "Invalid IP address"

        return self.async_show_form(
            step_id="user",
            data_schema=USER_SCHEMA,
            errors=errors,
        )

    async def async_step_ports(self, user_input=None) -> ConfigFlowResult:
        """Port definition step - provide names for zones and sources."""
        match self.entry_data["type"]:
            case "Audio":
                switch = AudioSwitch(self.entry_data["ip"])
            case "Video":
                switch = VideoSwitch(self.entry_data["ip"])
            case _:
                raise ConfigEntryError

        switch_state = await switch.get_switch_state()
        self.input_state = switch_state["inputs"]
        self.output_state = switch_state["outputs"]

        if user_input is not None:
            self.entry_data["inputs"] = user_input["inputs"]
            self.entry_data["outputs"] = user_input["outputs"]

            if self.source == SOURCE_RECONFIGURE:
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data_updates=self.entry_data,
                )
            return self.async_create_entry(
                title=self.entry_data["name"],
                data=self.entry_data,
            )

        return self.async_show_form(
            step_id="ports",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required("inputs"): section(
                            vol.Schema(
                                {
                                    vol.Optional(str(port["port"])): str
                                    for port in self.input_state
                                }
                            )
                        ),
                        vol.Required("outputs"): section(
                            vol.Schema(
                                {
                                    vol.Optional(str(port["port"])): str
                                    for port in self.output_state
                                }
                            )
                        ),
                    }
                ),
                self._get_reconfigure_entry().data
                if self.source == SOURCE_RECONFIGURE
                else {},
            ),
        )

    async def async_step_reconfigure(self, user_input=None) -> ConfigFlowResult:
        """Reconfiguration step - allows for all parameters except switch type to be changed."""
        errors = {}
        config_entry = self._get_reconfigure_entry()
        if user_input is not None:
            ip = user_input.get("ip", "")
            if is_ipv4_address(ip) or is_ipv6_address(ip):
                switch = Switch(ip)
                switch_info = await switch.get_info()
                identifier = switch_info["savantID"]
                await self.async_set_unique_id(identifier)
                self._abort_if_unique_id_mismatch()

                self.entry_data = {
                    "ip": ip,
                    "name": user_input["name"],
                    "type": config_entry.data["type"],
                }

                return await self.async_step_ports()
            logger.error("%s is not an ip", ip)
            errors["invalid_ip"] = "Invalid IP address"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema({vol.Required("name"): str, vol.Required("ip"): str}),
                config_entry.data,
            ),
            errors=errors,
        )
