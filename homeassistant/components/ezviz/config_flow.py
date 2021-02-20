"""Config flow for ezviz."""
import logging

from pyezviz import EzvizClient
from pyezviz.client import PyEzvizError
import voluptuous as vol

from homeassistant import exceptions
from homeassistant.config_entries import CONN_CLASS_CLOUD_POLL, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_PASSWORD, CONF_REGION, CONF_TIMEOUT, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow

from .const import (  # pylint: disable=unused-import
    CONF_FFMPEG_ARGUMENTS,
    DEFAULT_FFMPEG_ARGUMENTS,
    DEFAULT_REGION,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_REGION, default=DEFAULT_REGION): str,
    }
)


_LOGGER = logging.getLogger(__name__)


class EzvizConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ezviz."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_CLOUD_POLL

    async def _validate_and_create(self, data):
        """Validate the user input allows us to connect.

        Data has the keys from DATA_SCHEMA with values provided by the user.
        """

        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if (
                entry.data[CONF_USERNAME] == data[CONF_USERNAME]
                and entry.data[CONF_PASSWORD] == data[CONF_PASSWORD]
            ):
                raise AbortFlow("already_configured")

        # constructor does login call
        client = EzvizClient(
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
            data[CONF_REGION],
            data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
        )

        # Validate data by sending a login request to ezviz

        try:
            await self.hass.async_add_executor_job(client.login)

        except PyEzvizError as err:
            raise InvalidAuth from err

        return self.async_create_entry(title=data[CONF_USERNAME], data=data)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return EzvizOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors = {}

        if user_input is not None:
            if CONF_TIMEOUT not in user_input:
                user_input[CONF_TIMEOUT] = DEFAULT_TIMEOUT

            try:
                return await self._validate_and_create(user_input)

            except InvalidAuth:
                errors["base"] = "invalid_auth"

            except AbortFlow:
                raise

            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                return self.async_abort(reason="unknown")

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors or {}
        )

    async def async_step_import(self, import_config):
        """Handle config import from yaml."""
        try:
            return await self._validate_and_create(import_config)

        except InvalidAuth:
            _LOGGER.error("Error importing Ezviz platform config: invalid auth.")
            return self.async_abort(reason="invalid_auth")

        except AbortFlow:
            raise

        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Error importing ezviz platform config: unexpected exception."
            )
            return self.async_abort(reason="unknown")


class EzvizOptionsFlowHandler(OptionsFlow):
    """Handle Ezviz client options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage Ezviz options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Optional(
                CONF_TIMEOUT,
                default=self.config_entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
            ): int,
            vol.Optional(
                CONF_FFMPEG_ARGUMENTS,
                default=self.config_entry.options.get(
                    CONF_FFMPEG_ARGUMENTS, DEFAULT_FFMPEG_ARGUMENTS
                ),
            ): str,
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
