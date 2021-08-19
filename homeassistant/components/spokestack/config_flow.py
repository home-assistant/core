"""ConfigFlow for Spokestack."""
import logging

import voluptuous as vol

from homeassistant import config_entries

from .const import CONF_IDENTITY, CONF_SECRET_KEY, DEFAULT_LANG, DOMAIN
from .tts import CONF_LANG, get_engine

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IDENTITY, default="Identity"): str,
        vol.Required(CONF_SECRET_KEY, default="Secret Key"): str,
        vol.Optional(CONF_LANG, default=DEFAULT_LANG): str,
    }
)


async def validate_user_input(hass, user_input):
    """Validate the user's API keys."""
    # Setup a client to ping the API.
    tts = get_engine(hass, user_input)
    # Verify synthesis does not result in error.
    await hass.async_add_executor_job(tts.get_tts_audio, "ping")


class SpokestackConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Spokestack."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""

        # Only allow 1 instance.
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors = {}
        # Only allow 1 instance
        if user_input is not None:
            try:
                # Ensure user input contains a valid API key.
                await validate_user_input(self.hass, user_input)
                # Create the entry from user input.
                return self.async_create_entry(title=DOMAIN.title(), data=user_input)

            except Exception:  # pylint: disable=broad-except
                _LOGGER.error("Invalid Identity and Secret Key")
                errors["base"] = "invalid_config"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
