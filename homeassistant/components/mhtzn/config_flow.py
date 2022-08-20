"""Config flow for MHTZN integration."""
from __future__ import annotations

import logging
from collections import OrderedDict

import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.components import zeroconf
from homeassistant.data_entry_flow import FlowResult
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)

from .const import (
    DOMAIN, CONF_BROKER, CONF_LIGHT_DEVICE_TYPE
)
from .scan import scan_and_get_connection_dict
from .util import format_connection

connection_dict = {}
light_device_type = None
scan_flag = False
_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MHTZN."""

    VERSION = 1

    async def async_step_zeroconf(
            self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""
        global scan_flag

        """Format the connection information reported by mdns"""
        connection = format_connection(discovery_info)

        """Realize the change of gateway connection information and trigger HA to reconnect to the gateway"""
        for entry in self._async_current_entries():
            entry_data = entry.data
            if entry_data[CONF_NAME] == connection[CONF_NAME]:
                if CONF_LIGHT_DEVICE_TYPE in entry_data:
                    connection[CONF_LIGHT_DEVICE_TYPE] = entry_data[CONF_LIGHT_DEVICE_TYPE]
                self.hass.config_entries.async_update_entry(
                    entry,
                    data=connection,
                )

        """When an available gateway connection is found, the configuration card is displayed"""
        if (not self._async_current_entries()
                and not scan_flag
                and connection[CONF_NAME] is not None
                and connection[CONF_BROKER] is not None
                and connection[CONF_PORT] is not None
                and connection[CONF_USERNAME] is not None
                and connection[CONF_PASSWORD] is not None):
            scan_flag = True
            return await self.async_step_option()

        return self.async_abort(reason="single_instance_allowed")

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""

        """Only one integration instance is allowed to be added"""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return await self.async_step_option()

    async def async_step_option(self, user_input=None):
        """Configure the lighting control method"""

        global light_device_type
        errors = {}

        if user_input is not None:
            if user_input[CONF_LIGHT_DEVICE_TYPE] == "单灯":
                light_device_type = "single"
            else:
                light_device_type = "group"

            return await self.async_step_scan()

        fields = OrderedDict()
        fields[vol.Required(CONF_LIGHT_DEVICE_TYPE)] = vol.In(["单灯", "灯组"])

        return self.async_show_form(
            step_id="option",
            data_schema=vol.Schema(fields),
            errors=errors
        )

    async def async_step_scan(self, user_input=None):
        """Select a gateway from the list of discovered gateways to connect to"""
        global scan_flag
        global connection_dict
        global light_device_type
        errors = {}

        if user_input is not None:
            name = user_input[CONF_NAME]
            connection = connection_dict.get(name)
            if connection is not None:
                can_connect = self._try_mqtt_connect(connection)
                if can_connect:
                    connection[CONF_LIGHT_DEVICE_TYPE] = light_device_type
                    scan_flag = False
                    """Create an integration based on selected configuration information"""
                    return self.async_create_entry(
                        title=connection[CONF_NAME], data=connection
                    )
                else:
                    errors["base"] = "cannot_connect"
            else:
                return self.async_abort(reason="select_error")

        """Search the LAN's gateway list"""
        connection_dict = await scan_and_get_connection_dict(3)

        connection_name_list = []

        if connection_dict is not None:
            for connection_name in list(connection_dict.keys()):
                connection_name_list.append(connection_name)

        if len(connection_name_list) < 1:
            return self.async_abort(reason="not_found_device")

        fields = OrderedDict()
        fields[vol.Required(CONF_NAME)] = vol.In(connection_name_list)

        return self.async_show_form(
            step_id="scan", data_schema=vol.Schema(fields), errors=errors
        )

    def _try_mqtt_connect(self, connection):
        return self.hass.async_add_executor_job(
            try_connection,
            self.hass,
            connection[CONF_BROKER],
            connection[CONF_PORT],
            connection[CONF_USERNAME],
            connection[CONF_PASSWORD],
        )


def try_connection(hass, broker, port, username, password, protocol="3.1.1"):
    return True


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidHost(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid hostname."""
