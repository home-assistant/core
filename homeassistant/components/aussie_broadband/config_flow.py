"""Config flow for Aussie Broadband integration."""
from __future__ import annotations

import logging
from typing import Any

from aussiebb import AussieBB, AuthenticationException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import ATTR_PASSWORD, ATTR_SERVICE_ID, ATTR_USERNAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("username"): str,
        vol.Required("password"): str,
    }
)

STEP_SELECT_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("service_id"): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Aussie Broadband."""

    VERSION = 1

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
                AussieBB, user_input[ATTR_USERNAME], user_input[ATTR_PASSWORD]
            )
        except AuthenticationException:
            errors["base"] = "invalid_credentials"

        if self.client is not None:
            self.data.update(user_input)
            self.services = await self.hass.async_add_executor_job(
                self.client.get_services
            )
            if len(self.services) == 0:
                return self.async_abort(reason="no_devices_found")

            if len(self.services) == 1:
                service = self.services[0]
                self.data[ATTR_SERVICE_ID] = service["service_id"]

                existing_entry = await self.async_set_unique_id(
                    self.data[ATTR_SERVICE_ID]
                )
                if existing_entry is not None:
                    return self.async_abort(reason="already_configured")

                return self.async_create_entry(
                    title=service["description"], data=self.data
                )

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
                if s["service_id"] == user_input[ATTR_SERVICE_ID]
            )
            self.data[ATTR_SERVICE_ID] = service["service_id"]

            existing_entry = await self.async_set_unique_id(self.data[ATTR_SERVICE_ID])
            if existing_entry is not None:
                return self.async_abort(reason="already_configured")

            return self.async_create_entry(title=service["description"], data=self.data)

        service_options = {s["service_id"]: s["description"] for s in self.services}
        schema = vol.Schema({vol.Required(ATTR_SERVICE_ID): vol.In(service_options)})
        return self.async_show_form(
            step_id="service",
            data_schema=schema,
        )
