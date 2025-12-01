"""Config flow for the Duck DNS integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_DOMAIN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from . import _update_duckdns
from .const import DOMAIN
from .issue import deprecate_yaml_issue

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DOMAIN): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT, suffix=".duckdns.org")
        ),
        vol.Required(CONF_ACCESS_TOKEN): str,
    }
)


class DuckDnsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Duck DNS."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_DOMAIN: user_input[CONF_DOMAIN]})
            session = async_get_clientsession(self.hass)
            try:
                if not await _update_duckdns(
                    session,
                    user_input[CONF_DOMAIN],
                    user_input[CONF_ACCESS_TOKEN],
                ):
                    errors["base"] = "update_failed"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if not errors:
                return self.async_create_entry(
                    title=f"{user_input[CONF_DOMAIN]}.duckdns.org", data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_USER_DATA_SCHEMA, suggested_values=user_input
            ),
            errors=errors,
            description_placeholders={"url": "https://www.duckdns.org/"},
        )

    async def async_step_import(self, import_info: dict[str, Any]) -> ConfigFlowResult:
        """Import config from yaml."""

        self._async_abort_entries_match({CONF_DOMAIN: import_info[CONF_DOMAIN]})
        result = await self.async_step_user(import_info)
        if errors := result.get("errors"):
            deprecate_yaml_issue(self.hass, import_success=False)
            return self.async_abort(reason=errors["base"])

        deprecate_yaml_issue(self.hass, import_success=True)
        return result
