"""Config flow for PAJ GPS Tracker integration."""

from __future__ import annotations

import logging
from typing import Any

from pajgps_api import PajGpsApi
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
) -> str | None:
    """Attempt a real login with the given credentials.

    Returns an error key string on failure, or None on success.
    """
    websession = async_get_clientsession(hass)
    api: PajGpsApi | None = None
    try:
        api = PajGpsApi(email=email, password=password, websession=websession)
        await api.login()
    except AuthenticationError, TokenRefreshError:
        return "invalid_auth"
    except Exception:  # noqa: BLE001
        return "cannot_connect"

    return None


class PajGPSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for PAJ GPS Tracker."""

    data: dict[str, Any] | None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self.data = user_input
            if not errors:
                # Normalize email for duplicate protection and storage
                normalized_email = self.data["email"].strip().lower()
                self.data[CONF_EMAIL] = normalized_email
                self._async_abort_entries_match({CONF_EMAIL: normalized_email})
                error_key = await _validate_credentials(
                    self.data[CONF_EMAIL], self.data[CONF_PASSWORD], self.hass
                )
                if error_key:
                    errors["base"] = error_key
            if not errors:
                return self.async_create_entry(title=normalized_email, data=self.data)

            return self.async_show_form(
                step_id="user",
                data_schema=self.add_suggested_values_to_schema(
                    CONFIG_SCHEMA, user_input
                ),
                errors=errors,
            )

        return self.async_show_form(
            step_id="user", data_schema=CONFIG_SCHEMA, errors=errors
        )
