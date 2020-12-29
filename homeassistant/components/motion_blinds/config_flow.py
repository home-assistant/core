"""Config flow to configure Motion Blinds using their WLAN API."""
import logging

from motionblinds import MotionDiscovery
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_HOST

# pylint: disable=unused-import
from .const import DEFAULT_GATEWAY_NAME, DOMAIN
from .gateway import ConnectMotionGateway

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOST): str,
    }
)

CONFIG_SETTINGS = vol.Schema(
    {
        vol.Required(CONF_API_KEY): vol.All(str, vol.Length(min=16, max=16)),
    }
)


class MotionBlindsFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Motion Blinds config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize the Motion Blinds flow."""
        self.host = None
        self.key = None
        self.ips = []

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            self.host = user_input.get(CONF_HOST)

            if self.host is not None:
                return await self.async_step_connect()

            # Use MotionGateway discovery
            discover_class = MotionDiscovery()
            gateways = await self.hass.async_add_executor_job(discover_class.discover)
            self.ips = list(gateways)

            if len(self.ips) == 1:
                self.host = self.ips[0]
                return await self.async_step_connect()

            if len(self.ips) > 1:
                return await self.async_step_select()

            errors["base"] = "discovery_error"

        return self.async_show_form(
            step_id="user", data_schema=CONFIG_SCHEMA, errors=errors
        )

    async def async_step_select(self, user_input=None):
        """Handle multiple motion gateways found."""
        errors = {}
        if user_input is not None:
            self.host = user_input["select_ip"]
            return await self.async_step_connect()

        select_schema = vol.Schema({vol.Required("select_ip"): vol.In(self.ips)})

        return self.async_show_form(
            step_id="select", data_schema=select_schema, errors=errors
        )

    async def async_step_connect(self, user_input=None):
        """Connect to the Motion Gateway."""
        errors = {}
        if user_input is not None:
            self.key = user_input[CONF_API_KEY]

            connect_gateway_class = ConnectMotionGateway(self.hass, None)
            if not await connect_gateway_class.async_connect_gateway(
                self.host, self.key
            ):
                return self.async_abort(reason="connection_error")
            motion_gateway = connect_gateway_class.gateway_device

            mac_address = motion_gateway.mac

            await self.async_set_unique_id(mac_address)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=DEFAULT_GATEWAY_NAME,
                data={CONF_HOST: self.host, CONF_API_KEY: self.key},
            )

        return self.async_show_form(
            step_id="connect", data_schema=CONFIG_SETTINGS, errors=errors
        )
