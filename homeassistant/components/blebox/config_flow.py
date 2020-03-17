"""Config flow for BleBox devices integration."""
import logging

from blebox_uniapi.error import Error
from blebox_uniapi.products import Products
from blebox_uniapi.session import ApiHost
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .errors import CannotConnect

PLACEHOLDER_HOST = "192.168.0.2"
PLACEHOLDER_PORT = 80

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=PLACEHOLDER_HOST): str,
        vol.Required(CONF_PORT, default=PLACEHOLDER_PORT): int,
    }
)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    host = data[CONF_HOST]
    port = data[CONF_PORT]

    try:
        websession = async_get_clientsession(hass)
        api_host = ApiHost(host, port, None, websession, hass.loop, _LOGGER)
        product = await Products.async_from_host(api_host)

        # Return some info we want to store in the config entry.
        return {"title": product.name}
    except Error as ex:
        _LOGGER.error("validate input: likely failed to connect (%s)", ex)
        raise CannotConnect


class BleBoxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BleBox devices."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the BleBox config flow."""
        self.device_config = {}

    async def async_step_user(self, user_input=None):
        """Handle initial user-triggered config step."""

        errors = {}
        if user_input is not None:
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                if entry.data[CONF_HOST] == user_input[CONF_HOST]:
                    if entry.data[CONF_PORT] == user_input[CONF_PORT]:
                        return self.async_abort(reason="already_configured")

            try:
                info = await validate_input(self.hass, user_input)

                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except RuntimeError as ex:
                _LOGGER.exception("Unexpected exception: %s", ex)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors,
        )
