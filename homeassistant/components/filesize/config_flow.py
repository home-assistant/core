"""Config flow for filesize integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_FILE_PATH, CONF_UNIT_OF_MEASUREMENT, DATA_MEGABYTES

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_FILE_PATH): str,  # vol.IsFile,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT, default=DATA_MEGABYTES): str,
    }
)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input."""

    _LOGGER.info("Validating file path: %s", data[CONF_FILE_PATH])
    if not hass.config.is_allowed_path(data[CONF_FILE_PATH]):
        _LOGGER.error(
            "File path %s is not valid or allowed. Check directory whitelisting.",
            data[CONF_FILE_PATH],
        )
        raise InvalidPath

    # Return info that you want to store in the config entry.
    return {"title": f"{data[CONF_FILE_PATH]} ({data[CONF_UNIT_OF_MEASUREMENT]})"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for filesize."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_FILE_PATH]}_{user_input[CONF_UNIT_OF_MEASUREMENT]}"
            )
            self._abort_if_unique_id_configured()

            try:
                info = await validate_input(self.hass, user_input)

                return self.async_create_entry(title=info["title"], data=user_input)
            except InvalidPath:  # pylint: disable=broad-except
                errors["base"] = "invalid_path"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class InvalidPath(exceptions.HomeAssistantError):
    """Error if invalid path provided."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
