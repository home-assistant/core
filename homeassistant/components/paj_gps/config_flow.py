"""Config flow for PAJ GPS Tracker integration."""

from __future__ import annotations

import logging
from typing import Any

from pajgps_api import PajGpsApi
from pajgps_api.models.auth import AuthResponse
from pajgps_api.pajgps_api_error import AuthenticationError, TokenRefreshError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


async def _validate_credentials(
    email: str, password: str, hass: HomeAssistant
) -> tuple[str | None, AuthResponse | None]:
    """Attempt a real login with the given credentials.

    Returns (None, auth) on success, or (error_key, None) on failure.
    """
    websession = async_get_clientsession(hass)
    try:
        api = PajGpsApi(email=email, password=password, websession=websession)
        auth = await api.login()
    except AuthenticationError, TokenRefreshError:
        return "invalid_auth", None
    except Exception:
        _LOGGER.exception("Unexpected error validating PAJ GPS credentials")
        return "unknown", None

    return None, auth


class PajGPSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for PAJ GPS Tracker."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=CONFIG_SCHEMA)

        normalized_email = user_input[CONF_EMAIL].strip().lower()
        user_input[CONF_EMAIL] = normalized_email
        error, auth = await _validate_credentials(
            user_input[CONF_EMAIL], user_input[CONF_PASSWORD], self.hass
        )
        if error is not None:
            return self.async_show_form(
                step_id="user", data_schema=CONFIG_SCHEMA, errors={"base": error}
            )
        assert auth is not None
        await self.async_set_unique_id(str(auth.userID))
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=normalized_email, data=user_input)
