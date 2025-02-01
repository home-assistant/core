"""Support for Template lights."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_TRANSITION,
    DEFAULT_MAX_KELVIN,
    DEFAULT_MIN_KELVIN,
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA as LIGHT_PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
    LightEntityFeature,
    filter_supported_color_modes,
)
from homeassistant.const import (
    CONF_ENTITY_ID,
    CONF_FRIENDLY_NAME,
    CONF_LIGHTS,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.script import Script
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import color as color_util

from .const import DOMAIN
from .template_entity import (
    TEMPLATE_ENTITY_COMMON_SCHEMA_LEGACY,
    TemplateEntity,
    rewrite_common_legacy_to_modern_conf,
)

_LOGGER = logging.getLogger(__name__)
_VALID_STATES = [STATE_ON, STATE_OFF, "true", "false"]

# Legacy
CONF_COLOR_ACTION = "set_color"
CONF_COLOR_TEMPLATE = "color_template"

CONF_HS_ACTION = "set_hs"
CONF_HS_TEMPLATE = "hs_template"
CONF_RGB_ACTION = "set_rgb"
CONF_RGB_TEMPLATE = "rgb_template"
CONF_RGBW_ACTION = "set_rgbw"
CONF_RGBW_TEMPLATE = "rgbw_template"
CONF_RGBWW_ACTION = "set_rgbww"
CONF_RGBWW_TEMPLATE = "rgbww_template"
CONF_EFFECT_ACTION = "set_effect"
CONF_EFFECT_LIST_TEMPLATE = "effect_list_template"
CONF_EFFECT_TEMPLATE = "effect_template"
CONF_LEVEL_ACTION = "set_level"
CONF_LEVEL_TEMPLATE = "level_template"
CONF_MAX_MIREDS_TEMPLATE = "max_mireds_template"
CONF_MIN_MIREDS_TEMPLATE = "min_mireds_template"
CONF_OFF_ACTION = "turn_off"
CONF_ON_ACTION = "turn_on"
CONF_SUPPORTS_TRANSITION = "supports_transition_template"
CONF_TEMPERATURE_ACTION = "set_temperature"
CONF_TEMPERATURE_TEMPLATE = "temperature_template"
CONF_WHITE_VALUE_ACTION = "set_white_value"
CONF_WHITE_VALUE_TEMPLATE = "white_value_template"

DEFAULT_MIN_MIREDS = 153
DEFAULT_MAX_MIREDS = 500

LIGHT_SCHEMA = vol.All(
    cv.deprecated(CONF_ENTITY_ID),
    vol.Schema(
        {
            vol.Exclusive(CONF_COLOR_ACTION, "hs_legacy_action"): cv.SCRIPT_SCHEMA,
            vol.Exclusive(CONF_COLOR_TEMPLATE, "hs_legacy_template"): cv.template,
            vol.Exclusive(CONF_HS_ACTION, "hs_legacy_action"): cv.SCRIPT_SCHEMA,
            vol.Exclusive(CONF_HS_TEMPLATE, "hs_legacy_template"): cv.template,
            vol.Optional(CONF_RGB_ACTION): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_RGB_TEMPLATE): cv.template,
            vol.Optional(CONF_RGBW_ACTION): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_RGBW_TEMPLATE): cv.template,
            vol.Optional(CONF_RGBWW_ACTION): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_RGBWW_TEMPLATE): cv.template,
            vol.Inclusive(CONF_EFFECT_ACTION, "effect"): cv.SCRIPT_SCHEMA,
            vol.Inclusive(CONF_EFFECT_LIST_TEMPLATE, "effect"): cv.template,
            vol.Inclusive(CONF_EFFECT_TEMPLATE, "effect"): cv.template,
            vol.Optional(CONF_ENTITY_ID): cv.entity_ids,
            vol.Optional(CONF_FRIENDLY_NAME): cv.string,
            vol.Optional(CONF_LEVEL_ACTION): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_LEVEL_TEMPLATE): cv.template,
            vol.Optional(CONF_MAX_MIREDS_TEMPLATE): cv.template,
            vol.Optional(CONF_MIN_MIREDS_TEMPLATE): cv.template,
            vol.Required(CONF_OFF_ACTION): cv.SCRIPT_SCHEMA,
            vol.Required(CONF_ON_ACTION): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_SUPPORTS_TRANSITION): cv.template,
            vol.Optional(CONF_TEMPERATURE_ACTION): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_TEMPERATURE_TEMPLATE): cv.template,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
            vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        }
    ).extend(TEMPLATE_ENTITY_COMMON_SCHEMA_LEGACY.schema),
)

PLATFORM_SCHEMA = vol.All(
    # CONF_WHITE_VALUE_* is deprecated, support will be removed in release 2022.9
    cv.removed(CONF_WHITE_VALUE_ACTION),
    cv.removed(CONF_WHITE_VALUE_TEMPLATE),
    LIGHT_PLATFORM_SCHEMA.extend(
        {vol.Required(CONF_LIGHTS): cv.schema_with_slug_keys(LIGHT_SCHEMA)}
    ),
)


async def _async_create_entities(hass, config):
    """Create the Template Lights."""
    lights = []

    for object_id, entity_config in config[CONF_LIGHTS].items():
        entity_config = rewrite_common_legacy_to_modern_conf(hass, entity_config)
        unique_id = entity_config.get(CONF_UNIQUE_ID)

        lights.append(
            LightTemplate(
                hass,
                object_id,
                entity_config,
                unique_id,
            )
        )

    return lights


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the template lights."""
    async_add_entities(await _async_create_entities(hass, config))


