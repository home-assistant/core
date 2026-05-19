"""Config flow for PAJ GPS Tracker integration."""

import logging
from typing import Any

from aiohttp import ClientError
from pajgps_api import PajGpsApi
from pajgps_api.models.auth import AuthResponse
from pajgps_api.pajgps_api_error import AuthenticationError, TokenRefreshError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.EMAIL,
                autocomplete="email",
            )
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            )
        ),
    }
)


class PajGPSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for PAJ GPS Tracker."""

    async def _validate_credentials(
        self, email: str, password: str
    ) -> tuple[str | None, AuthResponse | None]:
        """Attempt a real login with the given credentials.

        Returns (None, auth) on success, or (error_key, None) on failure.
        """
        websession = async_get_clientsession(self.hass)
        try:
            api = PajGpsApi(email=email, password=password, websession=websession)
            auth = await api.login()
        except AuthenticationError, TokenRefreshError:
            return "invalid_auth", None
        except ClientError:
            return "cannot_connect", None
        except Exception:
            _LOGGER.exception("Unexpected error validating PAJ GPS credentials")
            return "unknown", None

        return None, auth

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            normalized_email = user_input[CONF_EMAIL].strip().lower()
            user_input[CONF_EMAIL] = normalized_email
            error, auth = await self._validate_credentials(
                user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
            )
            if error is None and auth is not None:
                await self.async_set_unique_id(str(auth.userID))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=normalized_email, data=user_input)
            if error is not None:
                errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )
