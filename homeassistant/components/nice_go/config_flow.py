"""Config flow for Nice G.O. integration."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
import logging
from typing import Any

from nice_go import AuthFailedError, NiceGOApi
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_REFRESH_TOKEN, CONF_REFRESH_TOKEN_CREATION_TIME, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = {
    vol.Required(CONF_EMAIL): str,
    vol.Required(CONF_PASSWORD): str,
}


async def validate_input(
    hass: HomeAssistant,
    data: dict[str, str],
) -> dict[str, str | float | None]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    hub = NiceGOApi()

    try:
        refresh_token = await hub.authenticate(
            data[CONF_EMAIL],
            data[CONF_PASSWORD],
            async_get_clientsession(hass),
        )
    except AuthFailedError as err:
        raise InvalidAuth from err

    return {
        CONF_EMAIL: data[CONF_EMAIL],
        CONF_PASSWORD: data[CONF_PASSWORD],
        CONF_REFRESH_TOKEN: refresh_token,
        CONF_REFRESH_TOKEN_CREATION_TIME: datetime.now().timestamp(),
    }


class NiceGOConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nice G.O."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._reauth_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        data_schema = vol.Schema(STEP_USER_DATA_SCHEMA)

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=data_schema)

        await self.async_set_unique_id(user_input[CONF_EMAIL])
        self._abort_if_unique_id_configured()

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            # Check if we are reauthenticating
            if self._reauth_entry is not None:
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry,
                    data=info,
                )
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

            return self.async_create_entry(
                title=user_input[CONF_EMAIL],
                data=info,
            )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Reauth in case of a password change or other error."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_user()


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidDeviceID(HomeAssistantError):
    """Error to indicate there is invalid device ID."""