class LightTemplate(TemplateEntity, LightEntity):
    """Representation of a templated Light, including dimmable."""

    _attr_should_poll = False

    def __init__(
        self,
        hass,
        object_id,
        config,
        unique_id,
    ):
        """Initialize the light."""
        super().__init__(
            hass, config=config, fallback_name=object_id, unique_id=unique_id
        )
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, object_id, hass=hass
        )
        friendly_name = self._attr_name
        self._template = config.get(CONF_VALUE_TEMPLATE)
        self._on_script = Script(hass, config[CONF_ON_ACTION], friendly_name, DOMAIN)
        self._off_script = Script(hass, config[CONF_OFF_ACTION], friendly_name, DOMAIN)
        self._level_script = None
        if (level_action := config.get(CONF_LEVEL_ACTION)) is not None:
            self._level_script = Script(hass, level_action, friendly_name, DOMAIN)
        self._level_template = config.get(CONF_LEVEL_TEMPLATE)
        self._temperature_script = None
        if (temperature_action := config.get(CONF_TEMPERATURE_ACTION)) is not None:
            self._temperature_script = Script(
                hass, temperature_action, friendly_name, DOMAIN
            )
        self._temperature_template = config.get(CONF_TEMPERATURE_TEMPLATE)
        self._color_script = None
        if (color_action := config.get(CONF_COLOR_ACTION)) is not None:
            self._color_script = Script(hass, color_action, friendly_name, DOMAIN)
        self._color_template = config.get(CONF_COLOR_TEMPLATE)
        self._hs_script = None
        if (hs_action := config.get(CONF_HS_ACTION)) is not None:
            self._hs_script = Script(hass, hs_action, friendly_name, DOMAIN)
        self._hs_template = config.get(CONF_HS_TEMPLATE)
        self._rgb_script = None
        if (rgb_action := config.get(CONF_RGB_ACTION)) is not None:
            self._rgb_script = Script(hass, rgb_action, friendly_name, DOMAIN)
        self._rgb_template = config.get(CONF_RGB_TEMPLATE)
        self._rgbw_script = None
        if (rgbw_action := config.get(CONF_RGBW_ACTION)) is not None:
            self._rgbw_script = Script(hass, rgbw_action, friendly_name, DOMAIN)
        self._rgbw_template = config.get(CONF_RGBW_TEMPLATE)
        self._rgbww_script = None
        if (rgbww_action := config.get(CONF_RGBWW_ACTION)) is not None:
            self._rgbww_script = Script(hass, rgbww_action, friendly_name, DOMAIN)
        self._rgbww_template = config.get(CONF_RGBWW_TEMPLATE)
        self._effect_script = None
        if (effect_action := config.get(CONF_EFFECT_ACTION)) is not None:
            self._effect_script = Script(hass, effect_action, friendly_name, DOMAIN)
        self._effect_list_template = config.get(CONF_EFFECT_LIST_TEMPLATE)
        self._effect_template = config.get(CONF_EFFECT_TEMPLATE)
        self._max_mireds_template = config.get(CONF_MAX_MIREDS_TEMPLATE)
        self._min_mireds_template = config.get(CONF_MIN_MIREDS_TEMPLATE)
        self._supports_transition_template = config.get(CONF_SUPPORTS_TRANSITION)

        self._state = False
        self._brightness = None
        self._temperature = None
        self._hs_color = None
        self._rgb_color = None
        self._rgbw_color = None
        self._rgbww_color = None
        self._effect = None
        self._effect_list = None
        self._color_mode = None
        self._max_mireds = None
        self._min_mireds = None
        self._supports_transition = False
        self._supported_color_modes = None

        color_modes = {ColorMode.ONOFF}
        if self._level_script is not None:
            color_modes.add(ColorMode.BRIGHTNESS)
        if self._temperature_script is not None:
            color_modes.add(ColorMode.COLOR_TEMP)
        if self._hs_script is not None:
            color_modes.add(ColorMode.HS)
        if self._color_script is not None:
            color_modes.add(ColorMode.HS)
        if self._rgb_script is not None:
            color_modes.add(ColorMode.RGB)
        if self._rgbw_script is not None:
            color_modes.add(ColorMode.RGBW)
        if self._rgbww_script is not None:
            color_modes.add(ColorMode.RGBWW)

        self._supported_color_modes = filter_supported_color_modes(color_modes)
        if len(self._supported_color_modes) > 1:
            self._color_mode = ColorMode.UNKNOWN
        if len(self._supported_color_modes) == 1:
            self._color_mode = next(iter(self._supported_color_modes))

        self._attr_supported_features = LightEntityFeature(0)
        if self._effect_script is not None:
            self._attr_supported_features |= LightEntityFeature.EFFECT
        if self._supports_transition is True:
            self._attr_supported_features |= LightEntityFeature.TRANSITION

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        return self._brightness

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature value in Kelvin."""
        if self._temperature is None:
            return None
        return color_util.color_temperature_mired_to_kelvin(self._temperature)

    @property
    def min_color_temp_kelvin(self) -> int:
        """Return the warmest color_temp_kelvin that this light supports."""
        if self._max_mireds is not None:
            return color_util.color_temperature_mired_to_kelvin(self._max_mireds)

        return DEFAULT_MIN_KELVIN

    @property
    def max_color_temp_kelvin(self) -> int:
        """Return the coldest color_temp_kelvin that this light supports."""
        if self._min_mireds is not None:
            return color_util.color_temperature_mired_to_kelvin(self._min_mireds)

        return DEFAULT_MAX_KELVIN

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value [float, float]."""
        return self._hs_color

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the rgb color value."""
        return self._rgb_color

    @property
    def rgbw_color(self) -> tuple[int, int, int, int] | None:
        """Return the rgbw color value."""
        return self._rgbw_color

    @property
    def rgbww_color(self) -> tuple[int, int, int, int, int] | None:
        """Return the rgbww color value."""
        return self._rgbww_color

    @property
    def effect(self) -> str | None:
        """Return the effect."""
        return self._effect

    @property
    def effect_list(self) -> list[str] | None:
        """Return the effect list."""
        return self._effect_list

    @property
    def color_mode(self):
        """Return current color mode."""
        return self._color_mode

    @property
    def supported_color_modes(self):
        """Flag supported color modes."""
        return self._supported_color_modes

    @property
    def is_on(self) -> bool | None:
        """Return true if device is on."""
        return self._state

    @callback
    def _async_setup_templates(self) -> None:
        """Set up templates."""
        if self._template:
            self.add_template_attribute(
                "_state", self._template, None, self._update_state
            )
        if self._level_template:
            self.add_template_attribute(
                "_brightness",
                self._level_template,
                None,
                self._update_brightness,
                none_on_template_error=True,
            )
        if self._max_mireds_template:
            self.add_template_attribute(
                "_max_mireds_template",
                self._max_mireds_template,
                None,
                self._update_max_mireds,
                none_on_template_error=True,
            )
        if self._min_mireds_template:
            self.add_template_attribute(
                "_min_mireds_template",
                self._min_mireds_template,
                None,
                self._update_min_mireds,
                none_on_template_error=True,
            )
        if self._temperature_template:
            self.add_template_attribute(
                "_temperature",
                self._temperature_template,
                None,
                self._update_temperature,
                none_on_template_error=True,
            )
        if self._color_template:
            self.add_template_attribute(
                "_hs_color",
                self._color_template,
                None,
                self._update_hs,
                none_on_template_error=True,
            )
        if self._hs_template:
            self.add_template_attribute(
                "_hs_color",
                self._hs_template,
                None,
                self._update_hs,
                none_on_template_error=True,
            )
        if self._rgb_template:
            self.add_template_attribute(
                "_rgb_color",
                self._rgb_template,
                None,
                self._update_rgb,
                none_on_template_error=True,
            )
        if self._rgbw_template:
            self.add_template_attribute(
                "_rgbw_color",
                self._rgbw_template,
                None,
                self._update_rgbw,
                none_on_template_error=True,
            )
        if self._rgbww_template:
            self.add_template_attribute(
                "_rgbww_color",
                self._rgbww_template,
                None,
                self._update_rgbww,
                none_on_template_error=True,
            )
        if self._effect_list_template:
            self.add_template_attribute(
                "_effect_list",
                self._effect_list_template,
                None,
                self._update_effect_list,
                none_on_template_error=True,
            )
        if self._effect_template:
            self.add_template_attribute(
                "_effect",
                self._effect_template,
                None,
                self._update_effect,
                none_on_template_error=True,
            )
        if self._supports_transition_template:
            self.add_template_attribute(
                "_supports_transition_template",
                self._supports_transition_template,
                None,
                self._update_supports_transition,
                none_on_template_error=True,
            )
        super()._async_setup_templates()

    async def async_turn_on(self, **kwargs: Any) -> None:  # noqa: C901
        """Turn the light on."""
        optimistic_set = False
        # set optimistic states
        if self._template is None:
            self._state = True
            optimistic_set = True

        if self._level_template is None and ATTR_BRIGHTNESS in kwargs:
            _LOGGER.debug(
                "Optimistically setting brightness to %s", kwargs[ATTR_BRIGHTNESS]
            )
            self._brightness = kwargs[ATTR_BRIGHTNESS]
            optimistic_set = True

        if self._temperature_template is None and ATTR_COLOR_TEMP_KELVIN in kwargs:
            color_temp = color_util.color_temperature_kelvin_to_mired(
                kwargs[ATTR_COLOR_TEMP_KELVIN]
            )
            _LOGGER.debug(
                "Optimistically setting color temperature to %s",
                color_temp,
            )
            self._color_mode = ColorMode.COLOR_TEMP
            self._temperature = color_temp
            if self._hs_template is None and self._color_template is None:
                self._hs_color = None
            if self._rgb_template is None:
                self._rgb_color = None
            if self._rgbw_template is None:
                self._rgbw_color = None
            if self._rgbww_template is None:
                self._rgbww_color = None
            optimistic_set = True

        if (
            self._hs_template is None
            and self._color_template is None
            and ATTR_HS_COLOR in kwargs
        ):
            _LOGGER.debug(
                "Optimistically setting hs color to %s",
                kwargs[ATTR_HS_COLOR],
            )
            self._color_mode = ColorMode.HS
            self._hs_color = kwargs[ATTR_HS_COLOR]
            if self._temperature_template is None:
                self._temperature = None
            if self._rgb_template is None:
                self._rgb_color = None
            if self._rgbw_template is None:
                self._rgbw_color = None
            if self._rgbww_template is None:
                self._rgbww_color = None
            optimistic_set = True

        if self._rgb_template is None and ATTR_RGB_COLOR in kwargs:
            _LOGGER.debug(
                "Optimistically setting rgb color to %s",
                kwargs[ATTR_RGB_COLOR],
            )
            self._color_mode = ColorMode.RGB
            self._rgb_color = kwargs[ATTR_RGB_COLOR]
            if self._temperature_template is None:
                self._temperature = None
            if self._hs_template is None and self._color_template is None:
                self._hs_color = None
            if self._rgbw_template is None:
                self._rgbw_color = None
            if self._rgbww_template is None:
                self._rgbww_color = None
            optimistic_set = True

        if self._rgbw_template is None and ATTR_RGBW_COLOR in kwargs:
            _LOGGER.debug(
                "Optimistically setting rgbw color to %s",
                kwargs[ATTR_RGBW_COLOR],
            )
            self._color_mode = ColorMode.RGBW
            self._rgbw_color = kwargs[ATTR_RGBW_COLOR]
            if self._temperature_template is None:
                self._temperature = None
            if self._hs_template is None and self._color_template is None:
                self._hs_color = None
            if self._rgb_template is None:
                self._rgb_color = None
            if self._rgbww_template is None:
                self._rgbww_color = None
            optimistic_set = True

        if self._rgbww_template is None and ATTR_RGBWW_COLOR in kwargs:
            _LOGGER.debug(
                "Optimistically setting rgbww color to %s",
                kwargs[ATTR_RGBWW_COLOR],
            )
            self._color_mode = ColorMode.RGBWW
            self._rgbww_color = kwargs[ATTR_RGBWW_COLOR]
            if self._temperature_template is None:
                self._temperature = None
            if self._hs_template is None and self._color_template is None:
                self._hs_color = None
            if self._rgb_template is None:
                self._rgb_color = None
            if self._rgbw_template is None:
                self._rgbw_color = None
            optimistic_set = True

        common_params = {}

        if ATTR_BRIGHTNESS in kwargs:
            common_params["brightness"] = kwargs[ATTR_BRIGHTNESS]

        if ATTR_TRANSITION in kwargs and self._supports_transition is True:
            common_params["transition"] = kwargs[ATTR_TRANSITION]

        if ATTR_COLOR_TEMP_KELVIN in kwargs and self._temperature_script:
            common_params["color_temp"] = color_util.color_temperature_kelvin_to_mired(
                kwargs[ATTR_COLOR_TEMP_KELVIN]
            )

            await self.async_run_script(
                self._temperature_script,
                run_variables=common_params,
                context=self._context,
            )
        elif ATTR_EFFECT in kwargs and self._effect_script:
            effect = kwargs[ATTR_EFFECT]
            if effect not in self._effect_list:
                _LOGGER.error(
                    "Received invalid effect: %s for entity %s. Expected one of: %s",
                    effect,
                    self.entity_id,
                    self._effect_list,
                    exc_info=True,
                )

            common_params["effect"] = effect

            await self.async_run_script(
                self._effect_script, run_variables=common_params, context=self._context
            )
        elif ATTR_HS_COLOR in kwargs and self._color_script:
            hs_value = kwargs[ATTR_HS_COLOR]
            common_params["hs"] = hs_value
            common_params["h"] = int(hs_value[0])
            common_params["s"] = int(hs_value[1])

            await self.async_run_script(
                self._color_script, run_variables=common_params, context=self._context
            )
        elif ATTR_HS_COLOR in kwargs and self._hs_script:
            hs_value = kwargs[ATTR_HS_COLOR]
            common_params["hs"] = hs_value
            common_params["h"] = int(hs_value[0])
            common_params["s"] = int(hs_value[1])

            await self.async_run_script(
                self._hs_script, run_variables=common_params, context=self._context
            )
        elif ATTR_RGBWW_COLOR in kwargs and self._rgbww_script:
            rgbww_value = kwargs[ATTR_RGBWW_COLOR]
            common_params["rgbww"] = rgbww_value
            common_params["rgb"] = (
                int(rgbww_value[0]),
                int(rgbww_value[1]),
                int(rgbww_value[2]),
            )
            common_params["r"] = int(rgbww_value[0])
            common_params["g"] = int(rgbww_value[1])
            common_params["b"] = int(rgbww_value[2])
            common_params["cw"] = int(rgbww_value[3])
            common_params["ww"] = int(rgbww_value[4])

            await self.async_run_script(
                self._rgbww_script, run_variables=common_params, context=self._context
            )
        elif ATTR_RGBW_COLOR in kwargs and self._rgbw_script:
            rgbw_value = kwargs[ATTR_RGBW_COLOR]
            common_params["rgbw"] = rgbw_value
            common_params["rgb"] = (
                int(rgbw_value[0]),
                int(rgbw_value[1]),
                int(rgbw_value[2]),
            )
            common_params["r"] = int(rgbw_value[0])
            common_params["g"] = int(rgbw_value[1])
            common_params["b"] = int(rgbw_value[2])
            common_params["w"] = int(rgbw_value[3])

            await self.async_run_script(
                self._rgbw_script, run_variables=common_params, context=self._context
            )
        elif ATTR_RGB_COLOR in kwargs and self._rgb_script:
            rgb_value = kwargs[ATTR_RGB_COLOR]
            common_params["rgb"] = rgb_value
            common_params["r"] = int(rgb_value[0])
            common_params["g"] = int(rgb_value[1])
            common_params["b"] = int(rgb_value[2])

            await self.async_run_script(
                self._rgb_script, run_variables=common_params, context=self._context
            )
        elif ATTR_BRIGHTNESS in kwargs and self._level_script:
            await self.async_run_script(
                self._level_script, run_variables=common_params, context=self._context
            )
        else:
            await self.async_run_script(
                self._on_script, run_variables=common_params, context=self._context
            )

        if optimistic_set:
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        if ATTR_TRANSITION in kwargs and self._supports_transition is True:
            await self.async_run_script(
                self._off_script,
                run_variables={"transition": kwargs[ATTR_TRANSITION]},
                context=self._context,
            )
        else:
            await self.async_run_script(self._off_script, context=self._context)
        if self._template is None:
            self._state = False
            self.async_write_ha_state()

    @callback
    def _update_brightness(self, brightness):
        """Update the brightness from the template."""
        try:
            if brightness in (None, "None", ""):
                self._brightness = None
                return
            if 0 <= int(brightness) <= 255:
                self._brightness = int(brightness)
            else:
                _LOGGER.error(
                    "Received invalid brightness : %s for entity %s. Expected: 0-255",
                    brightness,
                    self.entity_id,
                )
                self._brightness = None
        except ValueError:
            _LOGGER.exception(
                "Template must supply an integer brightness from 0-255, or 'None'"
            )
            self._brightness = None

    @callback
    def _update_effect_list(self, effect_list):
        """Update the effect list from the template."""
        if effect_list in (None, "None", ""):
            self._effect_list = None
            return

        if not isinstance(effect_list, list):
            _LOGGER.error(
                (
                    "Received invalid effect list: %s for entity %s. Expected list of"
                    " strings"
                ),
                effect_list,
                self.entity_id,
            )
            self._effect_list = None
            return

        if len(effect_list) == 0:
            self._effect_list = None
            return

        self._effect_list = effect_list

    @callback
    def _update_effect(self, effect):
        """Update the effect from the template."""
        if effect in (None, "None", ""):
            self._effect = None
            return

        if effect not in self._effect_list:
            _LOGGER.error(
                "Received invalid effect: %s for entity %s. Expected one of: %s",
                effect,
                self.entity_id,
                self._effect_list,
            )
            self._effect = None
            return

        self._effect = effect

    @callback
    def _update_state(self, result):
        """Update the state from the template."""
        if isinstance(result, TemplateError):
            # This behavior is legacy
            self._state = False
            if not self._availability_template:
                self._attr_available = True
            return

        if isinstance(result, bool):
            self._state = result
            return

        state = str(result).lower()
        if state in _VALID_STATES:
            self._state = state in ("true", STATE_ON)
            return

        _LOGGER.error(
            "Received invalid light is_on state: %s for entity %s. Expected: %s",
            state,
            self.entity_id,
            ", ".join(_VALID_STATES),
        )
        self._state = None

    @callback
    def _update_temperature(self, render):
        """Update the temperature from the template."""
        try:
            if render in (None, "None", ""):
                self._temperature = None
                return
            temperature = int(render)
            min_mireds = self._min_mireds or DEFAULT_MIN_MIREDS
            max_mireds = self._max_mireds or DEFAULT_MAX_MIREDS
            if min_mireds <= temperature <= max_mireds:
                self._temperature = temperature
            else:
                _LOGGER.error(
                    (
                        "Received invalid color temperature : %s for entity %s."
                        " Expected: %s-%s"
                    ),
                    temperature,
                    self.entity_id,
                    min_mireds,
                    max_mireds,
                )
                self._temperature = None
        except ValueError:
            _LOGGER.exception(
                "Template must supply an integer temperature within the range for"
                " this light, or 'None'"
            )
            self._temperature = None
        self._color_mode = ColorMode.COLOR_TEMP

    @callback
    def _update_hs(self, render):
        """Update the color from the template."""
        if render is None:
            self._hs_color = None
            return

        h_str = s_str = None
        if isinstance(render, str):
            if render in ("None", ""):
                self._hs_color = None
                return
            h_str, s_str = map(
                float, render.replace("(", "").replace(")", "").split(",", 1)
            )
        elif isinstance(render, (list, tuple)) and len(render) == 2:
            h_str, s_str = render

        if (
            h_str is not None
            and s_str is not None
            and isinstance(h_str, (int, float))
            and isinstance(s_str, (int, float))
            and 0 <= h_str <= 360
            and 0 <= s_str <= 100
        ):
            self._hs_color = (h_str, s_str)
        elif h_str is not None and s_str is not None:
            _LOGGER.error(
                (
                    "Received invalid hs_color : (%s, %s) for entity %s. Expected:"
                    " (0-360, 0-100)"
                ),
                h_str,
                s_str,
                self.entity_id,
            )
            self._hs_color = None
        else:
            _LOGGER.error(
                "Received invalid hs_color : (%s) for entity %s", render, self.entity_id
            )
            self._hs_color = None
        self._color_mode = ColorMode.HS

    @callback
    def _update_rgb(self, render):
        """Update the color from the template."""
        if render is None:
            self._rgb_color = None
            return

        r_int = g_int = b_int = None
        if isinstance(render, str):
            if render in ("None", ""):
                self._rgb_color = None
                return
            cleanup_char = ["(", ")", "[", "]", " "]
            for char in cleanup_char:
                render = render.replace(char, "")
            r_int, g_int, b_int = map(int, render.split(",", 3))
        elif isinstance(render, (list, tuple)) and len(render) == 3:
            r_int, g_int, b_int = render

        if all(
            value is not None and isinstance(value, (int, float)) and 0 <= value <= 255
            for value in (r_int, g_int, b_int)
        ):
            self._rgb_color = (r_int, g_int, b_int)
        elif any(
            isinstance(value, (int, float)) and not 0 <= value <= 255
            for value in (r_int, g_int, b_int)
        ):
            _LOGGER.error(
                "Received invalid rgb_color : (%s, %s, %s) for entity %s. Expected: (0-255, 0-255, 0-255)",
                r_int,
                g_int,
                b_int,
                self.entity_id,
            )
            self._rgb_color = None
        else:
            _LOGGER.error(
                "Received invalid rgb_color : (%s) for entity %s",
                render,
                self.entity_id,
            )
            self._rgb_color = None
        self._color_mode = ColorMode.RGB

    @callback
    def _update_rgbw(self, render):
        """Update the color from the template."""
        if render is None:
            self._rgbw_color = None
            return

        r_int = g_int = b_int = w_int = None
        if isinstance(render, str):
            if render in ("None", ""):
                self._rgb_color = None
                return
            cleanup_char = ["(", ")", "[", "]", " "]
            for char in cleanup_char:
                render = render.replace(char, "")
            r_int, g_int, b_int, w_int = map(int, render.split(",", 4))
        elif isinstance(render, (list, tuple)) and len(render) == 4:
            r_int, g_int, b_int, w_int = render

        if all(
            value is not None and isinstance(value, (int, float)) and 0 <= value <= 255
            for value in (r_int, g_int, b_int, w_int)
        ):
            self._rgbw_color = (r_int, g_int, b_int, w_int)
        elif any(
            isinstance(value, (int, float)) and not 0 <= value <= 255
            for value in (r_int, g_int, b_int, w_int)
        ):
            _LOGGER.error(
                "Received invalid rgb_color : (%s, %s, %s, %s) for entity %s. Expected: (0-255, 0-255, 0-255, 0-255)",
                r_int,
                g_int,
                b_int,
                w_int,
                self.entity_id,
            )
            self._rgbw_color = None
        else:
            _LOGGER.error(
                "Received invalid rgb_color : (%s) for entity %s",
                render,
                self.entity_id,
            )
            self._rgbw_color = None
        self._color_mode = ColorMode.RGBW

    @callback
    def _update_rgbww(self, render):
        """Update the color from the template."""
        if render is None:
            self._rgbww_color = None
            return

        r_int = g_int = b_int = cw_int = ww_int = None
        if isinstance(render, str):
            if render in ("None", ""):
                self._rgb_color = None
                return
            cleanup_char = ["(", ")", "[", "]", " "]
            for char in cleanup_char:
                render = render.replace(char, "")
            r_int, g_int, b_int, cw_int, ww_int = map(int, render.split(",", 5))
        elif isinstance(render, (list, tuple)) and len(render) == 5:
            r_int, g_int, b_int, cw_int, ww_int = render

        if all(
            value is not None and isinstance(value, (int, float)) and 0 <= value <= 255
            for value in (r_int, g_int, b_int, cw_int, ww_int)
        ):
            self._rgbww_color = (r_int, g_int, b_int, cw_int, ww_int)
        elif any(
            isinstance(value, (int, float)) and not 0 <= value <= 255
            for value in (r_int, g_int, b_int, cw_int, ww_int)
        ):
            _LOGGER.error(
                "Received invalid rgb_color : (%s, %s, %s, %s, %s) for entity %s. Expected: (0-255, 0-255, 0-255, 0-255)",
                r_int,
                g_int,
                b_int,
                cw_int,
                ww_int,
                self.entity_id,
            )
            self._rgbww_color = None
        else:
            _LOGGER.error(
                "Received invalid rgb_color : (%s) for entity %s",
                render,
                self.entity_id,
            )
            self._rgbww_color = None
        self._color_mode = ColorMode.RGBWW

    @callback
    def _update_max_mireds(self, render):
        """Update the max mireds from the template."""

        try:
            if render in (None, "None", ""):
                self._max_mireds = None
                return
            self._max_mireds = int(render)
        except ValueError:
            _LOGGER.exception(
                "Template must supply an integer temperature within the range for"
                " this light, or 'None'"
            )
            self._max_mireds = None

    @callback
    def _update_min_mireds(self, render):
        """Update the min mireds from the template."""
        try:
            if render in (None, "None", ""):
                self._min_mireds = None
                return
            self._min_mireds = int(render)
        except ValueError:
            _LOGGER.exception(
                "Template must supply an integer temperature within the range for"
                " this light, or 'None'"
            )
            self._min_mireds = None

    @callback
    def _update_supports_transition(self, render):
        """Update the supports transition from the template."""
        if render in (None, "None", ""):
            self._supports_transition = False
            return
        self._attr_supported_features &= LightEntityFeature.EFFECT
        self._supports_transition = bool(render)
        if self._supports_transition:
            self._attr_supported_features |= LightEntityFeature.TRANSITION
