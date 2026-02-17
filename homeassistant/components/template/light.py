"""Support for Template lights."""

from __future__ import annotations

from collections.abc import Callable
import contextlib
import logging
from typing import TYPE_CHECKING, Any

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
    DOMAIN as LIGHT_DOMAIN,
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA as LIGHT_PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
    LightEntityFeature,
    filter_supported_color_modes,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_EFFECT,
    CONF_ENTITY_ID,
    CONF_FRIENDLY_NAME,
    CONF_LIGHTS,
    CONF_NAME,
    CONF_RGB,
    CONF_STATE,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import color as color_util

from . import TriggerUpdateCoordinator, validators as template_validators
from .const import DOMAIN
from .entity import AbstractTemplateEntity
from .helpers import (
    async_setup_template_entry,
    async_setup_template_platform,
    async_setup_template_preview,
)
from .schemas import (
    TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA,
    TEMPLATE_ENTITY_COMMON_SCHEMA_LEGACY,
    TEMPLATE_ENTITY_OPTIMISTIC_SCHEMA,
    make_template_entity_common_modern_schema,
)
from .template_entity import TemplateEntity
from .trigger_entity import TriggerEntity

_LOGGER = logging.getLogger(__name__)

# Legacy
ATTR_COLOR_TEMP = "color_temp"
CONF_COLOR_ACTION = "set_color"
CONF_COLOR_TEMPLATE = "color_template"

CONF_HS = "hs"
CONF_HS_ACTION = "set_hs"
CONF_HS_TEMPLATE = "hs_template"
CONF_RGB_ACTION = "set_rgb"
CONF_RGB_TEMPLATE = "rgb_template"
CONF_RGBW = "rgbw"
CONF_RGBW_ACTION = "set_rgbw"
CONF_RGBW_TEMPLATE = "rgbw_template"
CONF_RGBWW = "rgbww"
CONF_RGBWW_ACTION = "set_rgbww"
CONF_RGBWW_TEMPLATE = "rgbww_template"
CONF_EFFECT_ACTION = "set_effect"
CONF_EFFECT_LIST = "effect_list"
CONF_EFFECT_LIST_TEMPLATE = "effect_list_template"
CONF_EFFECT_TEMPLATE = "effect_template"
CONF_LEVEL = "level"
CONF_LEVEL_ACTION = "set_level"
CONF_LEVEL_TEMPLATE = "level_template"
CONF_MAX_MIREDS = "max_mireds"
CONF_MAX_MIREDS_TEMPLATE = "max_mireds_template"
CONF_MIN_MIREDS = "min_mireds"
CONF_MIN_MIREDS_TEMPLATE = "min_mireds_template"
CONF_OFF_ACTION = "turn_off"
CONF_ON_ACTION = "turn_on"
CONF_SUPPORTS_TRANSITION = "supports_transition"
CONF_SUPPORTS_TRANSITION_TEMPLATE = "supports_transition_template"
CONF_TEMPERATURE_ACTION = "set_temperature"
CONF_TEMPERATURE = "temperature"
CONF_TEMPERATURE_TEMPLATE = "temperature_template"
CONF_WHITE_VALUE_ACTION = "set_white_value"
CONF_WHITE_VALUE = "white_value"
CONF_WHITE_VALUE_TEMPLATE = "white_value_template"

DEFAULT_MIN_MIREDS = 153
DEFAULT_MAX_MIREDS = 500

LEGACY_FIELDS = {
    CONF_COLOR_ACTION: CONF_HS_ACTION,
    CONF_COLOR_TEMPLATE: CONF_HS,
    CONF_EFFECT_LIST_TEMPLATE: CONF_EFFECT_LIST,
    CONF_EFFECT_TEMPLATE: CONF_EFFECT,
    CONF_HS_TEMPLATE: CONF_HS,
    CONF_LEVEL_TEMPLATE: CONF_LEVEL,
    CONF_MAX_MIREDS_TEMPLATE: CONF_MAX_MIREDS,
    CONF_MIN_MIREDS_TEMPLATE: CONF_MIN_MIREDS,
    CONF_RGB_TEMPLATE: CONF_RGB,
    CONF_RGBW_TEMPLATE: CONF_RGBW,
    CONF_RGBWW_TEMPLATE: CONF_RGBWW,
    CONF_SUPPORTS_TRANSITION_TEMPLATE: CONF_SUPPORTS_TRANSITION,
    CONF_TEMPERATURE_TEMPLATE: CONF_TEMPERATURE,
    CONF_VALUE_TEMPLATE: CONF_STATE,
    CONF_WHITE_VALUE_TEMPLATE: CONF_WHITE_VALUE,
}

