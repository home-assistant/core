"""Config flow to configure Xiaomi Aqara."""
import logging
from socket import gaierror

import voluptuous as vol
from xiaomi_gateway import XiaomiGatewayDiscovery

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME, CONF_PORT
from homeassistant.helpers.device_registry import format_mac

# pylint: disable=unused-import
from .const import (
    CONF_INTERFACE,
    CONF_KEY,
    CONF_PROTOCOL,
    CONF_SID,
    DOMAIN,
    ZEROCONF_GATEWAY,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_GATEWAY_NAME = "Xiaomi Aqara Gateway"
DEFAULT_INTERFACE = "any"


GATEWAY_CONFIG = vol.Schema(
    {vol.Optional(CONF_INTERFACE, default=DEFAULT_INTERFACE): str}
)
GATEWAY_SETTINGS = vol.Schema(
    {
        vol.Optional(CONF_KEY): vol.All(str, vol.Length(min=16, max=16)),
        vol.Optional(CONF_NAME, default=DEFAULT_GATEWAY_NAME): str,
    }
)


class XiaomiAqaraFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Xiaomi Aqara config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize."""
        self.host = None
        self.interface = DEFAULT_INTERFACE
        self.gateways = None
        self.selected_gateway = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            self.interface = user_input[CONF_INTERFACE]

            # Discover Xiaomi Aqara Gateways in the netwerk to get required SIDs.
            xiaomi = XiaomiGatewayDiscovery(self.hass.add_job, [], self.interface)
            try:
                await self.hass.async_add_executor_job(xiaomi.discover_gateways)
            except gaierror:
                errors[CONF_INTERFACE] = "invalid_interface"

            if not errors:
                self.gateways = xiaomi.gateways

                # if host is already known by zeroconf discovery
                if self.host is not None:
                    self.selected_gateway = self.gateways.get(self.host)
                    if self.selected_gateway is not None:
                        return await self.async_step_settings()

                    errors["base"] = "not_found_error"
                else:
                    if len(self.gateways) == 1:
                        self.selected_gateway = list(self.gateways.values())[0]
                        return await self.async_step_settings()
                    if len(self.gateways) > 1:
                        return await self.async_step_select()

                    errors["base"] = "discovery_error"

        return self.async_show_form(
            step_id="user", data_schema=GATEWAY_CONFIG, errors=errors
        )

    async def async_step_select(self, user_input=None):
        """Handle multiple aqara gateways found."""
        errors = {}
        if user_input is not None:
            ip_adress = user_input["select_ip"]
            self.selected_gateway = self.gateways[ip_adress]
            return await self.async_step_settings()

        select_schema = vol.Schema(
            {
                vol.Required("select_ip"): vol.In(
                    [gateway.ip_adress for gateway in self.gateways.values()]
                )
            }
        )

        return self.async_show_form(
            step_id="select", data_schema=select_schema, errors=errors
        )

    async def async_step_zeroconf(self, discovery_info):
        """Handle zeroconf discovery."""
        name = discovery_info.get("name")
        self.host = discovery_info.get("host")
        mac_address = discovery_info.get("properties", {}).get("mac")

        if not name or not self.host or not mac_address:
            return self.async_abort(reason="not_xiaomi_aqara")

        # Check if the discovered device is an xiaomi aqara gateway.
        if not name.startswith(ZEROCONF_GATEWAY):
            _LOGGER.debug(
                "Xiaomi device '%s' discovered with host %s, not identified as xiaomi aqara gateway",
                name,
                self.host,
            )
            return self.async_abort(reason="not_xiaomi_aqara")

        # format mac (include semicolns and make uppercase)
        mac_address = format_mac(mac_address)

        unique_id = mac_address
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured({CONF_HOST: self.host})

        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        self.context.update({"title_placeholders": {"name": self.host}})

        return await self.async_step_user()

    async def async_step_settings(self, user_input=None):
        """Specify settings and connect aqara gateway."""
        errors = {}
        if user_input is not None:
            # get all required data
            name = user_input[CONF_NAME]
            key = user_input.get(CONF_KEY)
            ip_adress = self.selected_gateway.ip_adress
            port = self.selected_gateway.port
            sid = self.selected_gateway.sid
            protocol = self.selected_gateway.proto

            if key is not None:
                # validate key by issuing stop ringtone playback command.
                self.selected_gateway.key = key
                valid_key = self.selected_gateway.write_to_hub(sid, mid=10000)
            else:
                valid_key = True

            if valid_key:
                # format_mac, for a gateway the sid equels the mac address
                mac_address = format_mac(sid)

                # set unique_id
                unique_id = mac_address
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_HOST: ip_adress,
                        CONF_PORT: port,
                        CONF_MAC: mac_address,
                        CONF_INTERFACE: self.interface,
                        CONF_PROTOCOL: protocol,
                        CONF_KEY: key,
                        CONF_SID: sid,
                    },
                )

            errors[CONF_KEY] = "invalid_key"

        return self.async_show_form(
            step_id="settings", data_schema=GATEWAY_SETTINGS, errors=errors
        )
