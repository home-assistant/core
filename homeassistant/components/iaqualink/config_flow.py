"""Config flow to configure zone component."""
from __future__ import annotations

from typing import Any

import httpx
from iaqualink.client import AqualinkClient
from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceUnauthorizedException,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


class AqualinkFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Aqualink config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow start."""
        # Supporting a single account.
        entries = self._async_current_entries()
        if entries:
            return self.async_abort(reason="single_instance_allowed")

        errors = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            try:
                async with AqualinkClient(username, password):
                    pass
            except AqualinkServiceUnauthorizedException:
                errors["base"] = "invalid_auth"
            except (AqualinkServiceException, httpx.HTTPError):
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title=username, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
