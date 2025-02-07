"""Config flow for Fluss+ integration."""

from __future__ import annotations

import logging
from typing import Any

from fluss_api import (
    FlussApiClient,
    FlussApiClientAuthenticationError,
    FlussApiClientCommunicationError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): cv.string})


class FlussConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fluss+."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                FlussApiClient(user_input[CONF_API_KEY], self.hass)
            except FlussApiClientCommunicationError:
                errors["base"] = "cannot_connect"
            except FlussApiClientAuthenticationError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception occurred")
                errors["base"] = "unknown"
            if not errors:
                return self.async_create_entry(title="Fluss Device", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


