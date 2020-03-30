"""Config flow for BleBox devices integration."""
import logging

from blebox_uniapi.error import Error, UnsupportedBoxVersion
from blebox_uniapi.products import Products
from blebox_uniapi.session import ApiHost
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    ALREADY_CONFIGURED,
    CANNOT_CONNECT,
    DEFAULT_SETUP_TIMEOUT,
    DOMAIN,
    UNKNOWN,
    UNSUPPORTED_VERSION,
)

DEFAULT_HOST = "192.168.0.2"
DEFAULT_PORT = 80

_LOGGER = logging.getLogger(__name__)


def host_port(data):
    """Return a list with host and port."""
    return (data[CONF_HOST], data[CONF_PORT])


def create_schema(previous_input=None):
    """Create a schema with given values as default."""
    if previous_input is not None:
        host, port = host_port(previous_input)
    else:
        host = DEFAULT_HOST
        port = DEFAULT_PORT

    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=host): str,
            vol.Required(CONF_PORT, default=port): int,
        }
    )


LOG_MSG = {
    UNSUPPORTED_VERSION: "Outdated firmware",
    CANNOT_CONNECT: "Failed to identify device",
    UNKNOWN: "Unknown error while identifying device",
}


class BleBoxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BleBox devices."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the BleBox config flow."""
        self.device_config = {}

    def handle(self, step, exception, schema, addr, message_id):
        """Handle step exceptions."""

        _LOGGER.error("%s at %s:%d (%s)", LOG_MSG[message_id], *addr, exception)

        address = "{0}:{1}".format(*addr)
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors={"base": message_id},
            description_placeholders={"address": address},
        )

    def abort_because_configured(self, addr):
        """Return abort flow response for when already configured."""

        address = "{0}:{1}".format(*addr)
        return self.async_abort(
            reason=ALREADY_CONFIGURED, description_placeholders={"address": address},
        )

    async def async_step_user(self, user_input=None):
        """Handle initial user-triggered config step."""

        hass = self.hass
        schema = create_schema(user_input)

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=schema,
                errors={},
                description_placeholders={},
            )

        addr = host_port(user_input)

        for entry in hass.config_entries.async_entries(DOMAIN):
            if addr == host_port(entry.data):
                return self.abort_because_configured(addr)

        websession = async_get_clientsession(hass)
        api_host = ApiHost(*addr, DEFAULT_SETUP_TIMEOUT, websession, hass.loop, _LOGGER)

        try:
            product = await Products.async_from_host(api_host)

        except UnsupportedBoxVersion as ex:
            return self.handle("user", ex, schema, addr, UNSUPPORTED_VERSION)

        except Error as ex:
            return self.handle("user", ex, schema, addr, CANNOT_CONNECT)

        except RuntimeError as ex:
            return self.handle("user", ex, schema, addr, UNKNOWN)

        # Check if configured but IP changed since
        await self.async_set_unique_id(product.unique_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=product.name, data=user_input)
