"""Config flow for Sveriges Radio integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector

from .const import AREAS, CONF_AREA, DOMAIN, TITLE

_LOGGER = logging.getLogger(__name__)


# Should fix: adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_AREA, default="none"): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=AREAS,
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key="area",
            )
        ),
    }
)


class SverigesRadioConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sveriges Radio."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}

        if user_input is not None:
            return self.async_create_entry(title=TITLE, data=user_input)
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_onboarding(
        self, data: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by onboarding."""
        return self.async_create_entry(title="Sveriges Radio", data={})


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
