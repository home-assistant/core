"""Config flow for AfterShip integration."""
from __future__ import annotations

import logging
from typing import Any

from pyaftership import AfterShip, AfterShipException
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class AfterShipConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AfterShip."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_API_KEY: user_input[CONF_API_KEY]})
            try:
                aftership = AfterShip(
                    api_key=user_input[CONF_API_KEY],
                    session=async_get_clientsession(self.hass),
                )
                await aftership.trackings.list()
            except AfterShipException:
                _LOGGER.exception("Aftership raised exception")
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title="AfterShip", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    async def async_step_import(self, config: dict[str, Any]) -> FlowResult:
        """Import configuration from yaml."""
        async_create_issue(
            self.hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2024.4.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "AfterShip",
            },
        )

        self._async_abort_entries_match({CONF_API_KEY: config[CONF_API_KEY]})
        return self.async_create_entry(
            title=config.get(CONF_NAME, "AfterShip"),
            data={CONF_API_KEY: config[CONF_API_KEY]},
        )
