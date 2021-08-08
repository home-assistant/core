"""ConfigFlow for Spokestack."""
import logging

import voluptuous as vol

from homeassistant import config_entries

from .const import (
    CONF_KEY_ID,
    CONF_KEY_SECRET,
    CONF_LANG,
    CONF_MODE,
    CONF_PROFILE,
    CONF_VOICE,
    DEFAULT_LANG,
    DEFAULT_MODE,
    DEFAULT_PROFILE,
    DEFAULT_VOICE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_KEY_ID,
            msg="key_id",
            description="Spokestack API key from account dashboard.",
        ): str,
        vol.Required(
            CONF_KEY_SECRET,
            msg="key_secret",
            description="Spokestack API secret from account dashboard.",
        ): str,
        vol.Optional(CONF_VOICE, default=DEFAULT_VOICE): str,
        vol.Optional(CONF_LANG, default=DEFAULT_LANG): str,
        vol.Optional(CONF_MODE, default=DEFAULT_MODE): str,
        vol.Optional(CONF_PROFILE, default=DEFAULT_PROFILE): str,
    }
)


class SpokestackConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Spokestack."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            return self.async_create_entry(title=DOMAIN.title(), data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )
