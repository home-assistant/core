"""Config flow for TaHoma integration."""
from asyncio import TimeoutError
import logging

from aiohttp import ClientError
from pyhoma.client import TahomaClient
from pyhoma.exceptions import BadCredentialsException, TooManyRequestsException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    MIN_UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TaHoma."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Handle the flow."""
        return OptionsFlowHandler(config_entry)

    async def async_validate_input(self, user_input):
        """Validate user credentials."""
        username = user_input.get(CONF_USERNAME)
        password = user_input.get(CONF_PASSWORD)

        async with TahomaClient(username, password) as client:
            await client.login()
            return self.async_create_entry(title=username, data=user_input)

    async def async_step_user(self, user_input=None):
        """Handle the initial step via config flow."""
        errors = {}

        if user_input:
            await self.async_set_unique_id(user_input.get(CONF_USERNAME))
            self._abort_if_unique_id_configured()

            try:
                return await self.async_validate_input(user_input)
            except TooManyRequestsException:
                errors["base"] = "too_many_requests"
            except BadCredentialsException:
                errors["base"] = "invalid_auth"
            except (TimeoutError, ClientError):
                errors["base"] = "cannot_connect"
            except Exception as exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"
                _LOGGER.exception(exception)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_config: dict):
        """Handle the initial step via YAML configuration."""
        if not import_config:
            return

        try:
            return await self.async_validate_input(import_config)
        except TooManyRequestsException:
            _LOGGER.error("too_many_requests")
            return self.async_abort(reason="too_many_requests")
        except BadCredentialsException:
            _LOGGER.error("invalid_auth")
            return self.async_abort(reason="invalid_auth")
        except (TimeoutError, ClientError):
            _LOGGER.error("cannot_connect")
            return self.async_abort(reason="cannot_connect")
        except Exception as exception:  # pylint: disable=broad-except
            _LOGGER.exception(exception)
            return self.async_abort(reason="unknown")


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for TaHoma."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

        if self.options.get(CONF_UPDATE_INTERVAL) is None:
            self.options[CONF_UPDATE_INTERVAL] = DEFAULT_UPDATE_INTERVAL

    async def async_step_init(self, user_input=None):
        """Manage the Somfy TaHoma options."""
        return await self.async_step_update_interval()

    async def async_step_update_interval(self, user_input=None):
        """Manage the options regarding interval updates."""
        if user_input is not None:
            self.options[CONF_UPDATE_INTERVAL] = user_input[CONF_UPDATE_INTERVAL]
            return self.async_create_entry(title="", data=self.options)

        return self.async_show_form(
            step_id="update_interval",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_UPDATE_INTERVAL,
                        default=self.options.get(CONF_UPDATE_INTERVAL),
                    ): vol.All(cv.positive_int, vol.Clamp(min=MIN_UPDATE_INTERVAL))
                }
            ),
        )
