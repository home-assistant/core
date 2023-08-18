"""Config flow for the LiteJet lighting system."""
from __future__ import annotations

from typing import Any

import pylitejet
from serial import SerialException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PORT
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, callback
from homeassistant.data_entry_flow import FlowResult, FlowResultType
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import CONF_DEFAULT_TRANSITION, DOMAIN


class LiteJetOptionsFlow(config_entries.OptionsFlow):
    """Handle LiteJet options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize LiteJet options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage LiteJet options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_DEFAULT_TRANSITION,
                        default=self.config_entry.options.get(
                            CONF_DEFAULT_TRANSITION, 0
                        ),
                    ): cv.positive_int,
                }
            ),
        )


class LiteJetConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """LiteJet config flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Create a LiteJet config entry based upon user input."""
        if self._async_current_entries():
            if self.context["source"] == config_entries.SOURCE_IMPORT:
                async_create_issue(
                    self.hass,
                    HOMEASSISTANT_DOMAIN,
                    f"deprecated_yaml_{DOMAIN}",
                    breaks_in_ha_version="2024.2.0",
                    is_fixable=False,
                    issue_domain=DOMAIN,
                    severity=IssueSeverity.WARNING,
                    translation_key="deprecated_yaml",
                    translation_placeholders={
                        "domain": DOMAIN,
                        "integration_title": "LiteJet",
                    },
                )
            return self.async_abort(reason="single_instance_allowed")

        errors = {}
        if user_input is not None:
            port = user_input[CONF_PORT]

            try:
                system = await pylitejet.open(port)
            except SerialException:
                if self.context["source"] == config_entries.SOURCE_IMPORT:
                    async_create_issue(
                        self.hass,
                        DOMAIN,
                        "deprecated_yaml_serial_exception",
                        breaks_in_ha_version="2024.2.0",
                        is_fixable=False,
                        issue_domain=DOMAIN,
                        severity=IssueSeverity.ERROR,
                        translation_key="deprecated_yaml_serial_exception",
                        translation_placeholders={
                            "set_up_the_integration": "[set up the integration](/config/integrations/dashboard/add?domain=litejet)"
                        },
                    )
                errors[CONF_PORT] = "open_failed"
            else:
                await system.close()
                return self.async_create_entry(
                    title=port,
                    data={CONF_PORT: port},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_PORT): str}),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> FlowResult:
        """Import litejet config from configuration.yaml."""
        new_data = {CONF_PORT: import_data[CONF_PORT]}
        result = await self.async_step_user(new_data)
        if result["type"] == FlowResultType.CREATE_ENTRY:
            async_create_issue(
                self.hass,
                HOMEASSISTANT_DOMAIN,
                f"deprecated_yaml_{DOMAIN}",
                breaks_in_ha_version="2024.2.0",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_yaml",
                translation_placeholders={
                    "domain": DOMAIN,
                    "integration_title": "LiteJet",
                },
            )
        return result

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> LiteJetOptionsFlow:
        """Get the options flow for this handler."""
        return LiteJetOptionsFlow(config_entry)