DEFAULT_NAME = "Template Light"

LIGHT_COMMON_SCHEMA = vol.Schema(
    {
        vol.Inclusive(CONF_EFFECT_ACTION, "effect"): cv.SCRIPT_SCHEMA,
        vol.Inclusive(CONF_EFFECT_LIST, "effect"): cv.template,
        vol.Inclusive(CONF_EFFECT, "effect"): cv.template,
        vol.Optional(CONF_HS_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_HS): cv.template,
        vol.Optional(CONF_LEVEL_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_LEVEL): cv.template,
        vol.Optional(CONF_MAX_MIREDS): cv.template,
        vol.Optional(CONF_MIN_MIREDS): cv.template,
        vol.Required(CONF_OFF_ACTION): cv.SCRIPT_SCHEMA,
        vol.Required(CONF_ON_ACTION): cv.SCRIPT_SCHEMA,
        vol.Required(CONF_OFF_ACTION): cv.SCRIPT_SCHEMA,
        vol.Required(CONF_ON_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_RGB_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_RGB): cv.template,
        vol.Optional(CONF_RGBW_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_RGBW): cv.template,
        vol.Optional(CONF_RGBWW_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_RGBWW): cv.template,
        vol.Optional(CONF_STATE): cv.template,
        vol.Optional(CONF_SUPPORTS_TRANSITION): cv.template,
        vol.Optional(CONF_TEMPERATURE_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_TEMPERATURE): cv.template,
    }
)

LIGHT_YAML_SCHEMA = LIGHT_COMMON_SCHEMA.extend(
    TEMPLATE_ENTITY_OPTIMISTIC_SCHEMA
).extend(make_template_entity_common_modern_schema(LIGHT_DOMAIN, DEFAULT_NAME).schema)

LIGHT_LEGACY_YAML_SCHEMA = vol.All(
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
            vol.Optional(CONF_SUPPORTS_TRANSITION_TEMPLATE): cv.template,
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
        {vol.Required(CONF_LIGHTS): cv.schema_with_slug_keys(LIGHT_LEGACY_YAML_SCHEMA)}
    ),
)

