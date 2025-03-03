"""Config flow to configure Xiaomi Aqara."""

import logging
from socket import gaierror
from typing import Any

import voluptuous as vol
from xiaomi_gateway import MULTICAST_PORT, XiaomiGateway, XiaomiGatewayDiscovery

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME, CONF_PORT, CONF_PROTOCOL
from homeassistant.core import callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import (
    CONF_INTERFACE,
    CONF_KEY,
    CONF_SID,
    DEFAULT_DISCOVERY_RETRY,
    DOMAIN,
    ZEROCONF_ACPARTNER,
    ZEROCONF_GATEWAY,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_GATEWAY_NAME = "Xiaomi Aqara Gateway"
DEFAULT_INTERFACE = "any"


GATEWAY_CONFIG = vol.Schema(
    {vol.Optional(CONF_INTERFACE, default=DEFAULT_INTERFACE): str}
)
CONFIG_HOST = {
    vol.Optional(CONF_HOST): str,
    vol.Optional(CONF_MAC): str,
}
GATEWAY_CONFIG_HOST = GATEWAY_CONFIG.extend(CONFIG_HOST)
GATEWAY_SETTINGS = vol.Schema(
    {
        vol.Optional(CONF_KEY): vol.All(str, vol.Length(min=16, max=16)),
        vol.Optional(CONF_NAME, default=DEFAULT_GATEWAY_NAME): str,
    }
)


class XiaomiAqaraFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Xiaomi Aqara config flow."""

    VERSION = 1

    selected_gateway: XiaomiGateway
    gateways: dict[str, XiaomiGateway]

    def __init__(self) -> None:
        """Initialize."""
        self.host: str | None = None
        self.interface = DEFAULT_INTERFACE
        self.sid: str | None = None

    @callback
    def async_show_form_step_user(self, errors):
        """Show the form belonging to the user step."""
        schema = GATEWAY_CONFIG
        if (self.host is None and self.sid is None) or errors:
            schema = GATEWAY_CONFIG_HOST

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input is None:
            return self.async_show_form_step_user(errors)

        self.interface = user_input[CONF_INTERFACE]

        # allow optional manual setting of host and mac
        if self.host is None:
            self.host = user_input.get(CONF_HOST)
        if self.sid is None:
            # format sid from mac_address
            if (mac_address := user_input.get(CONF_MAC)) is not None:
                self.sid = format_mac(mac_address).replace(":", "")

        # if host is already known by zeroconf discovery or manual optional settings
        if self.host is not None and self.sid is not None:
            # Connect to Xiaomi Aqara Gateway
            self.selected_gateway = await self.hass.async_add_executor_job(
                XiaomiGateway,
                self.host,
                self.sid,
                None,
                DEFAULT_DISCOVERY_RETRY,
                self.interface,
                MULTICAST_PORT,
                None,
            )

            if self.selected_gateway.connection_error:
                errors[CONF_HOST] = "invalid_host"
            if self.selected_gateway.mac_error:
                errors[CONF_MAC] = "invalid_mac"
            if errors:
                return self.async_show_form_step_user(errors)

            return await self.async_step_settings()

        # Discover Xiaomi Aqara Gateways in the network to get required SIDs.
        xiaomi = XiaomiGatewayDiscovery(self.interface)
        try:
            await self.hass.async_add_executor_job(xiaomi.discover_gateways)
        except gaierror:
            errors[CONF_INTERFACE] = "invalid_interface"
            return self.async_show_form_step_user(errors)

        self.gateways = xiaomi.gateways

        if len(self.gateways) == 1:
            self.selected_gateway = list(self.gateways.values())[0]
            self.sid = self.selected_gateway.sid
            return await self.async_step_settings()
        if len(self.gateways) > 1:
            return await self.async_step_select()

        errors["base"] = "discovery_error"
        return self.async_show_form_step_user(errors)

    async def async_step_select(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle multiple aqara gateways found."""
        errors: dict[str, str] = {}
        if user_input is not None:
            ip_adress = user_input["select_ip"]
            self.selected_gateway = self.gateways[ip_adress]
            self.sid = self.selected_gateway.sid
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

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        name = discovery_info.name
        self.host = discovery_info.host
        mac_address = discovery_info.properties.get("mac")

        if not name or not self.host or not mac_address:
            return self.async_abort(reason="not_xiaomi_aqara")

        # Check if the discovered device is an xiaomi aqara gateway.
        if not (name.startswith((ZEROCONF_GATEWAY, ZEROCONF_ACPARTNER))):
            _LOGGER.debug(
                (
                    "Xiaomi device '%s' discovered with host %s, not identified as"
                    " xiaomi aqara gateway"
                ),
                name,
                self.host,
            )
            return self.async_abort(reason="not_xiaomi_aqara")

        # format mac (include semicolns and make lowercase)
        mac_address = format_mac(mac_address)

        # format sid from mac_address
        self.sid = mac_address.replace(":", "")

        unique_id = mac_address
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(
            {CONF_HOST: self.host, CONF_MAC: mac_address}
        )

        self.context.update({"title_placeholders": {"name": self.host}})

        return await self.async_step_user()

    async def async_step_settings(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Specify settings and connect aqara gateway."""
        errors = {}
        if user_input is not None:
            # get all required data
            name = user_input[CONF_NAME]
            key = user_input.get(CONF_KEY)
            ip_adress = self.selected_gateway.ip_adress
            port = self.selected_gateway.port
            protocol = self.selected_gateway.proto

            if key is not None:
                # validate key by issuing stop ringtone playback command.
                self.selected_gateway.key = key
                valid_key = self.selected_gateway.write_to_hub(self.sid, mid=10000)
            else:
                valid_key = True

            if valid_key:
                # format_mac, for a gateway the sid equals the mac address
                mac_address = format_mac(self.sid)

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
                        CONF_SID: self.sid,
                    },
                )

            errors[CONF_KEY] = "invalid_key"

        return self.async_show_form(
            step_id="settings", data_schema=GATEWAY_SETTINGS, errors=errors
        )
