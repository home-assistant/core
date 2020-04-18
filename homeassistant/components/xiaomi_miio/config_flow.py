"""Config flow to configure Xiaomi Miio."""
import logging

from miio import DeviceException, gateway
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TOKEN

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

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

    def __init__(self):
        """Initialize the Xiaomi Miio flow."""
        self._gateway = None
        self._gateway_info = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            # Check which device needs to be connected.
            if user_input.get(CONF_GATEWAY):
                return self.async_show_form(
                    step_id="gateway", data_schema=GATEWAY_CONFIG
                )

            errors["base"] = "no_device_selected"

        return self.async_show_form(
            step_id="user", data_schema=CONFIG_SCHEMA, errors=errors
        )

    async def async_step_gateway(self, user_input=None):
        """Handle a flow initialized by the user to configure a gateway."""
        errors = {}
        host = user_input.get(CONF_HOST)
        token = user_input.get(CONF_TOKEN)
        if user_input is not None and host is not None and token is not None:
            # Try to connect to a Xiaomi Gateway.
            _LOGGER.info("Initializing with host %s (token %s...)", host, token[:5])

            try:
                self._gateway = gateway.Gateway(host, token)
                self._gateway_info = self._gateway.info()
                _LOGGER.info(
                    "%s %s %s detected",
                    self._gateway_info.model,
                    self._gateway_info.firmware_version,
                    self._gateway_info.hardware_version,
                )

                unique_id = "{}-{}-gateway".format(
                    self._gateway_info.model, self._gateway_info.mac_address
                )
                await self.async_set_unique_id(unique_id)
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME),
                    data={
                        CONF_HOST: host,
                        CONF_TOKEN: token,
                        "gateway_id": unique_id,
                        "model": self._gateway_info.model,
                        "mac": self._gateway_info.mac_address,
                    },
                )

            except DeviceException:
                _LOGGER.error(
                    "DeviceException during setup of xiaomi gateway with host %s", host
                )

            errors["base"] = "connect_error"

        return self.async_show_form(
            step_id="gateway", data_schema=GATEWAY_CONFIG, errors=errors
        )
