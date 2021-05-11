"""Config flow for Litter-Robot integration."""
import logging

from pylitterbot.exceptions import LitterRobotException, LitterRobotLoginException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN
from .hub import LitterRobotHub

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Litter-Robot."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_USERNAME: user_input[CONF_USERNAME]})

            hub = LitterRobotHub(self.hass, user_input)
            try:
                await hub.login()
            except LitterRobotLoginException:
                errors["base"] = "invalid_auth"
            except LitterRobotException:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
