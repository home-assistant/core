"""Config flow for Flux integration."""
from __future__ import annotations

import logging

import voluptuous as vol
from voluptuous.schema_builder import UNDEFINED

from homeassistant import config_entries
from homeassistant.components.light import ATTR_TRANSITION
from homeassistant.const import (
    CONF_BRIGHTNESS,
    CONF_LIGHTS,
    CONF_MODE,
    CONF_NAME,
    Platform,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    BooleanSelector,
    ColorTempSelector,
    ColorTempSelectorConfig,
    DurationSelector,
    EntitySelector,
    EntitySelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TimeSelector,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.color import (
    color_temperature_kelvin_to_mired,
    color_temperature_mired_to_kelvin,
)

from .const import (
    CONF_ADJUST_BRIGHTNESS,
    CONF_INTERVAL,
    CONF_START_CT,
    CONF_START_TIME,
    CONF_STOP_CT,
    CONF_STOP_TIME,
    CONF_SUNSET_CT,
    DEFAULT_MODE,
    DEFAULT_NAME,
    DEFAULT_START_COLOR_TEMP_KELVIN,
    DEFAULT_STOP_COLOR_TEMP_KELVIN,
    DEFAULT_SUNSET_COLOR_TEMP_KELVIN,
    DOMAIN,
    MODE_MIRED,
    MODE_RGB,
    MODE_XY,
)
from .switch import CONF_DISABLE_BRIGHTNESS_ADJUST

_LOGGER = logging.getLogger(__name__)

MINIMAL_FLUX_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_LIGHTS): EntitySelector(
            EntitySelectorConfig(domain=Platform.LIGHT, multiple=True)
        ),
    }
)

allowed_colortemp_range = ColorTempSelectorConfig(
    {
        "min_mireds": color_temperature_kelvin_to_mired(40000),
        "max_mireds": color_temperature_kelvin_to_mired(1000),
    }
)


def default_settings():
    """Return object with the default settings for the Flux integration."""
    settings_dict = {}
    settings_dict[CONF_START_CT] = DEFAULT_START_COLOR_TEMP_KELVIN
    settings_dict[CONF_SUNSET_CT] = DEFAULT_SUNSET_COLOR_TEMP_KELVIN
    settings_dict[CONF_STOP_CT] = DEFAULT_STOP_COLOR_TEMP_KELVIN
    settings_dict[CONF_ADJUST_BRIGHTNESS] = True
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

        if user_input is not None:
            user_input.update(default_settings())
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=MINIMAL_FLUX_SCHEMA,
        )

    async def async_step_import(self, yaml_config: ConfigType) -> FlowResult:
        """Handle import from configuration.yaml."""
        # start with the same default settings as in the UI
        entry_data = default_settings()

        # remove the old two very similar options
        brightness = yaml_config.pop(CONF_BRIGHTNESS, False)
        disable_brightness_adjust = yaml_config.pop(
            CONF_DISABLE_BRIGHTNESS_ADJUST, False
        )

        # combine them into the "new" option
        if brightness or disable_brightness_adjust:
            entry_data[CONF_ADJUST_BRIGHTNESS] = False

        entry_data[CONF_INTERVAL] = {"seconds": yaml_config.pop(CONF_INTERVAL)}
        entry_data[ATTR_TRANSITION] = {"seconds": yaml_config.pop(ATTR_TRANSITION)}

        if CONF_START_TIME in yaml_config:
            entry_data[CONF_START_TIME] = str(yaml_config.pop(CONF_START_TIME))

        if CONF_STOP_TIME in yaml_config:
            entry_data[CONF_STOP_TIME] = str(yaml_config.pop(CONF_STOP_TIME))

        yaml_config.pop("platform")

        # apply the rest of the remaining options
        entry_data.update(yaml_config)

        self._async_abort_entries_match(entry_data)

        return self.async_create_entry(title=entry_data[CONF_NAME], data=entry_data)


class OptionsFlow(config_entries.OptionsFlow):
    """Handle flux options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the flux options flow."""
        self._config_entry = config_entry

    def reset_values_to_default(self, user_input):
        """Hacky method to reset saved values and use the default again."""
        time_that_signals_to_reset_to_defeault = "13:37:00"
        values_that_signal_to_reset_to_default = [
            time_that_signals_to_reset_to_defeault,
        ]

        return {
            key: value
            for key, value in user_input.items()
            if value not in values_that_signal_to_reset_to_default
        }

    def convert_mired_stuff_to_kelvin(self, user_input):
        """Convert between mireds and kelvins because I can't find the kelvin option for ColorTempSelector."""
        user_input[CONF_START_CT] = color_temperature_mired_to_kelvin(
            user_input[CONF_START_CT]
        )
        user_input[CONF_SUNSET_CT] = color_temperature_mired_to_kelvin(
            user_input[CONF_SUNSET_CT]
        )
        user_input[CONF_STOP_CT] = color_temperature_mired_to_kelvin(
            user_input[CONF_STOP_CT]
        )

        return user_input

    def remove_undefined(self, user_input):
        """Remove keys with values that are UNDEFINED."""
        return {key: value for key, value in user_input.items() if value != UNDEFINED}

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Configure the options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input = self.reset_values_to_default(user_input)
            user_input = self.convert_mired_stuff_to_kelvin(user_input)
            user_input = self.remove_undefined(user_input)

            # modify the existing entry...
            self.hass.config_entries.async_update_entry(
                self._config_entry, title=user_input[CONF_NAME], data=user_input
            )

            # instead of adding options to it..
            return self.async_create_entry(title="", data={})

        settings = self._config_entry.data

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=settings.get(CONF_NAME)): str,
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
                        CONF_STOP_TIME, default=settings.get(CONF_STOP_TIME, UNDEFINED)
                    ): TimeSelector(),
                    # colors
                    vol.Optional(
                        CONF_START_CT,
                        default=color_temperature_kelvin_to_mired(
                            float(settings.get(CONF_START_CT))  # type: ignore[arg-type]
                        ),
                    ): ColorTempSelector(allowed_colortemp_range),
                    vol.Optional(
                        CONF_SUNSET_CT,
                        default=color_temperature_kelvin_to_mired(
                            float(settings.get(CONF_SUNSET_CT))  # type: ignore[arg-type]
                        ),
                    ): ColorTempSelector(allowed_colortemp_range),
                    vol.Optional(
                        CONF_STOP_CT,
                        default=color_temperature_kelvin_to_mired(
                            float(settings.get(CONF_STOP_CT))  # type: ignore[arg-type]
                        ),
                    ): ColorTempSelector(allowed_colortemp_range),
                    # adjust_brightness
                    vol.Optional(
                        CONF_ADJUST_BRIGHTNESS,
                        default=settings.get(CONF_ADJUST_BRIGHTNESS),
                    ): BooleanSelector(),
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
