"""Config flow for IHC integration."""
import logging

from ihcsdk.ihccontroller import IHCController
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow

from . import get_options_value
from .const import CONF_AUTOSETUP, CONF_INFO, CONF_USE_GROUPS, DOMAIN
from .util import get_controller_serial

CONFIG_FLOW_VERSION = 1
_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL, default="http://192.168.1.3"): str,
        vol.Required(CONF_USERNAME, default=""): str,
        vol.Required(CONF_PASSWORD, default=""): str,
        vol.Optional(CONF_AUTOSETUP, default=True): bool,
        vol.Optional(CONF_USE_GROUPS, default=True): bool,
    }
)


def dovalidate(hass: HomeAssistant, user_input) -> str:
    """Validate the user input.

    Return the IHC controller serial number
    """
    url = user_input[CONF_URL]
    username = user_input[CONF_USERNAME]
    password = user_input[CONF_PASSWORD]
    # Do we have an IHC controller on this url
    if not IHCController.is_ihc_controller(url):
        raise CannotConnect()
    ihc_controller = IHCController(url, username, password)
    try:
        if not ihc_controller.authenticate():
            raise InvalidAuth()
        serial = get_controller_serial(ihc_controller)
    finally:
        ihc_controller.disconnect()
    return serial


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for IHC."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                serialnumber = await self.hass.async_add_executor_job(
                    dovalidate, self.hass, user_input
                )
                await self.async_set_unique_id(serialnumber)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="IHC Controller", data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except AbortFlow:
                errors["base"] = "already_setup"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """IHC options flow handler."""
        return OptionsFlowHandler(config_entry)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate we cannot authenticate."""


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Flow handle for IHC controller options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self._get_options_schema(),
        )

    def _get_options_schema(self):
        return vol.Schema(
            {
                vol.Optional(
                    CONF_INFO,
                    default=get_options_value(self.config_entry, CONF_INFO, True),
                ): bool,
            }
        )
