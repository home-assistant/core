"""Config flow for motionEye integration."""
import logging

from motioneye_client.client import (
    MotionEyeClient,
    MotionEyeClientConnectionFailure,
    MotionEyeClientInvalidAuth,
    MotionEyeClientRequestFailed,
)
from motioneye_client.const import DEFAULT_PORT
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import (  # pylint:disable=unused-import
    CONF_PASSWORD_ADMIN,
    CONF_PASSWORD_SURVEILLANCE,
    CONF_USERNAME_ADMIN,
    CONF_USERNAME_SURVEILLANCE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_USERNAME_ADMIN): str,
        vol.Optional(CONF_USERNAME_SURVEILLANCE): str,
        vol.Optional(CONF_PASSWORD_ADMIN): str,
        vol.Optional(CONF_PASSWORD_SURVEILLANCE): str,
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
            username_admin=user_input.get(CONF_USERNAME_ADMIN),
            username_surveillance=user_input.get(CONF_USERNAME_SURVEILLANCE),
            password_admin=user_input.get(CONF_PASSWORD_ADMIN),
            password_surveillance=user_input.get(CONF_PASSWORD_SURVEILLANCE),
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
