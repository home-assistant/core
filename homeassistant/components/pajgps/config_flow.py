"""Config flow for PAJ GPS Tracker integration."""

from __future__ import annotations

import logging
from typing import Any

from pajgps_api import PajGpsApi
from pajgps_api.pajgps_api_error import AuthenticationError, TokenRefreshError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


async def _validate_credentials(email: str, password: str) -> str | None:
    """Attempt a real login with the given credentials.

    Returns an error key string on failure, or None on success.
    """
    api: PajGpsApi | None = None
    try:
        api = PajGpsApi(email=email, password=password)
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
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=CONFIG_SCHEMA)

        self.data = user_input
        # Normalize email for duplicate protection and storage
        normalized_email = self.data[CONF_EMAIL].strip().lower()
        self.data[CONF_EMAIL] = normalized_email
        self._async_abort_entries_match({CONF_EMAIL: normalized_email})
        return self.async_create_entry(title=normalized_email, data=self.data)
