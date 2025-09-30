"""Config flow for Datadog."""

from typing import Any

from datadog import DogStatsd
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_PREFIX
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import (
    CONF_RATE,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_PREFIX,
    DEFAULT_RATE,
    DOMAIN,
)


class DatadogConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Datadog."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user config flow."""
        errors: dict[str, str] = {}
        if user_input:
            self._async_abort_entries_match(
                {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
            )
            # Validate connection to Datadog Agent
            success = await validate_datadog_connection(
                self.hass,
                user_input,
            )
            if not success:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"Datadog {user_input['host']}",
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: user_input[CONF_PORT],
                    },
                    options={
                        CONF_PREFIX: user_input[CONF_PREFIX],
                        CONF_RATE: user_input[CONF_RATE],
                    },
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                    vol.Required(CONF_PREFIX, default=DEFAULT_PREFIX): str,
                    vol.Required(CONF_RATE, default=DEFAULT_RATE): int,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Handle import from configuration.yaml."""
        # Check for duplicates
        self._async_abort_entries_match(
            {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
        )

        result = await self.async_step_user(user_input)

        if errors := result.get("errors"):
            await deprecate_yaml_issue(self.hass, False)
            return self.async_abort(reason=errors["base"])

        await deprecate_yaml_issue(self.hass, True)
        return result

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow handler."""
        return DatadogOptionsFlowHandler()


class DatadogOptionsFlowHandler(OptionsFlow):
    """Handle Datadog options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the Datadog options."""
        errors: dict[str, str] = {}
        data = self.config_entry.data
        options = self.config_entry.options

        if user_input is None:
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_PREFIX,
                            default=options.get(
                                CONF_PREFIX, data.get(CONF_PREFIX, DEFAULT_PREFIX)
                            ),
                        ): str,
                        vol.Required(
                            CONF_RATE,
                            default=options.get(
                                CONF_RATE, data.get(CONF_RATE, DEFAULT_RATE)
                            ),
                        ): int,
                    }
                ),
                errors={},
            )

        success = await validate_datadog_connection(
            self.hass,
            {**data, **user_input},
        )
        if success:
            return self.async_create_entry(
                data={
                    CONF_PREFIX: user_input[CONF_PREFIX],
                    CONF_RATE: user_input[CONF_RATE],
                }
            )

        errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PREFIX, default=options[CONF_PREFIX]): str,
                    vol.Required(CONF_RATE, default=options[CONF_RATE]): int,
                }
            ),
            errors=errors,
        )


async def validate_datadog_connection(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> bool:
    """Attempt to send a test metric to the Datadog agent."""
    try:
        client = DogStatsd(user_input[CONF_HOST], user_input[CONF_PORT])
        await hass.async_add_executor_job(client.increment, "connection_test")
    except (OSError, ValueError):
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
                "integration_title": "Datadog",
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
                "integration_title": "Datadog",
                "url": f"/config/integrations/dashboard/add?domain={DOMAIN}",
            },
        )