LIGHT_CONFIG_ENTRY_SCHEMA = LIGHT_COMMON_SCHEMA.extend(
    TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA.schema
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the template lights."""
    await async_setup_template_platform(
        hass,
        LIGHT_DOMAIN,
        config,
        StateLightEntity,
        TriggerLightEntity,
        async_add_entities,
        discovery_info,
        LEGACY_FIELDS,
        legacy_key=CONF_LIGHTS,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize config entry."""
    await async_setup_template_entry(
        hass,
        config_entry,
        async_add_entities,
        StateLightEntity,
        LIGHT_CONFIG_ENTRY_SCHEMA,
        True,
    )


@callback
def async_create_preview_light(
    hass: HomeAssistant, name: str, config: dict[str, Any]
) -> StateLightEntity:
    """Create a preview."""
    return async_setup_template_preview(
        hass,
        name,
        config,
        StateLightEntity,
        LIGHT_CONFIG_ENTRY_SCHEMA,
        True,
    )


def _string_to_list(result: str) -> list[float]:
    for char in "()[] ":
        result = result.replace(char, "")
    return [float(v) for v in result.split(",")]


def hs_color_list(entity: AbstractTemplateLight) -> Callable[[Any], list[int] | None]:
    """Convert the result to a list of numbers that represent hue and saturation."""

    def convert(result: Any) -> list[int] | None:
        if template_validators.check_result_for_none(result):
            return None

        if isinstance(result, str):
            with contextlib.suppress(ValueError):
                result = _string_to_list(result)

        if (
            isinstance(result, (list, tuple))
            and len(result) == 2
            and all(isinstance(value, (int, float)) for value in result)
        ):
            hue, saturation = result
            if not (0 <= hue <= 360) or not (0 <= saturation <= 100):
                template_validators.log_validation_result_error(
                    entity,
                    CONF_HS,
                    result,
                    (
                        "expected a hue value between 0 and 360 and "
                        "a saturation value between 0 and 100: (0-360, 0-100)"
                    ),
                )
                return None

            return list(result)

        template_validators.log_validation_result_error(
            entity,
            CONF_HS,
            result,
            "expected a list of numbers: (0-360, 0-100)",
        )
        return None

    return convert


def rgb_color_list(
    entity: AbstractTemplateLight, attribute: str, length: int
) -> Callable[[Any], list[int] | None]:
    """Convert the result to a list of numbers that represent a color."""
    example = "[" + ", ".join(("0-255",) * length) + "]"
    message = f"expected a list of {length} numbers between 0 and 255: {example}"

    def convert(result: Any) -> list[int] | None:
        if template_validators.check_result_for_none(result):
            return None

        if isinstance(result, str):
            with contextlib.suppress(ValueError):
                result = _string_to_list(result)

        if (
            isinstance(result, (list, tuple))
            and len(result) == length
            and all(isinstance(value, (int, float)) for value in result)
        ):
            # Ensure the result are numbers between 0 and 255.
            if all(0 <= value <= 255 for value in result):
                return list(result)

        template_validators.log_validation_result_error(
            entity, attribute, result, message
        )
        return None

    return convert


class AbstractTemplateLight(AbstractTemplateEntity, LightEntity):
    """Representation of a template lights features."""

    _entity_id_format = ENTITY_ID_FORMAT
    _optimistic_entity = True
    _attr_max_color_temp_kelvin = DEFAULT_MAX_KELVIN
    _attr_min_color_temp_kelvin = DEFAULT_MIN_KELVIN

    # The super init is not called because TemplateEntity and TriggerEntity will call AbstractTemplateEntity.__init__.
    # This ensures that the __init__ on AbstractTemplateEntity is not called twice.
    def __init__(  # pylint: disable=super-init-not-called
        self, name: str, config: dict[str, Any]
    ) -> None:
        """Initialize the features."""

        # Setup state and brightness
        self.setup_state_template(
            CONF_STATE, "_attr_is_on", template_validators.boolean(self, CONF_STATE)
        )
        self.setup_template(
            CONF_LEVEL,
            "_attr_brightness",
            template_validators.number(self, CONF_LEVEL, 0, 255, int),
        )

        # Setup Color temperature
        self.setup_template(
            CONF_TEMPERATURE,
            "_attr_color_temp_kelvin",
            self._validate_temperature,
            self._update_color("_attr_color_temp_kelvin", ColorMode.COLOR_TEMP),
        )

        # Setup Hue Saturation
        self.setup_template(
            CONF_HS,
            "_attr_hs_color",
            hs_color_list(self),
            self._update_color("_attr_hs_color", ColorMode.HS),
            render_complex=True,
        )

        # Setup RGB Colors
        for option, attribute, length, colormode in (
            (CONF_RGB, "_attr_rgb_color", 3, ColorMode.RGB),
            (CONF_RGBW, "_attr_rgbw_color", 4, ColorMode.RGBW),
            (CONF_RGBWW, "_attr_rgbww_color", 5, ColorMode.RGBWW),
        ):
            self.setup_template(
                option,
                attribute,
                rgb_color_list(self, option, length),
                self._update_color(attribute, colormode),
                render_complex=True,
            )

        # Setup Effect templates
        self.setup_template(
            CONF_EFFECT_LIST,
            "_attr_effect_list",
            template_validators.list_of_strings(
                self, CONF_EFFECT_LIST, none_on_empty=True
            ),
            render_complex=True,
        )
        self.setup_template(
            CONF_EFFECT,
            "_attr_effect",
            template_validators.item_in_list(
                self, "_attr_effect", "_attr_effect_list", CONF_EFFECT_LIST
            ),
        )

        # Min/Max temperature templates
        self.setup_template(
            CONF_MAX_MIREDS,
            "_attr_max_color_temp_kelvin",
            template_validators.number(self, CONF_MAX_MIREDS),
            self._update_max_mireds,
        )
        self.setup_template(
            CONF_MIN_MIREDS,
            "_attr_min_color_temp_kelvin",
            template_validators.number(self, CONF_MIN_MIREDS),
            self._update_min_mireds,
        )

        # Transition
        self.setup_template(
            CONF_SUPPORTS_TRANSITION,
            "_supports_transition_template",
            template_validators.boolean(self, CONF_SUPPORTS_TRANSITION),
            self._update_supports_transition,
        )

        # Stored values for template attributes
        self._supports_transition = False

        color_modes = {ColorMode.ONOFF}
        for action_id, color_mode in (
            (CONF_ON_ACTION, None),
            (CONF_OFF_ACTION, None),
            (CONF_EFFECT_ACTION, None),
            (CONF_TEMPERATURE_ACTION, ColorMode.COLOR_TEMP),
            (CONF_LEVEL_ACTION, ColorMode.BRIGHTNESS),
            (CONF_HS_ACTION, ColorMode.HS),
            (CONF_RGB_ACTION, ColorMode.RGB),
            (CONF_RGBW_ACTION, ColorMode.RGBW),
            (CONF_RGBWW_ACTION, ColorMode.RGBWW),
        ):
            if (action_config := config.get(action_id)) is not None:
                self.add_script(action_id, action_config, name, DOMAIN)
                if color_mode:
                    color_modes.add(color_mode)

        self._attr_supported_color_modes = filter_supported_color_modes(color_modes)
        if len(self._attr_supported_color_modes) > 1:
            self._attr_color_mode = ColorMode.UNKNOWN
        if len(self._attr_supported_color_modes) == 1:
            self._attr_color_mode = next(iter(self._attr_supported_color_modes))

        self._attr_supported_features = LightEntityFeature(0)
        if self._action_scripts.get(CONF_EFFECT_ACTION):
            self._attr_supported_features |= LightEntityFeature.EFFECT
        if self._supports_transition is True:
            self._attr_supported_features |= LightEntityFeature.TRANSITION

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        optimistic_set = self.set_optimistic_attributes(**kwargs)
        script_id, script_params = self.get_registered_script(**kwargs)
        await self.async_run_script(
            self._action_scripts[script_id],
            run_variables=script_params,
            context=self._context,
        )

        if optimistic_set:
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        off_script = self._action_scripts[CONF_OFF_ACTION]
        if ATTR_TRANSITION in kwargs and self._supports_transition is True:
            await self.async_run_script(
                off_script,
                run_variables={"transition": kwargs[ATTR_TRANSITION]},
                context=self._context,
            )
        else:
            await self.async_run_script(off_script, context=self._context)
        if self._attr_assumed_state:
            self._attr_is_on = False
            self.async_write_ha_state()

    def set_optimistic_attributes(self, **kwargs) -> bool:
        """Update attributes which should be set optimistically.

        Returns True if any attribute was updated.
        """
        optimistic_set = False
        if self._attr_assumed_state:
            self._attr_is_on = True
            optimistic_set = True

        if CONF_LEVEL not in self._templates and ATTR_BRIGHTNESS in kwargs:
            _LOGGER.debug(
                "Optimistically setting brightness to %s", kwargs[ATTR_BRIGHTNESS]
            )
            self._attr_brightness = kwargs[ATTR_BRIGHTNESS]
            optimistic_set = True

        if CONF_TEMPERATURE not in self._templates and ATTR_COLOR_TEMP_KELVIN in kwargs:
            self._set_optimistic_color(
                "color temperature",
                "_attr_color_temp_kelvin",
                kwargs[ATTR_COLOR_TEMP_KELVIN],
                ColorMode.COLOR_TEMP,
            )
            optimistic_set = True

        if CONF_TEMPERATURE not in self._templates and ATTR_COLOR_TEMP in kwargs:
            self._set_optimistic_color(
                "color temperature",
                "_attr_color_temp_kelvin",
                color_util.color_temperature_mired_to_kelvin(kwargs[ATTR_COLOR_TEMP]),
                ColorMode.COLOR_TEMP,
            )
            optimistic_set = True

        if CONF_HS not in self._templates and ATTR_HS_COLOR in kwargs:
            self._set_optimistic_color(
                "hs color", "_attr_hs_color", kwargs[ATTR_HS_COLOR], ColorMode.HS
            )
            optimistic_set = True

        if CONF_RGB not in self._templates and ATTR_RGB_COLOR in kwargs:
            self._set_optimistic_color(
                "rgb color", "_attr_rgb_color", kwargs[ATTR_RGB_COLOR], ColorMode.RGB
            )
            optimistic_set = True

        if CONF_RGBW not in self._templates and ATTR_RGBW_COLOR in kwargs:
            self._set_optimistic_color(
                "rgbw color",
                "_attr_rgbw_color",
                kwargs[ATTR_RGBW_COLOR],
                ColorMode.RGBW,
            )
            optimistic_set = True

        if CONF_RGBWW not in self._templates and ATTR_RGBWW_COLOR in kwargs:
            self._set_optimistic_color(
                "rgbww color",
                "_attr_rgbww_color",
                kwargs[ATTR_RGBWW_COLOR],
                ColorMode.RGBWW,
            )
            optimistic_set = True

        if optimistic_set and not self._attr_assumed_state:
            # If we are optmistically setting color or level but the state template
            # has not rendered, optimisically set the state to 'on'.
            self._attr_is_on = True

        return optimistic_set

    def _set_optimistic_color(
        self, description: str, attribute: str, value: Any, color_mode: ColorMode
    ) -> None:
        _LOGGER.debug(
            "Optimistically setting %s to %s",
            description,
            value,
        )

        self._attr_color_mode = color_mode
        setattr(self, attribute, value)

        for option, attr in (
            (CONF_TEMPERATURE, "_attr_color_temp_kelvin"),
            (CONF_HS, "_attr_hs_color"),
            (CONF_RGB, "_attr_rgb_color"),
            (CONF_RGBW, "_attr_rgbw_color"),
            (CONF_RGBWW, "_attr_rgbww_color"),
        ):
            if attribute == attr:
                continue

            if option not in self._templates:
                setattr(self, attr, None)

    def get_registered_script(self, **kwargs) -> tuple[str, dict]:
        """Get registered script for turn_on."""
        common_params = {}

        if ATTR_BRIGHTNESS in kwargs:
            common_params["brightness"] = kwargs[ATTR_BRIGHTNESS]

        if ATTR_TRANSITION in kwargs and self._supports_transition is True:
            common_params["transition"] = kwargs[ATTR_TRANSITION]

        if (
            ATTR_COLOR_TEMP_KELVIN in kwargs
            and (script := CONF_TEMPERATURE_ACTION) in self._action_scripts
        ):
            kelvin = kwargs[ATTR_COLOR_TEMP_KELVIN]
            common_params[ATTR_COLOR_TEMP_KELVIN] = kelvin
            common_params[ATTR_COLOR_TEMP] = (
                color_util.color_temperature_kelvin_to_mired(kelvin)
            )

            return (script, common_params)

        if (
            ATTR_EFFECT in kwargs
            and (script := CONF_EFFECT_ACTION) in self._action_scripts
        ):
            assert self._attr_effect_list is not None
            effect = kwargs[ATTR_EFFECT]
            if (
                self._attr_effect_list is not None
                and effect not in self._attr_effect_list
            ):
                _LOGGER.error(
                    "Received invalid effect: %s for entity %s. Expected one of: %s",
                    effect,
                    self.entity_id,
                    self._attr_effect_list,
                )

            common_params["effect"] = effect

            return (script, common_params)

        if (
            ATTR_HS_COLOR in kwargs
            and (script := CONF_HS_ACTION) in self._action_scripts
        ):
            hs_value = kwargs[ATTR_HS_COLOR]
            common_params["hs"] = hs_value
            common_params["h"] = int(hs_value[0])
            common_params["s"] = int(hs_value[1])

            return (script, common_params)

        if (
            ATTR_RGBWW_COLOR in kwargs
            and (script := CONF_RGBWW_ACTION) in self._action_scripts
        ):
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

            return (script, common_params)

        if (
            ATTR_RGBW_COLOR in kwargs
            and (script := CONF_RGBW_ACTION) in self._action_scripts
        ):
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

            return (script, common_params)

        if (
            ATTR_RGB_COLOR in kwargs
            and (script := CONF_RGB_ACTION) in self._action_scripts
        ):
            rgb_value = kwargs[ATTR_RGB_COLOR]
            common_params["rgb"] = rgb_value
            common_params["r"] = int(rgb_value[0])
            common_params["g"] = int(rgb_value[1])
            common_params["b"] = int(rgb_value[2])

            return (script, common_params)

        if (
            ATTR_BRIGHTNESS in kwargs
            and (script := CONF_LEVEL_ACTION) in self._action_scripts
        ):
            return (script, common_params)

        return (CONF_ON_ACTION, common_params)

    def _update_color(
        self, attribute: str, color_mode: ColorMode
    ) -> Callable[[Any], None]:
        """Update the color."""

        def update(render) -> None:
            if render is None:
                setattr(self, attribute, None)
                return

            setattr(self, attribute, render)
            self._attr_color_mode = color_mode

        return update

    @callback
    def _validate_temperature(self, result: Any) -> int | None:
        """Validate the temperature from the template."""
        if template_validators.check_result_for_none(result):
            return None

        if (min_kelvin := self._attr_min_color_temp_kelvin) is not None:
            max_mireds = color_util.color_temperature_kelvin_to_mired(min_kelvin)
        else:
            max_mireds = DEFAULT_MAX_MIREDS

        if (max_kelvin := self._attr_max_color_temp_kelvin) is not None:
            min_mireds = color_util.color_temperature_kelvin_to_mired(max_kelvin)
        else:
            min_mireds = DEFAULT_MIN_MIREDS

        if isinstance(result, (int, float)) and min_mireds <= result <= max_mireds:
            return color_util.color_temperature_mired_to_kelvin(result)

        template_validators.log_validation_result_error(
            self,
            CONF_TEMPERATURE,
            result,
            f"expected a number between {min_mireds} and {max_mireds}",
        )
        return None

    @callback
    def _update_max_mireds(self, render):
        """Update the max mireds from the template."""
        if render is None:
            self._attr_min_color_temp_kelvin = DEFAULT_MIN_KELVIN
            return

        try:
            self._attr_min_color_temp_kelvin = (
                color_util.color_temperature_mired_to_kelvin(int(render))
            )
        except ValueError:
            _LOGGER.exception(
                "Template must supply an integer temperature within the range for"
                " this light, or 'None'"
            )
            self._attr_min_color_temp_kelvin = DEFAULT_MIN_KELVIN

    @callback
    def _update_min_mireds(self, render):
        """Update the min mireds from the template."""
        if render is None:
            self._attr_max_color_temp_kelvin = DEFAULT_MAX_KELVIN
            return

        try:
            self._attr_max_color_temp_kelvin = (
                color_util.color_temperature_mired_to_kelvin(int(render))
            )
        except ValueError:
            _LOGGER.exception(
                "Template must supply an integer temperature within the range for"
                " this light, or 'None'"
            )
            self._attr_max_color_temp_kelvin = DEFAULT_MAX_KELVIN

    @callback
    def _update_supports_transition(self, render):
        """Update the supports transition from the template."""
        if render is None:
            self._supports_transition = False
            return
        self._attr_supported_features &= ~LightEntityFeature.TRANSITION
        self._supports_transition = bool(render)
        if self._supports_transition:
            self._attr_supported_features |= LightEntityFeature.TRANSITION


class StateLightEntity(TemplateEntity, AbstractTemplateLight):
    """Representation of a templated Light, including dimmable."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict[str, Any],
        unique_id: str | None,
    ) -> None:
        """Initialize the light."""
        TemplateEntity.__init__(self, hass, config, unique_id)
        name = self._attr_name
        if TYPE_CHECKING:
            assert name is not None
        AbstractTemplateLight.__init__(self, name, config)


class TriggerLightEntity(TriggerEntity, AbstractTemplateLight):
    """Light entity based on trigger data."""

    domain = LIGHT_DOMAIN

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: TriggerUpdateCoordinator,
        config: ConfigType,
    ) -> None:
        """Initialize the entity."""
        TriggerEntity.__init__(self, hass, coordinator, config)
        # Render the _attr_name before initializing TemplateLightEntity
        self._attr_name = name = self._rendered.get(CONF_NAME, DEFAULT_NAME)
        AbstractTemplateLight.__init__(self, name, config)
