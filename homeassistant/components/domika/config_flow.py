"""Config flow for Domika integration."""

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import DOMAIN


class DomikaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Domika."""

    VERSION = 1
    MINOR_VERSION = 0

    async def async_step_user(
        self, _user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        return self.async_create_entry(
            title=DOMAIN,
            # Data is immutable options.
            data={},
            # Default options.
            options={
                "critical_entities": {
                    "smoke_select_all": False,
                    "moisture_select_all": False,
                    "co_select_all": False,
                    "gas_select_all": False,
                    "critical_included_entity_ids": [],
                },
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(OptionsFlow):
    """Handle an options flow for Domika."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(
        self,
        _user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Manage the options."""
        return await self.async_step_critical_entities()

    async def async_step_critical_entities(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Manage critical entities options."""
        if user_input is not None:
            self.options["critical_entities"] = user_input
            return await self._update_options()

        critical_entities = self.options.get("critical_entities", {})

        entity_selector = selector.selector(
            {
                "entity": {
                    "domain": "binary_sensor",
                    "multiple": True,
                },
            },
        )

        return self.async_show_form(
            step_id="critical_entities",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        schema="smoke_select_all",
                        default=critical_entities.get("smoke_select_all", False),
                    ): bool,
                    vol.Optional(
                        schema="moisture_select_all",
                        default=critical_entities.get("moisture_select_all", False),
                    ): bool,
                    vol.Optional(
                        schema="co_select_all",
                        default=critical_entities.get("co_select_all", False),
                    ): bool,
                    vol.Optional(
                        schema="gas_select_all",
                        default=critical_entities.get("gas_select_all", False),
                    ): bool,
                    vol.Optional(
                        schema="critical_included_entity_ids",
                        default=critical_entities.get(
                            "critical_included_entity_ids", []
                        ),
                    ): entity_selector,
                },
            ),
        )

    async def _update_options(self) -> ConfigFlowResult:
        """Update config entry options."""
        return self.async_create_entry(title=DOMAIN, data=self.options)
