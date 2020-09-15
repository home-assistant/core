"""Config flow for Dyson integration."""
import logging

from libpurecool.dyson import DysonAccount
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from . import CONF_LANGUAGE
from . import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect."""
    dyson_account = DysonAccount(
        data[CONF_USERNAME], data[CONF_PASSWORD], data[CONF_LANGUAGE]
    )
    if not await hass.async_add_executor_job(dyson_account.login):
        raise InvalidAuth


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dyson."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                username = user_input[CONF_USERNAME]
                language = user_input[CONF_LANGUAGE]
                await self.async_set_unique_id("{language}_{username}")
                self._abort_if_unique_id_configured()

                await validate_input(self.hass, user_input)
                return self.async_create_entry(
                    title=f"{username} ({language})",
                    data=user_input,
                )
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, default=user_input.get(CONF_USERNAME, "")
                    ): str,
                    vol.Required(
                        CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, "")
                    ): str,
                    vol.Required(
                        CONF_LANGUAGE, default=user_input.get(CONF_LANGUAGE, "")
                    ): str,
                }
            ),
            errors=errors,
        )


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
