"""Config flow to configure Xiaomi Aqara."""
import logging

import voluptuous as vol

from getmac import get_mac_address
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT, CONF_NAME

_LOGGER = logging.getLogger(__name__)

DOMAIN = "xiaomi_aqara"

CONF_DISCOVERY_RETRY = "discovery_retry"
CONF_INTERFACE = "interface"
CONF_PROTOCOL = "protocol"
CONF_KEY = "key"
CONF_SID = "sid"

DEFAULT_GATEWAY_NAME = "Xiaomi Aqara Gateway"
DEFAULT_INTERFACE = "any"
DEFAULT_DISCOVERY_RETRY = 3
ZEROCONF_GATEWAY = "lumi-gateway"


GATEWAY_CONFIG =  = vol.Schema(
    {
        vol.Optional(CONF_INTERFACE, default=DEFAULT_INTERFACE): str,
    }
)
GATEWAY_SETTINGS = vol.Schema(
    {
        vol.Optional(CONF_KEY): vol.All(str, vol.Length(min=16, max=16)),
        vol.Optional(CONF_DISCOVERY_RETRY, default=DEFAULT_DISCOVERY_RETRY): vol.All(int, vol.Range(min=1)),
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
            xiaomi.discover_gateways()
            self.gateways = xiaomi.gateways
            
            # if host is already known by zeroconf discovery
            if self.host is not None:
                self.selected_gateway = self.gateways.get(self.host)
                if self.selected_gateway is not None:
                    return await self.async_step_settings()

                errors["base"] = "not_found_error"
            else:
                if len(self.gateways)==1:
                    self.selected_gateway = list(self.gateways.values())[0]
                    return await self.async_step_settings()
                if len(self.gateways)>1:
                    return await self.async_step_select()

                errors["base"] = "discovery_error"

        return self.async_show_form(
            step_id="user", data_schema=GATEWAY_CONFIG, errors=errors
        )

    async def async_step_select(self, user_input=None):
        """Handle multiple aqara gateways found."""
        errors = {}
        if user_input is not None:
            ip = user_input["select_ip"]
            self.selected_gateway = self.gateways[ip]
            return await self.async_step_settings()

        select_scheme = vol.Schema(
            {
                vol.Required("select_ip"): vol.In(
                    [gateway.ip_adress for gateway in self.gateways]
                )
            }
        )

        return self.async_show_form(
            step_id="select", data_schema=select_scheme, errors=errors
        )

    async def async_step_zeroconf(self, user_input=None):
        """Handle zeroconf discovery."""
        if user_input is None:
            return self.async_abort(reason="not_xiaomi_aqara")

        name = user_input.get("name")
        self.host = user_input.get("host")
        mac_address = user_input.get("properties", {}).get("mac")

        if not name or not self.host or not mac_address:
            return self.async_abort(reason="not_xiaomi_aqara")

        # format mac (include semicolns and make uppercase)
        if len(mac_address) == 12:
            mac_address = ":".join(mac_address[i : i + 2] for i in range(0, 12, 2))
        mac_address = mac_address.upper()

        # Check if the discovered device is an xiaomi aqara gateway.
        if not name.startswith(ZEROCONF_GATEWAY):
            _LOGGER.debug(
                "Xiaomi device '%s' discovered with host %s, not identified as xiaomi aqara gateway",
                name,
                self.host,
            )
            return self.async_abort(reason="not_xiaomi_aqara")

        unique_id = f"aqara-gateway-{mac_address}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return await self.async_step_user()


    async def async_step_settings(self, user_input=None):
        """Specify settings and connect aqara gateway."""
        errors = {}
        if user_input is not None:
            # get all required data
            discovery_retry = user_input[CONF_DISCOVERY_RETRY]
            name = user_input[CONF_NAME]
            key = user_input.get(CONF_KEY)
            ip = self.selected_gateway.ip_adress
            port = self.selected_gateway.port
            sid = self.selected_gateway.sid
            protocol = self.selected_gateway.proto
            
            # get mac address
            mac_address = await self.async_get_mac(ip)
            
            if mac_address is not None:
                # set unique_id
                unique_id = f"aqara-gateway-{mac_address}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_HOST: ip,
                        CONF_PORT: port
                        CONF_MAC: mac_address,
                        CONF_INTERFACE: self.interface,
                        CONF_DISCOVERY_RETRY: discovery_retry,
                        CONF_PROTOCOL: protocol,
                        CONF_KEY: key,
                        CONF_SID: sid,
                    },
                )

            errors["base"] = "get_mac_error"

        return self.async_show_form(
            step_id="settings", data_schema=GATEWAY_SETTINGS, errors=errors
        )

    async def async_get_mac(self, ip):
        """Get the mac address of the Xiaomi Aqara Gateway."""
        mac_address = await self.hass.async_add_executor_job(
            partial(get_mac_address, **{"ip": ip})
        )
        if mac_address is not None:
            mac_address = mac_address.upper()
        return mac_address