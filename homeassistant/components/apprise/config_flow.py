"""Config flow for Apprise."""

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME, CONF_URL
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import DOMAIN


class AppriseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Apprise."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input:
            return self.async_create_entry(
                title=user_input.get(CONF_NAME, "Apprise"),
                data={
                    CONF_URL: user_input[CONF_URL],
                    "config": user_input.get("config"),
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_NAME, default="Apprise"): str,
                    vol.Optional("config"): str,
                    vol.Optional(CONF_URL): str,
                }
            ),
        )

    async def async_step_import(self, import_config: dict) -> ConfigFlowResult:
        """Handle import from configuration.yaml."""
        result = await self.async_step_user(import_config)

        if errors := result.get("errors"):
            await deprecate_yaml_issue(self.hass, False)
            return self.async_abort(reason=errors["base"])

        await deprecate_yaml_issue(self.hass, True)
        return result


async def deprecate_yaml_issue(
    hass: HomeAssistant,
    import_success: bool,
) -> None:
    """Create an issue to deprecate YAML config."""
    if import_success:
        async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            is_fixable=False,
            issue_domain=DOMAIN,
            breaks_in_ha_version="2026.2.0",
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Apprise",
            },
        )
    else:
        async_create_issue(
            hass,
            DOMAIN,
            "deprecated_yaml_import_connection_error",
            breaks_in_ha_version="2026.2.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml_import_connection_error",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Apprise",
                "url": f"/config/integrations/dashboard/add?domain={DOMAIN}",
            },
        )
