"""Config flow for Balboa Spa Client integration."""
from pybalboa import BalboaSpaWifi
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import callback

from .const import _LOGGER, CONF_SYNC_TIME, DOMAIN

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_HOST): str, vol.Required(CONF_NAME, default="Spa"): str}
)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data[CONF_HOST] == data[CONF_HOST]:
            raise AlreadyConfigured

    _LOGGER.debug("Attempting to connect to %s", data[CONF_HOST])
    spa = BalboaSpaWifi(data[CONF_HOST])
    connected = await spa.connect()
    _LOGGER.debug("Got connected = %d", connected)
    if not connected:
        raise CannotConnect
    await spa.disconnect()

    return {"title": data[CONF_NAME]}


class BalboaSpaClientFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Balboa Spa Client config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return BalboaSpaClientOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except AlreadyConfigured:
                return self.async_abort(reason="already_configured")
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class AlreadyConfigured(exceptions.HomeAssistantError):
    """Error to indicate this device is already configured."""


class BalboaSpaClientOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Balboa Spa Client options."""

    def __init__(self, config_entry):
        """Initialize Balboa Spa Client options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage Balboa Spa Client options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SYNC_TIME,
                        default=self.config_entry.options.get(CONF_SYNC_TIME, False),
                    ): bool,
                }
            ),
        )
