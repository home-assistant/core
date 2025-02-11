"""Config flow for Gaposa integration."""

from __future__ import annotations

from asyncio import timeout
from collections.abc import Mapping
import logging
from typing import Any

from aiohttp import ClientConnectionError
from pygaposa import FirebaseAuthException, Gaposa, GaposaAuthException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_PASSWORD, CONF_USERNAME, DEFAULT_GATEWAY_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    try:
        async with timeout(10):  # Add timeout handling
            websession = async_get_clientsession(hass)
            gaposa = Gaposa(data[CONF_API_KEY], loop=hass.loop, websession=websession)
            await gaposa.login(data[CONF_USERNAME], data[CONF_PASSWORD])
    except ClientConnectionError as exp:
        _LOGGER.error(exp)
        raise CannotConnect from exp
    except GaposaAuthException as exp:
        _LOGGER.error(exp)
        raise InvalidAuth from exp
    except FirebaseAuthException as exp:
        _LOGGER.error(exp)
        raise InvalidAuth from exp

    await gaposa.close()

    # Return info that you want to store in the config entry.
    return {"title": DEFAULT_GATEWAY_NAME}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Gaposa."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthorization request."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthorization flow."""
        errors = {}

        if user_input is not None:
            entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
            assert entry is not None

            try:
                # Validate the new password
                await validate_input(
                    self.hass,
                    {
                        "api_key": entry.data["api_key"],
                        "username": entry.data["username"],
                        "password": user_input["password"],
                    },
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                # Update the config entry with the new password
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={
                        **entry.data,
                        "password": user_input["password"],
                    },
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required("password"): str,
                }
            ),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
