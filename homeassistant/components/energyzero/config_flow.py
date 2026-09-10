"""Config flow for EnergyZero integration."""

from typing import Any, override

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from .const import (
    CONF_ELECTRICITY_PRICE_INTERVAL,
    DEFAULT_ELECTRICITY_PRICE_INTERVAL,
    DOMAIN,
    ELECTRICITY_INTERVALS,
)


class EnergyZeroFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for EnergyZero integration."""

    VERSION = 1

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> EnergyZeroOptionsFlow:
        """Return the options flow."""
        return EnergyZeroOptionsFlow()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is None:
            return self.async_show_form(step_id="user")

        return self.async_create_entry(
            title="EnergyZero",
            data={},
        )


class EnergyZeroOptionsFlow(OptionsFlowWithReload):
    """Manage EnergyZero options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the electricity price interval."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(
                            CONF_ELECTRICITY_PRICE_INTERVAL,
                            default=DEFAULT_ELECTRICITY_PRICE_INTERVAL,
                        ): SelectSelector(
                            SelectSelectorConfig(
                                options=list(ELECTRICITY_INTERVALS),
                                translation_key=CONF_ELECTRICITY_PRICE_INTERVAL,
                            )
                        ),
                    }
                ),
                self.config_entry.options,
            ),
        )
