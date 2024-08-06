"""Config flow for Nice G.O. integration."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from nice_go import ApiError, AuthFailedError, NiceGOApi
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_REFRESH_TOKEN, CONF_REFRESH_TOKEN_CREATION_TIME, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_EMAIL])
            self._abort_if_unique_id_configured()

            hub = NiceGOApi()

            try:
                refresh_token = await hub.authenticate(
                    user_input[CONF_EMAIL],
                    user_input[CONF_PASSWORD],
                    async_get_clientsession(self.hass),
                )
            except AuthFailedError:
                errors["base"] = "invalid_auth"
            except ApiError as e:
                _LOGGER.exception("API error")
                if "UserNotFoundException" in str(e.__context__):
                    errors["base"] = "user_not_found"
                else:
                    errors["base"] = "unknown"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                info = {
                    CONF_EMAIL: user_input[CONF_EMAIL],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_REFRESH_TOKEN: refresh_token,
                    CONF_REFRESH_TOKEN_CREATION_TIME: datetime.now().timestamp(),
                }

                return self.async_create_entry(
                    title=user_input[CONF_EMAIL],
                    data=info,
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidDeviceID(HomeAssistantError):
    """Error to indicate there is invalid device ID."""
