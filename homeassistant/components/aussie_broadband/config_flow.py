"""Config flow for Aussie Broadband integration."""
from __future__ import annotations

import logging
from typing import Any

from aussiebb import AussieBB, AuthenticationException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_PASSWORD, CONF_SERVICE_ID, CONF_USERNAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("username"): str,
        vol.Required("password"): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Aussie Broadband."""

    VERSION = 1
    _reauth = False

    def __init__(self):
        """Initialize the config flow."""
        self.data = {}
        self.services = None
        self.client = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
            )

        errors = {}
        try:
            self.client = await self.hass.async_add_executor_job(
                AussieBB, user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
        except AuthenticationException:
            errors["base"] = "invalid_auth"

        if self.client is not None:
            self.data.update(user_input)
            self.services = await self.hass.async_add_executor_job(
                self.client.get_services
            )
            if len(self.services) == 0:
                return self.async_abort(reason="no_services_found")

            if len(self.services) == 1:
                return await self.create_entry(self.services[0])

            # account has more than one service, select service to add
            return await self.async_step_service()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_service(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the service selection step."""

        if user_input is not None:
            service = next(
                s
                for s in self.services
                if s["service_id"] == user_input[CONF_SERVICE_ID]
            )
            return await self.create_entry(service)

        service_options = {s["service_id"]: s["description"] for s in self.services}
        return self.async_show_form(
            step_id="service",
            data_schema=vol.Schema(
                {vol.Required(CONF_SERVICE_ID): vol.In(service_options)}
            ),
        )

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reauth."""
        self._reauth = True
        return await self.async_step_user(user_input)

    async def create_entry(self, service):
        """Create entry for a service."""
        self.data[CONF_SERVICE_ID] = service["service_id"]

        entry = await self.async_set_unique_id(self.data[CONF_SERVICE_ID])
        if self._reauth:
            self.hass.config_entries.async_update_entry(
                entry, title=service["description"], data=self.data
            )
            return self.async_abort(reason="reauth_successful")

        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=service["description"], data=self.data)
