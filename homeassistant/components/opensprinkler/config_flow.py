"""Config flow for Opensprinkler integration."""
import logging

from pyopensprinkler import (
    OpenSprinkler,
    OpensprinklerAuthError,
    OpensprinklerConnectionError,
)
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT

from .const import (  # pylint: disable=unused-import
    CONF_RUN_SECONDS,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_RUN_SECONDS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Optional(CONF_RUN_SECONDS, default=DEFAULT_RUN_SECONDS): int,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Opensprinkler."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                password = user_input[CONF_PASSWORD]
                host = (
                    f"{user_input[CONF_HOST]}:{user_input.get(CONF_PORT, DEFAULT_PORT)}"
                )
                await self.hass.async_add_executor_job(OpenSprinkler, host, password)

                await self.async_set_unique_id(host)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, DEFAULT_NAME),
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_PORT: user_input.get(CONF_PORT, DEFAULT_PORT),
                        CONF_NAME: user_input.get(CONF_NAME, DEFAULT_NAME),
                        CONF_RUN_SECONDS: user_input.get(
                            CONF_RUN_SECONDS, DEFAULT_RUN_SECONDS
                        ),
                    },
                )
            except OpensprinklerConnectionError:
                errors["base"] = "cannot_connect"
            except OpensprinklerAuthError:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DEVICE_SCHEMA, errors=errors
        )

    async def async_step_import(self, user_input):
        """Handle import."""
        return await self.async_step_user(user_input)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
