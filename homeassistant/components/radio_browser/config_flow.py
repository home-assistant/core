"""Config flow for Radio Browser integration."""

from __future__ import annotations

from typing import Any

from radios import Order
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)

from .const import CONF_ORDER, DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ORDER, default=Order.NAME): vol.In(Order),
    }
)


class RadioBrowserConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Radio Browser."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(title="Radio Browser", data=user_input)

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

    async def async_step_onboarding(
        self, data: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by onboarding."""
        return self.async_create_entry(
            title="Radio Browser", data={CONF_ORDER: Order.NAME}
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SchemaOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SchemaOptionsFlowHandler(
            config_entry,
            {
                "init": SchemaFlowFormStep(schema=DATA_SCHEMA),
            },
        )

    async def async_migrate_entry(self, config_entry: ConfigEntry) -> bool:
        """Migrate old entry."""
        if self.VERSION == 2:
            new_data = {**config_entry.data}

            if CONF_ORDER not in new_data:
                new_data[CONF_ORDER] = Order.NAME

            self.hass.config_entries.async_update_entry(config_entry, data=new_data)

        return True
