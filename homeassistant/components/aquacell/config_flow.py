"""Config flow for Aquacell integration."""
from __future__ import annotations

import logging
from typing import Any

from aioaquacell import ApiException, AquacellApi, AuthenticationFailed
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_REFRESH_TOKEN, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(
    hass: HomeAssistant, email: str, password: str
) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    session = async_get_clientsession(hass)
    api = AquacellApi(session)
    refresh_token = None
    try:
        refresh_token = await api.authenticate(email, password)
    except AuthenticationFailed as err:
        raise InvalidAuth from err
    except ApiException as err:
        raise CannotConnect from err

    return {
        CONF_REFRESH_TOKEN: refresh_token,
        CONF_EMAIL: email,
        CONF_PASSWORD: password,
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Aquacell."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(
                    self.hass, user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
                )
                await self.async_set_unique_id(
                    user_input[CONF_EMAIL].lower(), raise_on_progress=False
                )
                self._abort_if_unique_id_configured()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL],
                    data=info,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(self, user_input=None):
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Dialog that informs the user that reauth is required."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(
                    self.hass, user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
                )
                entry = await self.async_set_unique_id(
                    user_input[CONF_EMAIL].lower(), raise_on_progress=False
                )
                if entry:
                    self.hass.config_entries.async_update_entry(entry, data=info)
                    await self.hass.config_entries.async_reload(entry.entry_id)
                    return self.async_abort(reason="reauth_successful")

                return self.async_create_entry(title=user_input[CONF_EMAIL], data=info)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reauth_confirm", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
