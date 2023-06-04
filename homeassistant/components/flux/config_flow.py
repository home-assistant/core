"""Config flow for Flux integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from voluptuous.schema_builder import UNDEFINED

from homeassistant import config_entries
from homeassistant.components.light import ATTR_TRANSITION
from homeassistant.const import CONF_BRIGHTNESS, CONF_LIGHTS, CONF_MODE, Platform
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    ColorTempSelector,
    ColorTempSelectorConfig,
    DurationSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TimeSelector,
)
from homeassistant.util.color import color_temperature_kelvin_to_mired

from .const import (
    CONF_INTERVAL,
    CONF_START_CT,
    CONF_START_TIME,
    CONF_STOP_CT,
    CONF_STOP_TIME,
    CONF_SUNSET_CT,
    CONF_SUNSET_TIME,
    DEFAULT_MODE,
    DOMAIN,
    MODE_MIRED,
    MODE_RGB,
    MODE_XY,
)

_LOGGER = logging.getLogger(__name__)

MINIMAL_FLUX_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LIGHTS): EntitySelector(
            EntitySelectorConfig(domain=Platform.LIGHT, multiple=True)
        )
    }
)

allowed_colortemp_range = ColorTempSelectorConfig(
    {
        "min_mireds": color_temperature_kelvin_to_mired(40000),
        "max_mireds": color_temperature_kelvin_to_mired(1000),
    }
)


def add_default_settings(settings_dict):
    """Add the default settings for the Flux integration to the initial config settings."""
    settings_dict[CONF_START_CT] = color_temperature_kelvin_to_mired(4000)
    settings_dict[CONF_SUNSET_CT] = color_temperature_kelvin_to_mired(3000)
    settings_dict[CONF_STOP_CT] = color_temperature_kelvin_to_mired(1900)
    settings_dict[CONF_MODE] = DEFAULT_MODE
    settings_dict[CONF_INTERVAL] = {"seconds": 30}
    settings_dict[ATTR_TRANSITION] = {"seconds": 30}
    return settings_dict


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Flux."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> OptionsFlow:
        """Get the options flow for the Flux component."""
        return OptionsFlow(config_entry)

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""

        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            return self.async_create_entry(
                title="Flux", data=add_default_settings(user_input)
            )

        return self.async_show_form(
            step_id="user",
            data_schema=MINIMAL_FLUX_SCHEMA,
        )


class OptionsFlow(config_entries.OptionsFlow):
    """Handle flux options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the flux options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure the options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            # Reset saved time value and use the default again.
            time_that_signals_to_reset_to_defeault = "13:37:00"
            brightness_that_signals_to_reset_to_defeault = 123
            values_that_signal_to_reset_to_default = [
                time_that_signals_to_reset_to_defeault,
                brightness_that_signals_to_reset_to_defeault,
            ]

            user_input = {
                key: value
                for key, value in user_input.items()
                if value not in values_that_signal_to_reset_to_default
            }

            # modify the existing entry...
            self.hass.config_entries.async_update_entry(
                self._config_entry, data=user_input
            )

            # instead of adding options to it..
            return self.async_create_entry(title="", data={})

        settings = self._config_entry.data

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_LIGHTS, default=settings.get(CONF_LIGHTS)
                    ): EntitySelector(
                        EntitySelectorConfig(domain=Platform.LIGHT, multiple=True)
                    ),
                    # times
                    vol.Optional(
                        CONF_START_TIME,
                        default=settings.get(CONF_START_TIME, UNDEFINED),
                    ): TimeSelector(),
                    vol.Optional(
                        CONF_SUNSET_TIME,
                        default=settings.get(CONF_SUNSET_TIME, UNDEFINED),
                    ): TimeSelector(),
                    vol.Optional(
                        CONF_STOP_TIME, default=settings.get(CONF_STOP_TIME, UNDEFINED)
                    ): TimeSelector(),
                    # colors
                    vol.Optional(
                        CONF_START_CT,
                        default=settings.get(CONF_START_CT),
                    ): ColorTempSelector(allowed_colortemp_range),
                    vol.Optional(
                        CONF_SUNSET_CT,
                        default=settings.get(CONF_SUNSET_CT),
                    ): ColorTempSelector(allowed_colortemp_range),
                    vol.Optional(
                        CONF_STOP_CT,
                        default=settings.get(CONF_STOP_CT),
                    ): ColorTempSelector(allowed_colortemp_range),
                    # brightness
                    vol.Optional(
                        CONF_BRIGHTNESS,
                        default=settings.get(CONF_BRIGHTNESS, UNDEFINED),
                    ): NumberSelector(
                        NumberSelectorConfig({"min": 0, "max": 255, "step": 1})
                    ),
                    vol.Optional(
                        CONF_MODE, default=settings.get(CONF_MODE)
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=MODE_XY, label=MODE_XY),
                                SelectOptionDict(value=MODE_MIRED, label=MODE_MIRED),
                                SelectOptionDict(value=MODE_RGB, label=MODE_RGB),
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    # update settings
                    vol.Optional(
                        ATTR_TRANSITION, default=settings.get(ATTR_TRANSITION)
                    ): DurationSelector(),
                    vol.Optional(
                        CONF_INTERVAL, default=settings.get(CONF_INTERVAL)
                    ): DurationSelector(),
                }
            ),
            errors=errors,
        )
