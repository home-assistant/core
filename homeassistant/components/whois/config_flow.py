"""Config flow to configure the Whois integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
import whois
from whois.exceptions import (
    FailedParsingWhoisOutput,
    UnknownDateFormat,
    UnknownTld,
    WhoisCommandFailed,
)

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_DOMAIN
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


class WhoisFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Whois."""

    VERSION = 1

    imported_name: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            domain = user_input[CONF_DOMAIN].lower()

            await self.async_set_unique_id(domain)
            self._abort_if_unique_id_configured()

            try:
                await self.hass.async_add_executor_job(whois.query, domain)
            except UnknownTld:
                errors["base"] = "unknown_tld"
            except WhoisCommandFailed:
                errors["base"] = "whois_command_failed"
            except FailedParsingWhoisOutput:
                errors["base"] = "unexpected_response"
            except UnknownDateFormat:
                errors["base"] = "unknown_date_format"
            else:
                return self.async_create_entry(
                    title=self.imported_name or user_input[CONF_DOMAIN],
                    data={
                        CONF_DOMAIN: domain,
                    },
                )
        else:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DOMAIN, default=user_input.get(CONF_DOMAIN, "")
                    ): str,
                }
            ),
            errors=errors,
        )
