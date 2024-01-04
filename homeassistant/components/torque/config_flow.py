"""Config flow for Torque integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_EMAIL, CONF_NAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

ISSUE_PLACEHOLDER = {"url": "/config/integrations/dashboard/add?domain=torque"}
DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


class TorqueConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Torque."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_EMAIL: user_input[CONF_EMAIL],
                }
            )

            await self.async_set_unique_id(user_input[CONF_NAME])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, user_input: dict[str, Any]) -> FlowResult:
        """Import the YAML config."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        self._async_abort_entries_match(
            {
                CONF_NAME: user_input[CONF_NAME],
                CONF_EMAIL: user_input[CONF_EMAIL],
            }
        )

        async_create_issue(
            self.hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2024.7.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Torque",
            },
        )

        return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)
