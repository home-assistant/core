"""Config flow for Epion."""
from __future__ import annotations

import logging
from typing import Any

from epion import Epion, EpionAuthenticationError, EpionConnectionError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_API_KEY
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class EpionConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Epion."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}
        if user_input:
            try:
                key_valid = await self.hass.async_add_executor_job(
                    self._check_api_key, user_input[CONF_API_KEY]
                )
            except EpionConnectionError:
                _LOGGER.error("Unexpected problem when configuring Epion API")
                errors["base"] = "cannot_connect"
            else:
                if key_valid:
                    return self.async_create_entry(
                        title="Epion integration",
                        data=user_input,
                    )
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                }
            ),
            errors=errors,
        )

    def _check_api_key(self, api_key: str) -> bool:
        """Try to connect and see if the API key is valid."""
        api = Epion(api_key)
        try:
            api.get_current()
            return True
        except EpionAuthenticationError:
            return False
