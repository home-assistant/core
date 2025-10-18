"""The config flow for the Prowl component."""

from __future__ import annotations

import logging
from typing import Any

import prowlpy
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_NAME

from .const import DOMAIN
from .helpers import async_verify_key
from .issues import async_create_prowl_yaml_migration_fail_issue

_LOGGER = logging.getLogger(__name__)


class ProwlConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the Prowl component."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user configuration."""
        errors = {}

        if user_input:
            api_key = user_input[CONF_API_KEY]
            self._async_abort_entries_match({CONF_API_KEY: api_key})

            errors = await self._validate_api_key(api_key)
            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={
                        CONF_API_KEY: api_key,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_API_KEY): str,
                        vol.Required(CONF_NAME): str,
                    },
                ),
                user_input or {CONF_NAME: "Prowl"},
            ),
            errors=errors,
        )

    async def async_step_import(self, config: dict[str, Any]) -> ConfigFlowResult:
        """Handle import from legacy YAML."""
        api_key = config[CONF_API_KEY]
        self._async_abort_entries_match({CONF_API_KEY: api_key})

        errors = await self._validate_api_key(api_key)
        if not errors:
            return self.async_create_entry(
                title=config[CONF_NAME],
                data={
                    CONF_API_KEY: api_key,
                },
            )
        await async_create_prowl_yaml_migration_fail_issue(self.hass)
        return self.async_abort(reason="invalid_api_key")

    async def _validate_api_key(self, api_key: str) -> dict[str, str]:
        """Validate the provided API key."""
        ret = {}
        try:
            if not await async_verify_key(self.hass, api_key):
                ret = {"base": "invalid_api_key"}
        except TimeoutError:
            ret = {"base": "api_timeout"}
        except prowlpy.APIError:
            ret = {"base": "bad_api_response"}
        return ret
