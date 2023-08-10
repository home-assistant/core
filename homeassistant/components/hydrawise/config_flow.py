"""Config flow for the Hydrawise integration."""

from __future__ import annotations

from typing import Any

from pydrawise import legacy
from requests.exceptions import ConnectTimeout, HTTPError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN
from homeassistant.data_entry_flow import AbortFlow, FlowResult, FlowResultType
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str})


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hydrawise."""

    VERSION = 1

    async def _create_entry(self, api_key: str) -> FlowResult:
        """Create the config entry."""
        try:
            api = await self.hass.async_add_executor_job(
                legacy.LegacyHydrawise, api_key
            )
        except ConnectTimeout:
            await self._import_issue("timeout")
            return self.async_abort(reason="timeout_connect")
        except HTTPError as ex:
            LOGGER.error("Unable to connect to Hydrawise cloud service: %s", ex)
            await self._import_issue("connection")
            return self.async_abort(reason="cannot_connect")

        if not api.status:
            await self._import_issue("unknown")
            return self.async_abort(reason="unknown")

        await self.async_set_unique_id(f"hydrawise-{api.customer_id}")
        try:
            self._abort_if_unique_id_configured()
        except AbortFlow:
            await self._import_issue("")
            raise

        return self.async_create_entry(title="Hydrawise", data={CONF_API_KEY: api_key})

    async def _import_issue(self, error_type: str) -> None:
        """Create an issue about a YAML import failure."""
        async_create_issue(
            self.hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{error_type}",
            breaks_in_ha_version="2024.2.0",
            is_fixable=False,
            severity=IssueSeverity.ERROR,
            translation_key="deprecated_yaml_import_issue",
            translation_placeholders={"error_type": error_type},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial setup."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )
        api_key = user_input[CONF_API_KEY]
        return await self._create_entry(api_key)

    async def async_step_import(self, import_data: dict[str, Any]) -> FlowResult:
        """Import data from YAML."""
        result = await self._create_entry(import_data.get(CONF_API_KEY, ""))
        if result["type"] == FlowResultType.CREATE_ENTRY:
            async_create_issue(
                self.hass,
                HOMEASSISTANT_DOMAIN,
                f"deprecated_yaml_{DOMAIN}",
                breaks_in_ha_version="2024.3.0",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_yaml",
                translation_placeholders={
                    "domain": DOMAIN,
                    "integration_title": "Hydrawise",
                },
            )
        return result
