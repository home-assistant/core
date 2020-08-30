"""Config flow for Shark IQ integration."""

import asyncio
from typing import Dict, Optional

import aiohttp
import async_timeout
from sharkiqpy import SharkIqAuthError, get_ayla_api
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN, LOGGER  # pylint:disable=unused-import

SHARKIQ_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect."""
    ayla_api = get_ayla_api(
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
        websession=hass.helpers.aiohttp_client.async_get_clientsession(hass),
    )

    try:
        with async_timeout.timeout(10):
            LOGGER.debug("Initialize connection to Ayla networks API")
            await ayla_api.async_sign_in()
    except (asyncio.TimeoutError, aiohttp.ClientError) as errors:
        raise CannotConnect from errors
    except SharkIqAuthError as error:
        raise InvalidAuth from error

    # Return info that you want to store in the config entry.
    return {"title": data[CONF_USERNAME]}


class SharkIqConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Shark IQ."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def _async_validate_input(self, user_input):
        """Validate form input."""
        errors = {}
        info = None

        if user_input is not None:
            # noinspection PyBroadException
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
        return info, errors

    async def async_step_user(self, user_input: Optional[Dict] = None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            info, errors = await self._async_validate_input(user_input)
            if info:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=SHARKIQ_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, user_input: Optional[dict] = None):
        """Handle re-auth if login is invalid."""
        errors = {}

        if user_input is not None:
            _, errors = await self._async_validate_input(user_input)

            if not errors:
                for entry in self._async_current_entries():
                    if entry.unique_id == self.unique_id:
                        self.hass.config_entries.async_update_entry(
                            entry, data=user_input
                        )

                        return self.async_abort(reason="reauth_successful")

            if errors["base"] != "invalid_auth":
                return self.async_abort(reason=errors["base"])

        return self.async_show_form(
            step_id="reauth",
            data_schema=SHARKIQ_SCHEMA,
            errors=errors,
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
