"""Config flow for Flux integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.light import ATTR_TRANSITION
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlowResult,
    OptionsFlow,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import (
    CONF_BRIGHTNESS,
    CONF_LIGHTS,
    CONF_MODE,
    CONF_NAME,
    Platform,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    ColorTempSelector,
    ColorTempSelectorConfig,
    ColorTempSelectorUnit,
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

from .const import (
    CONF_ADJUST_BRIGHTNESS,
    CONF_INTERVAL,
    CONF_START_CT,
    CONF_START_TIME,
    CONF_STOP_CT,
    CONF_STOP_TIME,
    CONF_SUNSET_CT,
    DEFAULT_NAME,
    DEFAULT_SETTINGS,
    DOMAIN,
    MODE_MIRED,
    MODE_RGB,
    MODE_XY,
)
from .switch import CONF_DISABLE_BRIGHTNESS_ADJUST

USER_FLOW_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_LIGHTS): EntitySelector(
            EntitySelectorConfig(domain=Platform.LIGHT, multiple=True)
        ),
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Flux."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for the Flux component."""
        return FluxOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        if user_input is not None:
            user_input.update(DEFAULT_SETTINGS.copy())
            return self.async_create_entry(
                title=user_input[CONF_NAME], data={}, options=user_input
            )

        return self.async_show_form(
            step_id="user",
            data_schema=USER_FLOW_SCHEMA,
        )

    async def async_step_import(self, yaml_config: ConfigType) -> ConfigFlowResult:
        """Handle import from configuration.yaml."""
        # start with the same default settings as in the UI
        entry_options = DEFAULT_SETTINGS.copy()

        # remove the old two very similar options
        brightness = yaml_config.get(CONF_BRIGHTNESS, False)
        disable_brightness_adjust = yaml_config.get(
            CONF_DISABLE_BRIGHTNESS_ADJUST, False
        )

        # combine them into the "new" option
        if brightness or disable_brightness_adjust:
            entry_options[CONF_ADJUST_BRIGHTNESS] = False

        if CONF_INTERVAL in yaml_config:
            entry_options[CONF_INTERVAL] = {"seconds": yaml_config[CONF_INTERVAL]}
        if ATTR_TRANSITION in yaml_config:
            entry_options[ATTR_TRANSITION] = {"seconds": yaml_config[ATTR_TRANSITION]}

        if CONF_START_TIME in yaml_config:
            entry_options[CONF_START_TIME] = str(yaml_config[CONF_START_TIME])

        if CONF_STOP_TIME in yaml_config:
            entry_options[CONF_STOP_TIME] = str(yaml_config[CONF_STOP_TIME])

        # apply the rest of the remaining options
        entry_options[CONF_LIGHTS] = yaml_config[CONF_LIGHTS]
        if CONF_MODE in yaml_config:
            entry_options[CONF_MODE] = yaml_config[CONF_MODE]
        if CONF_START_CT in yaml_config:
            entry_options[CONF_START_CT] = yaml_config[CONF_START_CT]
        if CONF_SUNSET_CT in yaml_config:
            entry_options[CONF_SUNSET_CT] = yaml_config[CONF_SUNSET_CT]
        if CONF_STOP_CT in yaml_config:
            entry_options[CONF_STOP_CT] = yaml_config[CONF_STOP_CT]
        if CONF_NAME in yaml_config:
            entry_options[CONF_NAME] = yaml_config[CONF_NAME]

        self._async_abort_entries_match(entry_options)

        return self.async_create_entry(
            title=str(entry_options.get(CONF_NAME, DEFAULT_NAME)),
            data={},
            options=entry_options,
        )


class FluxOptionsFlow(OptionsFlowWithConfigEntry):
    """Handle flux options."""

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        """Configure the options."""
        if user_input is not None:
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        settings = self._config_entry.options

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
                        description={"suggested_value": settings.get(CONF_START_TIME)},
                    ): TimeSelector(),
                    vol.Optional(
                        CONF_STOP_TIME,
                        description={"suggested_value": settings.get(CONF_STOP_TIME)},
                    ): TimeSelector(),
                    # colors
                    vol.Optional(
                        CONF_START_CT,
                        default=settings.get(CONF_START_CT),
                    ): ColorTempSelector(
                        ColorTempSelectorConfig(unit=ColorTempSelectorUnit.KELVIN)
                    ),
                    vol.Optional(
                        CONF_SUNSET_CT,
                        default=settings.get(CONF_SUNSET_CT),
                    ): ColorTempSelector(
                        ColorTempSelectorConfig(unit=ColorTempSelectorUnit.KELVIN)
                    ),
                    vol.Optional(
                        CONF_STOP_CT,
                        default=settings.get(CONF_STOP_CT),
                    ): ColorTempSelector(
                        ColorTempSelectorConfig(unit=ColorTempSelectorUnit.KELVIN)
                    ),
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
        )
