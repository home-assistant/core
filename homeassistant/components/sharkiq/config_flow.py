"""Config flow for Shark IQ integration."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import aiohttp
import async_timeout
from sharkiq import SharkIqAuthError, get_ayla_api
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_PASSWORD, CONF_REGION, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    LOGGER,
    SHARKIQ_REGION_DEFAULT,
    SHARKIQ_REGION_EUROPE,
    SHARKIQ_REGION_OPTIONS,
)

SHARKIQ_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(
            CONF_REGION, default=SHARKIQ_REGION_DEFAULT
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=SHARKIQ_REGION_OPTIONS, translation_key="region"
            ),
        ),
    }
)


async def _validate_input(
    hass: core.HomeAssistant, data: Mapping[str, Any]
) -> dict[str, str]:
    """Validate the user input allows us to connect."""
    ayla_api = get_ayla_api(
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
        websession=async_get_clientsession(hass),
        europe=(data[CONF_REGION] == SHARKIQ_REGION_EUROPE),
    )

    try:
        async with async_timeout.timeout(10):
            LOGGER.debug("Initialize connection to Ayla networks API")
            await ayla_api.async_sign_in()
    except (asyncio.TimeoutError, aiohttp.ClientError, TypeError) as error:
        LOGGER.error(error)
        raise CannotConnect(
            "Unable to connect to SharkIQ services.  Check your region settings."
        ) from error
    except SharkIqAuthError as error:
        LOGGER.error(error)
        raise InvalidAuth(
            "Username or password incorrect.  Please check your credentials."
        ) from error
    except Exception as error:
        LOGGER.exception("Unexpected exception")
        LOGGER.error(error)
        raise UnknownAuth(
            "An unknown error occurred. Check your region settings and open an issue on Github if the issue persists."
        ) from error

    # Return info that you want to store in the config entry.
    return {"title": data[CONF_USERNAME]}


class SharkIqConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Shark IQ."""

    VERSION = 1

    async def _async_validate_input(
        self, user_input: Mapping[str, Any]
    ) -> tuple[dict[str, str] | None, dict[str, str]]:
        """Validate form input."""
        errors = {}
        info = None

        # noinspection PyBroadException
        try:
            info = await _validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except UnknownAuth:
            errors["base"] = "unknown"
        return info, errors

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            info, errors = await self._async_validate_input(user_input)
            if info:
                await self.async_set_unique_id(user_input[CONF_USERNAME])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=SHARKIQ_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, user_input: Mapping[str, Any]) -> FlowResult:
        """Handle re-auth if login is invalid."""
        errors: dict[str, str] = {}

        if user_input is not None:
            _, errors = await self._async_validate_input(user_input)

            if not errors:
                errors = {"base": "unknown"}
                if entry := await self.async_set_unique_id(self.unique_id):
                    self.hass.config_entries.async_update_entry(entry, data=user_input)
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


class UnknownAuth(exceptions.HomeAssistantError):
    """Error to indicate there is an uncaught auth error."""
