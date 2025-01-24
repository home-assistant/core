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

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.httpx_client import get_async_client

from .const import DOMAIN


class AqualinkFlowHandler(ConfigFlow, domain=DOMAIN):
    """Aqualink config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow start."""
        errors = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            try:
                async with AqualinkClient(
                    username, password, httpx_client=get_async_client(self.hass)
                ):
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
