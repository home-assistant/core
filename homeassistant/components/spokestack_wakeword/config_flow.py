"""Spokestack Wake Word Config Flow."""
import logging
import re

import voluptuous as vol

from homeassistant import config_entries, exceptions

from .const import DEFAULT_MODEL_URL, DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)


DATA_SCHEMA = vol.Schema(
    {
        vol.Required("model_name", default="Hey, Spokestack!"): str,
        vol.Optional("model_url", default=DEFAULT_MODEL_URL): str,
    }
)


async def validate_input(inputs):
    """Ensure model_url looks like a url."""
    url_regex = r"((https?):((//)|(\\\\))+([\w\d:#@%/;$()~_?\+-=\\\.&](#!)?)*)"
    if re.match(url_regex, inputs["model_url"]):
        return True
    raise ValueError("URL is not valid")


class SpokestackConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Spokestack ConfigFlow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle user step."""
        errors = {}
        if user_input is not None:
            try:
                # Validate user input
                valid = await validate_input(user_input)
                if valid:
                    return self.async_create_entry(
                        title=DOMAIN.title(), data=user_input
                    )
            except ValueError:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "invalid_url"
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidHost(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid hostname."""
