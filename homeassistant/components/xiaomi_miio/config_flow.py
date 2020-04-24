"""Config flow to configure Xiaomi Miio."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TOKEN

# pylint: disable=unused-import
from .const import DOMAIN
from .gateway import ConnectXiaomiGateway

_LOGGER = logging.getLogger(__name__)

CONF_FLOW_TYPE = "config_flow_device"
CONF_GATEWAY = "gateway"
DEFAULT_GATEWAY_NAME = "Xiaomi Gateway"

GATEWAY_CONFIG = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_TOKEN): vol.All(str, vol.Length(min=32, max=32)),
        vol.Optional(CONF_NAME, default=DEFAULT_GATEWAY_NAME): str,
    }
)

CONFIG_SCHEMA = vol.Schema({vol.Optional(CONF_GATEWAY, default=False): bool})


class XiaomiMiioFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Xiaomi Miio config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            # Check which device needs to be connected.
            if user_input[CONF_GATEWAY]:
                return await self.async_step_gateway()

            errors["base"] = "no_device_selected"

        return self.async_show_form(
            step_id="user", data_schema=CONFIG_SCHEMA, errors=errors
        )

    async def async_step_gateway(self, user_input=None):
        """Handle a flow initialized by the user to configure a gateway."""
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            token = user_input[CONF_TOKEN]

            # Try to connect to a Xiaomi Gateway.
            connect_gateway_class = ConnectXiaomiGateway(self.hass)
            await connect_gateway_class.async_connect_gateway(host, token)
            gateway_info = connect_gateway_class.gateway_info

            if gateway_info is not None:
                unique_id = f"{gateway_info.model}-{gateway_info.mac_address}-gateway"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={
                        CONF_FLOW_TYPE: CONF_GATEWAY,
                        CONF_HOST: host,
                        CONF_TOKEN: token,
                        "gateway_id": unique_id,
                        "model": gateway_info.model,
                        "mac": gateway_info.mac_address,
                    },
                )

            errors["base"] = "connect_error"

        return self.async_show_form(
            step_id="gateway", data_schema=GATEWAY_CONFIG, errors=errors
        )
