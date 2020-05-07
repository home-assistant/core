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
ZEROCONF_GATEWAY = ("lumi-gateway")

GATEWAY_SETTINGS = {
    vol.Required(CONF_TOKEN): vol.All(str, vol.Length(min=32, max=32)),
    vol.Optional(CONF_NAME, default=DEFAULT_GATEWAY_NAME): str,
}

GATEWAY_CONFIG = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
).extend(GATEWAY_SETTINGS)

CONFIG_SCHEMA = vol.Schema({vol.Optional(CONF_GATEWAY, default=False): bool})


class XiaomiMiioFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Xiaomi Miio config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL


    def __init__(self):
        """Initialize."""
        self.host = None

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

    async def async_step_zeroconf(self, user_input=None):
        """Handle zeroconf discovery."""
        if user_input is None:
            return self.async_abort(reason="not_xiaomi_miio")

        name = user_input.get("name")
        self.host = user_input.get("host")
        mac_address = user_input.get("properties", {}).get("mac")

        if not name or not self.host or not mac_address:
            return self.async_abort(reason="not_xiaomi_miio")

        # Check which device is discovered.
        if name.startswith(ZEROCONF_GATEWAY):
            model = name.split("_")[0].replace("-", ".")
            
            unique_id = f"{model}-{mac_address}-gateway"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            
            return await self.async_step_gateway()

        # Discovered device is not yet supported
        return self.async_abort(reason="not_xiaomi_miio")

    async def async_step_gateway(self, user_input=None):
        """Handle a flow initialized by the user to configure a gateway."""
        errors = {}
        if user_input is not None:
            token = user_input[CONF_TOKEN]
            if user_input.get(CONF_HOST):
                self.host = user_input[CONF_HOST]
            
            if self.host:
                # Try to connect to a Xiaomi Gateway.
                connect_gateway_class = ConnectXiaomiGateway(self.hass)
                await connect_gateway_class.async_connect_gateway(self.host, token)
                gateway_info = connect_gateway_class.gateway_info

                if gateway_info is not None:
                    unique_id = f"{gateway_info.model}-{gateway_info.mac_address}-gateway"
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=user_input[CONF_NAME],
                        data={
                            CONF_FLOW_TYPE: CONF_GATEWAY,
                            CONF_HOST: self.host,
                            CONF_TOKEN: token,
                            "gateway_id": unique_id,
                            "model": gateway_info.model,
                            "mac": gateway_info.mac_address,
                        },
                    )

                errors["base"] = "connect_error"
            else:
                errors["base"] = "no_host"

        if self.host:
            return self.async_show_form(
                step_id="gateway", data_schema=vol.Schema(GATEWAY_SETTINGS), errors=errors
            )
        else:
            return self.async_show_form(
                step_id="gateway", data_schema=GATEWAY_CONFIG, errors=errors
            )
