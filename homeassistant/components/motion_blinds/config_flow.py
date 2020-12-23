"""Config flow to configure Motion Blinds using their WLAN API."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_HOST

# pylint: disable=unused-import
from .const import DEFAULT_GATEWAY_NAME, DOMAIN
from .gateway import ConnectMotionGateway

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
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

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            self.host = user_input[CONF_HOST]
            self.key = user_input[CONF_API_KEY]
            return await self.async_step_connect()

        return self.async_show_form(
            step_id="user", data_schema=CONFIG_SCHEMA, errors=errors
        )

    async def async_step_connect(self, user_input=None):
        """Connect to the Motion Gateway."""

        connect_gateway_class = ConnectMotionGateway(self.hass, None)
        if not await connect_gateway_class.async_connect_gateway(self.host, self.key):
            return self.async_abort(reason="connection_error")
        motion_gateway = connect_gateway_class.gateway_device

        mac_address = motion_gateway.mac

        await self.async_set_unique_id(mac_address)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=DEFAULT_GATEWAY_NAME,
            data={CONF_HOST: self.host, CONF_API_KEY: self.key},
        )
