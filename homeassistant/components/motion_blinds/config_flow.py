"""Config flow to configure Motion Blinds using their WLAN API."""
from socket import gaierror

from motionblinds import MotionDiscovery
from motionblinds.motion_blinds import MotionCommunication
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import callback

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

CONFIG_SETTINGS = vol.Schema(
    {
        vol.Required(CONF_API_KEY): vol.All(str, vol.Length(min=16, max=16)),
        vol.Optional(CONF_INTERFACE, default=DEFAULT_INTERFACE): str,
    }
)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options for the component."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlowHandler:
        """Get the options flow."""
        return OptionsFlowHandler(config_entry)

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
            interface = user_input[CONF_INTERFACE]

            # check socket interface
            if interface != DEFAULT_INTERFACE:
                motion_com = MotionCommunication
                try:
                    sock = motion_com._create_mcast_socket(interface)
                    sock.close()
                except gaierror:
                    errors[CONF_INTERFACE] = "invalid_interface"
                    return self.async_show_form(
                        step_id="connect", data_schema=CONFIG_SETTINGS, errors=errors
                    )

            connect_gateway_class = ConnectMotionGateway(self.hass, multicast=None)
            if not await connect_gateway_class.async_connect_gateway(self._host, key):
                return self.async_abort(reason="connection_error")
            motion_gateway = connect_gateway_class.gateway_device

            mac_address = motion_gateway.mac

            await self.async_set_unique_id(mac_address)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=DEFAULT_GATEWAY_NAME,
                data={
                    CONF_HOST: self._host,
                    CONF_API_KEY: key,
                    CONF_INTERFACE: interface,
                },
            )

        return self.async_show_form(
            step_id="connect", data_schema=CONFIG_SETTINGS, errors=errors
        )
