"""Config flow for motionEye integration."""
import logging

from motioneye_client.client import (
    MotionEyeClient,
    MotionEyeClientConnectionFailure,
    MotionEyeClientInvalidAuth,
    MotionEyeClientRequestFailed,
)
from motioneye_client.const import DEFAULT_PORT, DEFAULT_USERNAME
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for motionEye."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}
        client = MotionEyeClient(
            user_input[CONF_HOST],
            user_input[CONF_PORT],
            username=user_input.get(CONF_USERNAME),
            password=user_input.get(CONF_PASSWORD),
        )

        try:
            await client.async_client_login()
        except MotionEyeClientConnectionFailure:
            errors["base"] = "cannot_connect"
        except MotionEyeClientInvalidAuth:
            errors["base"] = "invalid_auth"
        except MotionEyeClientRequestFailed:
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(
                title=f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}",
                data=user_input,
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
