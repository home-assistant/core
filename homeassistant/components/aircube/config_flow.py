"""Config flow for airCube."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import callback

from .const import CONF_DETECTION_TIME, DEFAULT_DETECTION_TIME, DEFAULT_NAME, DOMAIN
from .errors import CannotConnect, ConnectionTimeout, LoginError, SSLError
from .router import _get_session_id


class AirCubeFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a airCube config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return AirCubeOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                if entry.data[CONF_HOST] == user_input[CONF_HOST]:
                    return self.async_abort(reason="already_configured")
                if entry.data[CONF_NAME] == user_input[CONF_NAME]:
                    errors[CONF_NAME] = "name_exists"
                    break

            try:
                await self.hass.async_add_executor_job(
                    _get_session_id,
                    f"https://{user_input[CONF_HOST]}/ubus",
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    user_input[CONF_VERIFY_SSL],
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except ConnectionTimeout:
                errors["base"] = "timeout"
            except LoginError:
                errors[CONF_USERNAME] = "wrong_credentials"
                errors[CONF_PASSWORD] = "wrong_credentials"
            except SSLError:
                errors["base"] = "ssl_error"

            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_VERIFY_SSL, default=False): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_config):
        """Import airCube from config."""
        import_config[CONF_DETECTION_TIME] = import_config[CONF_DETECTION_TIME].seconds
        return await self.async_step_user(user_input=import_config)


class AirCubeOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle airCube options."""

    def __init__(self, config_entry):
        """Initialize airCube options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the airCube options."""
        return await self.async_step_device_tracker()

    async def async_step_device_tracker(self, user_input=None):
        """Manage the device tracker options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Optional(
                CONF_DETECTION_TIME,
                default=self.config_entry.options.get(
                    CONF_DETECTION_TIME, DEFAULT_DETECTION_TIME,
                ),
            ): int
        }

        return self.async_show_form(
            step_id="device_tracker", data_schema=vol.Schema(options)
        )
