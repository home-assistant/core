"""Config flow to configure Motion Blinds using their WLAN API."""
from socket import gaierror

from motionblinds import AsyncMotionMulticast, MotionDiscovery
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import dhcp, network
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.device_registry import format_mac

from .const import (
    CONF_INTERFACE,
    CONF_WAIT_FOR_PUSH,
    DEFAULT_GATEWAY_NAME,
    DEFAULT_INTERFACE,
    DEFAULT_WAIT_FOR_PUSH,
    DOMAIN,
)
from .gateway import ConnectMotionGateway

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOST): str,
    }
)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options for the component."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Init object."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        errors = {}
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        settings_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_WAIT_FOR_PUSH,
                    default=self.config_entry.options.get(
                        CONF_WAIT_FOR_PUSH, DEFAULT_WAIT_FOR_PUSH
                    ),
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=settings_schema, errors=errors
        )


class MotionBlindsFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Motion Blinds config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize the Motion Blinds flow."""
        self._host = None
        self._ips = []
        self._config_settings = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlowHandler:
        """Get the options flow."""
        return OptionsFlowHandler(config_entry)

    async def async_step_dhcp(self, discovery_info: dhcp.DhcpServiceInfo) -> FlowResult:
        """Handle discovery via dhcp."""
        mac_address = format_mac(discovery_info.macaddress).replace(":", "")
        await self.async_set_unique_id(mac_address)
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.ip})

        short_mac = mac_address[-6:].upper()
        self.context["title_placeholders"] = {
            "short_mac": short_mac,
            "ip_address": discovery_info.ip,
        }

        self._host = discovery_info.ip
        return await self.async_step_connect()

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            self._host = user_input.get(CONF_HOST)

            if self._host is not None:
                return await self.async_step_connect()

            # Use MotionGateway discovery
            discover_class = MotionDiscovery()
            gateways = await self.hass.async_add_executor_job(discover_class.discover)
            self._ips = list(gateways)

            if len(self._ips) == 1:
                self._host = self._ips[0]
                return await self.async_step_connect()

            if len(self._ips) > 1:
                return await self.async_step_select()

            errors["base"] = "discovery_error"

        return self.async_show_form(
            step_id="user", data_schema=CONFIG_SCHEMA, errors=errors
        )

    async def async_step_select(self, user_input=None):
        """Handle multiple motion gateways found."""
        if user_input is not None:
            self._host = user_input["select_ip"]
            return await self.async_step_connect()

        select_schema = vol.Schema({vol.Required("select_ip"): vol.In(self._ips)})

        return self.async_show_form(step_id="select", data_schema=select_schema)

    async def async_step_connect(self, user_input=None):
        """Connect to the Motion Gateway."""
        errors = {}
        if user_input is not None:
            key = user_input[CONF_API_KEY]
            multicast_interface = user_input[CONF_INTERFACE]

            # check socket interface
            if multicast_interface != DEFAULT_INTERFACE:
                motion_multicast = AsyncMotionMulticast(interface=multicast_interface)
                try:
                    await motion_multicast.Start_listen()
                    motion_multicast.Stop_listen()
                except gaierror:
                    errors[CONF_INTERFACE] = "invalid_interface"
                    return self.async_show_form(
                        step_id="connect",
                        data_schema=self._config_settings,
                        errors=errors,
                    )

            connect_gateway_class = ConnectMotionGateway(self.hass, multicast=None)
            if not await connect_gateway_class.async_connect_gateway(self._host, key):
                return self.async_abort(reason="connection_error")
            motion_gateway = connect_gateway_class.gateway_device

            mac_address = motion_gateway.mac

            await self.async_set_unique_id(mac_address, raise_on_progress=False)
            self._abort_if_unique_id_configured(
                updates={
                    CONF_HOST: self._host,
                    CONF_API_KEY: key,
                    CONF_INTERFACE: multicast_interface,
                }
            )

            return self.async_create_entry(
                title=DEFAULT_GATEWAY_NAME,
                data={
                    CONF_HOST: self._host,
                    CONF_API_KEY: key,
                    CONF_INTERFACE: multicast_interface,
                },
            )

        (interfaces, default_interface) = await self.async_get_interfaces()

        self._config_settings = vol.Schema(
            {
                vol.Required(CONF_API_KEY): vol.All(str, vol.Length(min=16, max=16)),
                vol.Optional(CONF_INTERFACE, default=default_interface): vol.In(
                    interfaces
                ),
            }
        )

        return self.async_show_form(
            step_id="connect", data_schema=self._config_settings, errors=errors
        )

    async def async_get_interfaces(self):
        """Get list of interface to use."""
        interfaces = [DEFAULT_INTERFACE, "0.0.0.0"]
        enabled_interfaces = []
        default_interface = DEFAULT_INTERFACE

        adapters = await network.async_get_adapters(self.hass)
        for adapter in adapters:
            if ipv4s := adapter["ipv4"]:
                ip4 = ipv4s[0]["address"]
                interfaces.append(ip4)
                if adapter["enabled"]:
                    enabled_interfaces.append(ip4)
                    if adapter["default"]:
                        default_interface = ip4

        if len(enabled_interfaces) == 1:
            default_interface = enabled_interfaces[0]

        return (interfaces, default_interface)
