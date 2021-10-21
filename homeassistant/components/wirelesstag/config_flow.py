"""Config flow for Wirelesstag integration."""
import asyncio
import logging

import voluptuous as vol
from wirelesstagpy import WirelessTags
from wirelesstagpy.exceptions import (
    WirelessTagsConnectionError,
    WirelessTagsWrongCredentials,
)

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from . import DOMAIN, WirelessTagPlatform

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Wirelesstags."""

    VERSION = 1

    def __init__(self):
        """Init config flow for Wirelesstags."""
        self._api = None
        _LOGGER.debug("Created ConfigFlow for WirelessTags")
        super().__init__()

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        _LOGGER.debug("Started async_step_user for WirelessTags")
        if user_input is not None:
            try:
                await self._async_validate_input(self.hass, user_input)
                return self.async_create_entry(title="WirelessTags", data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, config):
        """Handle import of WirelessTags config from YAML."""

        cleaned_data = {
            CONF_USERNAME: config[CONF_USERNAME],
            CONF_PASSWORD: config[CONF_PASSWORD],
        }
        return await self.async_step_user(user_input=cleaned_data)

    async def _async_validate_input(self, hass: core.HomeAssistant, data):
        """Validate the user input allows us to connect."""
        try:
            username = data[CONF_USERNAME]
            password = data[CONF_PASSWORD]

            wirelesstags = WirelessTags(username=username, password=password)
            self._api = WirelessTagPlatform(hass, wirelesstags)

            # try to authenticate during loading tags
            await hass.async_add_executor_job(self._api.load_tags)
        except (WirelessTagsWrongCredentials) as error:
            raise InvalidAuth from error
        except (WirelessTagsConnectionError, asyncio.TimeoutError) as error:
            _LOGGER.error("Could not reach the WirelessTags: %s", error)
            raise CannotConnect from error
            # Return info that you want to store in the config entry.
        except Exception as error:  # pylint: disable=broad-except
            _LOGGER.error("Failed to validate credentials for WirelessTags: %s", error)
        return True


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
