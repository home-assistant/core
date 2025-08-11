"""Config flow for Apprise."""

from typing import Any

from apprise import Apprise
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
        errors: dict[str, str] = {}

        if user_input:
            if user_input.get("config"):
                if user_input.get(CONF_URL):
                    input_data = {
                        CONF_NAME: user_input.get(CONF_NAME, "Apprise"),
                        "config": user_input["config"],
                        CONF_URL: user_input[CONF_URL],
                    }
                else:
                    input_data = {
                        CONF_NAME: user_input.get(CONF_NAME, "Apprise"),
                        "config": user_input["config"],
                    }
            elif user_input.get(CONF_URL):
                input_data = {
                    CONF_NAME: user_input.get(CONF_NAME, "Apprise"),
                    CONF_URL: user_input[CONF_URL],
                }
            else:
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema(
                        {
                            vol.Required(CONF_NAME, default="Apprise"): str,
                            vol.Optional("config"): str,
                            vol.Optional(CONF_URL): str,
                        }
                    ),
                    errors=errors,
                )
            success = await validate_apprise_connection(self.hass, input_data)
            if not success:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, "Apprise"),
                    data=input_data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default="Apprise"): str,
                    vol.Optional("config"): str,
                    vol.Optional(CONF_URL): str,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_config: dict) -> ConfigFlowResult:
        """Handle import from configuration.yaml."""
        result = await self.async_step_user(import_config)

        success = await validate_apprise_connection(self.hass, import_config)
        if not success:
            await deprecate_yaml_issue(self.hass, False)
            return self.async_abort(reason="cannot_connect")

        await deprecate_yaml_issue(self.hass, True)
        return result


async def validate_apprise_connection(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> bool:
    """Attempt to send a test message to Apprise."""
    if not user_input.get("config"):
        return True

    try:
        client = Apprise()
        client.add(user_input["config"])

        if user_input.get(CONF_URL):
            client.add(user_input[CONF_URL])

        await hass.async_add_executor_job(client.notify, "Test message")
    except (OSError, ValueError, ConnectionError):
        return False
    else:
        return True


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
