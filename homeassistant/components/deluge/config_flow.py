"""Config flow for Deluge Bittorent Client."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)

from . import get_client
from .const import (
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
)
from .errors import AuthenticationError, CannotConnect, UnknownError

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


class DelugeFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Deluge config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:

            for entry in self._async_current_entries():
                if (
                    entry.data[CONF_HOST] == user_input[CONF_HOST]
                    and entry.data[CONF_PORT] == user_input[CONF_PORT]
                ):
                    return self.async_abort(reason="already_configured")
                if entry.data[CONF_NAME] == user_input[CONF_NAME]:
                    errors[CONF_NAME] = "name_exists"
                    break
            try:
                await get_client(self.hass, user_input)

            except AuthenticationError:
                errors[CONF_USERNAME] = "invalid_auth"
                errors[CONF_PASSWORD] = "invalid_auth"
            except (CannotConnect, UnknownError):
                errors["base"] = "cannot_connect"

            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )
