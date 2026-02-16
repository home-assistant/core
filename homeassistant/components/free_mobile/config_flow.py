"""Config flow for Free Mobile notification."""

from __future__ import annotations

import logging
from typing import Any

from freesms import FreeClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_USERNAME

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class FreeMobileConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle Free Mobile config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            client: FreeClient | None = None
            # Create a FreeClient to validate credentials
            try:
                client = FreeClient(
                    user_input[CONF_USERNAME], user_input[CONF_ACCESS_TOKEN]
                )
            except AssertionError:
                _LOGGER.exception("Failed to initialize FreeClient")
                errors["base"] = "client_initialization_failed"

            # Send a test SMS to validate the credentials
            if not errors and client:
                try:
                    await self.hass.async_add_executor_job(
                        client.send_sms, "Home Assistant test"
                    )
                except Exception:
                    _LOGGER.exception("Failed to send test SMS")
                    errors["base"] = "test_sms_failed"

            if errors:
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema(
                        {
                            vol.Required(CONF_USERNAME): str,
                            vol.Required(CONF_ACCESS_TOKEN): str,
                        }
                    ),
                    errors=errors,
                )

            # If we get here, validation succeeded
            await self.async_set_unique_id(user_input[CONF_USERNAME])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(title="Free Mobile", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_ACCESS_TOKEN): str,
                }
            ),
            errors=errors,
        )
