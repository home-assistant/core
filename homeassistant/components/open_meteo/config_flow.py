"""Config flow to configure the Open-Meteo integration."""

from typing import Any, override

import voluptuous as vol

from homeassistant.components.zone import DOMAIN as ZONE_DOMAIN
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_ZONE
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_FORECAST_DAYS,
    DEFAULT_FORECAST_DAYS,
    DOMAIN,
    FORECAST_DAY_LIMITS,
)


def _forecast_days_selector() -> SelectSelector:
    """Return the selector for the daily forecast limit."""
    return SelectSelector(
        SelectSelectorConfig(
            options=list(FORECAST_DAY_LIMITS),
            mode=SelectSelectorMode.DROPDOWN,
            translation_key=CONF_FORECAST_DAYS,
        )
    )


class OpenMeteoFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for OpenMeteo."""

    VERSION = 1

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> OpenMeteoOptionsFlow:
        """Return the options flow for this entry."""
        return OpenMeteoOptionsFlow()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_ZONE])
            self._abort_if_unique_id_configured()

            state = self.hass.states.get(user_input[CONF_ZONE])
            return self.async_create_entry(
                title=state.name if state else "Open-Meteo",
                data={CONF_ZONE: user_input[CONF_ZONE]},
                options={CONF_FORECAST_DAYS: user_input[CONF_FORECAST_DAYS]},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ZONE): EntitySelector(
                        EntitySelectorConfig(domain=ZONE_DOMAIN),
                    ),
                    vol.Required(
                        CONF_FORECAST_DAYS, default=DEFAULT_FORECAST_DAYS
                    ): _forecast_days_selector(),
                }
            ),
        )


class OpenMeteoOptionsFlow(OptionsFlowWithReload):
    """Manage the daily forecast limit."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure the number of daily forecast entries returned."""
        if user_input is not None:
            return self.async_create_entry(
                data={**self.config_entry.options, **user_input}
            )

        forecast_days = self.config_entry.options.get(
            CONF_FORECAST_DAYS, DEFAULT_FORECAST_DAYS
        )
        if (
            not isinstance(forecast_days, str)
            or forecast_days not in FORECAST_DAY_LIMITS
        ):
            forecast_days = DEFAULT_FORECAST_DAYS

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_FORECAST_DAYS, default=forecast_days
                    ): _forecast_days_selector(),
                }
            ),
        )
