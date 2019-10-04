"""Config flow for Glances Client."""
from glances_api import exceptions
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import callback

from . import GlancesClient
from .const import (
    CONF_VERSION,
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_VERSION,
    DOMAIN,
    SUPPORTED_VERSIONS,
)


class GlancesFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Glances config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return GlancesOptionsFlowHandler(config_entry)

    def __init__(self):
        """Initialize the Glances flow."""
        # self.config = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:

            for entry in self._async_current_entries():
                if entry.data[CONF_HOST] == user_input[CONF_HOST]:
                    return self.async_abort(reason="already_configured")

            if user_input[CONF_VERSION] not in SUPPORTED_VERSIONS:
                errors[CONF_VERSION] = "wrong_version"

            if not errors:
                try:
                    api = GlancesClient(self.hass, **user_input)
                    await api.get_data()
                    return self.async_create_entry(
                        title=user_input[CONF_NAME], data=user_input
                    )
                except exceptions.GlancesApiConnectionError:
                    errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                    vol.Optional(CONF_USERNAME): str,
                    vol.Optional(CONF_PASSWORD): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                    vol.Required(CONF_VERSION, default=DEFAULT_VERSION): int,
                    vol.Optional(CONF_SSL, default=False): bool,
                    vol.Optional(CONF_VERIFY_SSL, default=False): bool,
                }
            ),
            errors=errors,
        )


class GlancesOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Glances client options."""

    def __init__(self, config_entry):
        """Initialize Glances options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the Glances options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=self.config_entry.options.get(CONF_SCAN_INTERVAL),
            ): int
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))
