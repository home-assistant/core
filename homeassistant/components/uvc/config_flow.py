"""Config flow for Unifi Video integration."""
import logging

from uvcclient import nvr
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import (
    CONF_API_KEY,
    CONF_BASE,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
)

from .const import DEFAULT_PASSWORD, DEFAULT_PORT, DEFAULT_SSL, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_SSL, default=DEFAULT_SSL): bool,
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_PASSWORD, default=DEFAULT_PASSWORD): str,
    }
)


async def validate_input(hass: core.HomeAssistant, data: dict):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    if len(data[CONF_HOST]) < 3:
        raise InvalidHost

    if data[CONF_PORT] < 1:
        raise InvalidPort

    if len(data[CONF_API_KEY]) < 3:
        raise InvalidKey

    await hass.async_add_executor_job(
        _test_connection,
        data[CONF_HOST],
        data[CONF_PORT],
        data[CONF_API_KEY],
        data[CONF_SSL],
    )

    return {"title": data[CONF_HOST]}


def _test_connection(addr, port, key, ssl):
    try:
        nvrconn = nvr.UVCRemote(addr, port, key, ssl=ssl)
        nvrconn.index()
    except nvr.NotAuthorized as ex:
        _LOGGER.error("Authorization failure while connecting to NVR")
        raise InvalidAuth from ex
    except nvr.NvrError as ex:
        _LOGGER.error("NVR error: %s", str(ex))
        raise CannotConnect from ex


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Unifi Video."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)

                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors[CONF_BASE] = "cannot_connect"
            except InvalidAuth:
                errors[CONF_BASE] = "invalid_auth"
            except InvalidHost:
                errors[CONF_HOST] = "cannot_connect"
            except InvalidKey:
                errors[CONF_API_KEY] = "invalid_key"
            except InvalidPort:
                errors[CONF_PORT] = "invalid_port"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors[CONF_BASE] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, user_input):
        """Handle import."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        return await self.async_step_user(user_input)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidHost(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid hostname."""


class InvalidPort(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid port number."""


class InvalidKey(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid api key."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid authentication."""
