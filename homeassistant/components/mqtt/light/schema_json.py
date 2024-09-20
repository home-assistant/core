"""Support for MQTT JSON lights."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
import logging
from typing import TYPE_CHECKING, Any, cast

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_FLASH,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_TRANSITION,
    ATTR_WHITE,
    ATTR_XY_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    ENTITY_ID_FORMAT,
    FLASH_LONG,
    FLASH_SHORT,
    VALID_COLOR_MODES,
    ColorMode,
    LightEntity,
    LightEntityFeature,
    brightness_supported,
    color_supported,
    filter_supported_color_modes,
    valid_supported_color_modes,
)
from homeassistant.const import (
    CONF_BRIGHTNESS,
    CONF_COLOR_TEMP,
    CONF_EFFECT,
    CONF_HS,
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_RGB,
    CONF_XY,
    STATE_ON,
)
from homeassistant.core import async_get_hass, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.json import json_dumps
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, VolSchemaType
import homeassistant.util.color as color_util
from homeassistant.util.json import json_loads_object
from homeassistant.util.yaml import dump as yaml_dump

from .. import subscription
from ..config import DEFAULT_QOS, DEFAULT_RETAIN, MQTT_RW_SCHEMA
from ..const import (
    CONF_COMMAND_TOPIC,
    CONF_QOS,
    CONF_RETAIN,
    CONF_STATE_TOPIC,
    DOMAIN as MQTT_DOMAIN,
)
from ..entity import MqttEntity
from ..models import ReceiveMessage
from ..schemas import MQTT_ENTITY_COMMON_SCHEMA
from ..util import valid_subscribe_topic
from .schema import MQTT_LIGHT_SCHEMA_SCHEMA
from .schema_basic import (
    CONF_BRIGHTNESS_SCALE,
    CONF_WHITE_SCALE,
    MQTT_LIGHT_ATTRIBUTES_BLOCKED,
)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "mqtt_json"

DEFAULT_BRIGHTNESS = False
DEFAULT_COLOR_MODE = False
DEFAULT_COLOR_TEMP = False
DEFAULT_EFFECT = False
DEFAULT_FLASH_TIME_LONG = 10
DEFAULT_FLASH_TIME_SHORT = 2
DEFAULT_NAME = "MQTT JSON Light"
DEFAULT_RGB = False
DEFAULT_XY = False
DEFAULT_HS = False
DEFAULT_BRIGHTNESS_SCALE = 255
DEFAULT_WHITE_SCALE = 255

CONF_COLOR_MODE = "color_mode"
CONF_SUPPORTED_COLOR_MODES = "supported_color_modes"

CONF_EFFECT_LIST = "effect_list"

CONF_FLASH_TIME_LONG = "flash_time_long"
CONF_FLASH_TIME_SHORT = "flash_time_short"

CONF_MAX_MIREDS = "max_mireds"
CONF_MIN_MIREDS = "min_mireds"


def valid_color_configuration(
    setup_from_yaml: bool,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Test color_mode is not combined with deprecated config."""

    def _valid_color_configuration(config: ConfigType) -> ConfigType:
        deprecated = {CONF_COLOR_TEMP, CONF_HS, CONF_RGB, CONF_XY}
        deprecated_flags_used = any(config.get(key) for key in deprecated)
        if config.get(CONF_SUPPORTED_COLOR_MODES):
            if deprecated_flags_used:
                raise vol.Invalid(
                    "supported_color_modes must not "
                    f"be combined with any of {deprecated}"
                )
        elif deprecated_flags_used:
            deprecated_flags = ", ".join(key for key in deprecated if key in config)
            _LOGGER.warning(
                "Deprecated flags [%s] used in MQTT JSON light config "
                "for handling color mode, please use `supported_color_modes` instead. "
                "Got: %s. This will stop working in Home Assistant Core 2025.3",
                deprecated_flags,
                config,
            )
            if not setup_from_yaml:
                return config
            issue_id = hex(hash(frozenset(config)))
            yaml_config_str = yaml_dump(config)
            learn_more_url = (
                "https://www.home-assistant.io/integrations/"
                f"{LIGHT_DOMAIN}.mqtt/#json-schema"
            )
            hass = async_get_hass()
            async_create_issue(
                hass,
                MQTT_DOMAIN,
                issue_id,
                issue_domain=LIGHT_DOMAIN,
                is_fixable=False,
                severity=IssueSeverity.WARNING,
                learn_more_url=learn_more_url,
                translation_placeholders={
                    "deprecated_flags": deprecated_flags,
                    "config": yaml_config_str,
                },
                translation_key="deprecated_color_handling",
            )

        if CONF_COLOR_MODE in config:
            _LOGGER.warning(
                "Deprecated flag `color_mode` used in MQTT JSON light config "
                ", the `color_mode` flag is not used anymore and should be removed. "
                "Got: %s. This will stop working in Home Assistant Core 2025.3",
                config,
            )
            if not setup_from_yaml:
                return config
            issue_id = hex(hash(frozenset(config)))
            yaml_config_str = yaml_dump(config)
            learn_more_url = (
                "https://www.home-assistant.io/integrations/"
                f"{LIGHT_DOMAIN}.mqtt/#json-schema"
            )
            hass = async_get_hass()
            async_create_issue(
                hass,
                MQTT_DOMAIN,
                issue_id,
                breaks_in_ha_version="2025.3.0",
                issue_domain=LIGHT_DOMAIN,
                is_fixable=False,
                severity=IssueSeverity.WARNING,
                learn_more_url=learn_more_url,
                translation_placeholders={
                    "config": yaml_config_str,
                },
                translation_key="deprecated_color_mode_flag",
            )

        return config

    return _valid_color_configuration


_PLATFORM_SCHEMA_BASE = (
    MQTT_RW_SCHEMA.extend(
        {
            vol.Optional(CONF_BRIGHTNESS, default=DEFAULT_BRIGHTNESS): cv.boolean,
            vol.Optional(
                CONF_BRIGHTNESS_SCALE, default=DEFAULT_BRIGHTNESS_SCALE
            ): vol.All(vol.Coerce(int), vol.Range(min=1)),
            # CONF_COLOR_MODE was deprecated with HA Core 2024.4 and will be
            # removed with HA Core 2025.3
            vol.Optional(CONF_COLOR_MODE): cv.boolean,
            # CONF_COLOR_TEMP was deprecated with HA Core 2024.4 and will be
            # removed with HA Core 2025.3
            vol.Optional(CONF_COLOR_TEMP, default=DEFAULT_COLOR_TEMP): cv.boolean,
            vol.Optional(CONF_EFFECT, default=DEFAULT_EFFECT): cv.boolean,
            vol.Optional(CONF_EFFECT_LIST): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(
                CONF_FLASH_TIME_LONG, default=DEFAULT_FLASH_TIME_LONG
            ): cv.positive_int,
            vol.Optional(
                CONF_FLASH_TIME_SHORT, default=DEFAULT_FLASH_TIME_SHORT
            ): cv.positive_int,
            # CONF_HS was deprecated with HA Core 2024.4 and will be
            # removed with HA Core 2025.3
            vol.Optional(CONF_HS, default=DEFAULT_HS): cv.boolean,
            vol.Optional(CONF_MAX_MIREDS): cv.positive_int,
            vol.Optional(CONF_MIN_MIREDS): cv.positive_int,
            vol.Optional(CONF_NAME): vol.Any(cv.string, None),
            vol.Optional(CONF_QOS, default=DEFAULT_QOS): vol.All(
                vol.Coerce(int), vol.In([0, 1, 2])
            ),
            vol.Optional(CONF_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
            # CONF_RGB was deprecated with HA Core 2024.4 and will be
            # removed with HA Core 2025.3
            vol.Optional(CONF_RGB, default=DEFAULT_RGB): cv.boolean,
            vol.Optional(CONF_STATE_TOPIC): valid_subscribe_topic,
            vol.Optional(CONF_SUPPORTED_COLOR_MODES): vol.All(
                cv.ensure_list,
                [vol.In(VALID_COLOR_MODES)],
                vol.Unique(),
                valid_supported_color_modes,
            ),
            vol.Optional(CONF_WHITE_SCALE, default=DEFAULT_WHITE_SCALE): vol.All(
                vol.Coerce(int), vol.Range(min=1)
            ),
            # CONF_XY was deprecated with HA Core 2024.4 and will be
            # removed with HA Core 2025.3
            vol.Optional(CONF_XY, default=DEFAULT_XY): cv.boolean,
        },
    )
    .extend(MQTT_ENTITY_COMMON_SCHEMA.schema)
    .extend(MQTT_LIGHT_SCHEMA_SCHEMA.schema)
)

DISCOVERY_SCHEMA_JSON = vol.All(
    valid_color_configuration(False),
    _PLATFORM_SCHEMA_BASE.extend({}, extra=vol.REMOVE_EXTRA),
)

PLATFORM_SCHEMA_MODERN_JSON = vol.All(
    valid_color_configuration(True),
    _PLATFORM_SCHEMA_BASE,
)


class MqttLightJson(MqttEntity, LightEntity, RestoreEntity):
    """Representation of a MQTT JSON light."""

    _default_name = DEFAULT_NAME
    _entity_id_format = ENTITY_ID_FORMAT
    _attributes_extra_blocked = MQTT_LIGHT_ATTRIBUTES_BLOCKED

    _fixed_color_mode: ColorMode | str | None = None
    _flash_times: dict[str, int | None]
    _topic: dict[str, str | None]
    _optimistic: bool

    _deprecated_color_handling: bool = False

    @staticmethod
    def config_schema() -> VolSchemaType:
        """Return the config schema."""
        return DISCOVERY_SCHEMA_JSON

    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""
        self._attr_max_mireds = config.get(CONF_MAX_MIREDS, super().max_mireds)
        self._attr_min_mireds = config.get(CONF_MIN_MIREDS, super().min_mireds)
        self._attr_effect_list = config.get(CONF_EFFECT_LIST)

        self._topic = {
            key: config.get(key) for key in (CONF_STATE_TOPIC, CONF_COMMAND_TOPIC)
        }
        optimistic: bool = config[CONF_OPTIMISTIC]
        self._optimistic = optimistic or self._topic[CONF_STATE_TOPIC] is None
        self._attr_assumed_state = bool(self._optimistic)

        self._flash_times = {
            key: config.get(key)
            for key in (CONF_FLASH_TIME_SHORT, CONF_FLASH_TIME_LONG)
        }

        self._attr_supported_features = (
            LightEntityFeature.TRANSITION | LightEntityFeature.FLASH
        )
        self._attr_supported_features |= (
            config[CONF_EFFECT] and LightEntityFeature.EFFECT
        )
        if supported_color_modes := self._config.get(CONF_SUPPORTED_COLOR_MODES):
            self._attr_supported_color_modes = supported_color_modes
            if self.supported_color_modes and len(self.supported_color_modes) == 1:
                self._attr_color_mode = next(iter(self.supported_color_modes))
            else:
                self._attr_color_mode = ColorMode.UNKNOWN
        else:
            self._deprecated_color_handling = True
            color_modes = {ColorMode.ONOFF}
            if config[CONF_BRIGHTNESS]:
                color_modes.add(ColorMode.BRIGHTNESS)
            if config[CONF_COLOR_TEMP]:
                color_modes.add(ColorMode.COLOR_TEMP)
            if config[CONF_HS] or config[CONF_RGB] or config[CONF_XY]:
                color_modes.add(ColorMode.HS)
            self._attr_supported_color_modes = filter_supported_color_modes(color_modes)
            if self.supported_color_modes and len(self.supported_color_modes) == 1:
                self._fixed_color_mode = next(iter(self.supported_color_modes))

    def _update_color(self, values: dict[str, Any]) -> None:
        if self._deprecated_color_handling:
            # Deprecated color handling
            try:
                red = int(values["color"]["r"])
                green = int(values["color"]["g"])
                blue = int(values["color"]["b"])
                self._attr_hs_color = color_util.color_RGB_to_hs(red, green, blue)
            except KeyError:
                pass
            except ValueError:
                _LOGGER.warning(
                    "Invalid RGB color value '%s' received for entity %s",
                    values,
                    self.entity_id,
                )
                return

            try:
                x_color = float(values["color"]["x"])
                y_color = float(values["color"]["y"])
                self._attr_hs_color = color_util.color_xy_to_hs(x_color, y_color)
            except KeyError:
                pass
            except ValueError:
                _LOGGER.warning(
                    "Invalid XY color value '%s' received for entity %s",
                    values,
                    self.entity_id,
                )
                return

            try:
                hue = float(values["color"]["h"])
                saturation = float(values["color"]["s"])
                self._attr_hs_color = (hue, saturation)
            except KeyError:
                pass
            except ValueError:
                _LOGGER.warning(
                    "Invalid HS color value '%s' received for entity %s",
                    values,
                    self.entity_id,
                )
                return
        else:
            color_mode: str = values["color_mode"]
            if not self._supports_color_mode(color_mode):
                _LOGGER.warning(
                    "Invalid color mode '%s' received for entity %s",
                    color_mode,
                    self.entity_id,
                )
                return
            try:
                if color_mode == ColorMode.COLOR_TEMP:
                    self._attr_color_temp = int(values["color_temp"])
                    self._attr_color_mode = ColorMode.COLOR_TEMP
                elif color_mode == ColorMode.HS:
                    hue = float(values["color"]["h"])
                    saturation = float(values["color"]["s"])
                    self._attr_color_mode = ColorMode.HS
                    self._attr_hs_color = (hue, saturation)
                elif color_mode == ColorMode.RGB:
                    r = int(values["color"]["r"])
                    g = int(values["color"]["g"])
                    b = int(values["color"]["b"])
                    self._attr_color_mode = ColorMode.RGB
                    self._attr_rgb_color = (r, g, b)
                elif color_mode == ColorMode.RGBW:
                    r = int(values["color"]["r"])
                    g = int(values["color"]["g"])
                    b = int(values["color"]["b"])
                    w = int(values["color"]["w"])
                    self._attr_color_mode = ColorMode.RGBW
                    self._attr_rgbw_color = (r, g, b, w)
                elif color_mode == ColorMode.RGBWW:
                    r = int(values["color"]["r"])
                    g = int(values["color"]["g"])
                    b = int(values["color"]["b"])
                    c = int(values["color"]["c"])
                    w = int(values["color"]["w"])
                    self._attr_color_mode = ColorMode.RGBWW
                    self._attr_rgbww_color = (r, g, b, c, w)
                elif color_mode == ColorMode.WHITE:
                    self._attr_color_mode = ColorMode.WHITE
                elif color_mode == ColorMode.XY:
                    x = float(values["color"]["x"])
                    y = float(values["color"]["y"])
                    self._attr_color_mode = ColorMode.XY
                    self._attr_xy_color = (x, y)
            except (KeyError, ValueError):
                _LOGGER.warning(
                    "Invalid or incomplete color value '%s' received for entity %s",
                    values,
                    self.entity_id,
                )

    @callback
    def _state_received(self, msg: ReceiveMessage) -> None:
        """Handle new MQTT messages."""
        values = json_loads_object(msg.payload)

        if values["state"] == "ON":
            self._attr_is_on = True
        elif values["state"] == "OFF":
            self._attr_is_on = False
        elif values["state"] is None:
            self._attr_is_on = None

        if (
            self._deprecated_color_handling
            and color_supported(self.supported_color_modes)
            and "color" in values
        ):
            # Deprecated color handling
            if values["color"] is None:
                self._attr_hs_color = None
            else:
                self._update_color(values)

        if not self._deprecated_color_handling and "color_mode" in values:
            self._update_color(values)

        if brightness_supported(self.supported_color_modes):
            try:
                if brightness := values["brightness"]:
                    if TYPE_CHECKING:
                        assert isinstance(brightness, float)
                    self._attr_brightness = color_util.value_to_brightness(
                        (1, self._config[CONF_BRIGHTNESS_SCALE]), brightness
                    )
                else:
                    _LOGGER.debug(
                        "Ignoring zero brightness value for entity %s",
                        self.entity_id,
                    )

            except KeyError:
                pass
            except (TypeError, ValueError):
                _LOGGER.warning(
                    "Invalid brightness value '%s' received for entity %s",
                    values["brightness"],
                    self.entity_id,
                )

        if (
            self._deprecated_color_handling
            and self.supported_color_modes
            and ColorMode.COLOR_TEMP in self.supported_color_modes
        ):
            # Deprecated color handling
            try:
                if values["color_temp"] is None:
                    self._attr_color_temp = None
                else:
                    self._attr_color_temp = int(values["color_temp"])  # type: ignore[arg-type]
            except KeyError:
                pass
            except ValueError:
                _LOGGER.warning(
                    "Invalid color temp value '%s' received for entity %s",
                    values["color_temp"],
                    self.entity_id,
                )
            # Allow to switch back to color_temp
            if "color" not in values:
                self._attr_hs_color = None

        if self.supported_features and LightEntityFeature.EFFECT:
            with suppress(KeyError):
                self._attr_effect = cast(str, values["effect"])

    @callback
    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        self.add_subscription(
            CONF_STATE_TOPIC,
            self._state_received,
            {
                "_attr_brightness",
                "_attr_color_temp",
                "_attr_effect",
                "_attr_hs_color",
                "_attr_is_on",
                "_attr_rgb_color",
                "_attr_rgbw_color",
                "_attr_rgbww_color",
                "_attr_xy_color",
                "color_mode",
            },
        )

    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        subscription.async_subscribe_topics_internal(self.hass, self._sub_state)

        last_state = await self.async_get_last_state()
        if self._optimistic and last_state:
            self._attr_is_on = last_state.state == STATE_ON
            last_attributes = last_state.attributes
            self._attr_brightness = last_attributes.get(
                ATTR_BRIGHTNESS, self.brightness
            )
            self._attr_color_mode = last_attributes.get(
                ATTR_COLOR_MODE, self.color_mode
            )
            self._attr_color_temp = last_attributes.get(
                ATTR_COLOR_TEMP, self.color_temp
            )
            self._attr_effect = last_attributes.get(ATTR_EFFECT, self.effect)
            self._attr_hs_color = last_attributes.get(ATTR_HS_COLOR, self.hs_color)
            self._attr_rgb_color = last_attributes.get(ATTR_RGB_COLOR, self.rgb_color)
            self._attr_rgbw_color = last_attributes.get(
                ATTR_RGBW_COLOR, self.rgbw_color
            )
            self._attr_rgbww_color = last_attributes.get(
                ATTR_RGBWW_COLOR, self.rgbww_color
            )
            self._attr_xy_color = last_attributes.get(ATTR_XY_COLOR, self.xy_color)

    @property
    def color_mode(self) -> ColorMode | str | None:
        """Return current color mode."""
        if not self._deprecated_color_handling:
            return self._attr_color_mode
        if self._fixed_color_mode:
            # Legacy light with support for a single color mode
            return self._fixed_color_mode
        # Legacy light with support for ct + hs, prioritize hs
        if self.hs_color is not None:
            return ColorMode.HS
        return ColorMode.COLOR_TEMP

    def _set_flash_and_transition(self, message: dict[str, Any], **kwargs: Any) -> None:
        if ATTR_TRANSITION in kwargs:
            message["transition"] = kwargs[ATTR_TRANSITION]

        if ATTR_FLASH in kwargs:
            flash: str = kwargs[ATTR_FLASH]

            if flash == FLASH_LONG:
                message["flash"] = self._flash_times[CONF_FLASH_TIME_LONG]
            elif flash == FLASH_SHORT:
                message["flash"] = self._flash_times[CONF_FLASH_TIME_SHORT]

    def _scale_rgbxx(self, rgbxx: tuple[int, ...], kwargs: Any) -> tuple[int, ...]:
        # If brightness is supported, we don't want to scale the
        # RGBxx values given using the brightness and
        # we pop the brightness, to omit it from the payload
        brightness: int
        if self._config[CONF_BRIGHTNESS]:
            brightness = 255
        else:
            brightness = kwargs.pop(ATTR_BRIGHTNESS, 255)
        return tuple(round(i / 255 * brightness) for i in rgbxx)

    def _supports_color_mode(self, color_mode: ColorMode | str) -> bool:
        """Return True if the light natively supports a color mode."""
        return (
            not self._deprecated_color_handling
            and self.supported_color_modes is not None
            and color_mode in self.supported_color_modes
        )

    async def async_turn_on(self, **kwargs: Any) -> None:  # noqa: C901
        """Turn the device on.

        This method is a coroutine.
        """
        brightness: int
        should_update = False
        hs_color: tuple[float, float]
        message: dict[str, Any] = {"state": "ON"}
        rgb: tuple[int, ...]
        rgbw: tuple[int, ...]
        rgbcw: tuple[int, ...]
        xy_color: tuple[float, float]

        if ATTR_HS_COLOR in kwargs and (
            self._config[CONF_HS] or self._config[CONF_RGB] or self._config[CONF_XY]
        ):
            # Legacy color handling
            hs_color = kwargs[ATTR_HS_COLOR]
            message["color"] = {}
            if self._config[CONF_RGB]:
                # If brightness is supported, we don't want to scale the
                # RGB values given using the brightness.
                if self._config[CONF_BRIGHTNESS]:
                    brightness = 255
                else:
                    # We pop the brightness, to omit it from the payload
                    brightness = kwargs.pop(ATTR_BRIGHTNESS, 255)
                rgb = color_util.color_hsv_to_RGB(
                    hs_color[0], hs_color[1], brightness / 255 * 100
                )
                message["color"]["r"] = rgb[0]
                message["color"]["g"] = rgb[1]
                message["color"]["b"] = rgb[2]
            if self._config[CONF_XY]:
                xy_color = color_util.color_hs_to_xy(*kwargs[ATTR_HS_COLOR])
                message["color"]["x"] = xy_color[0]
                message["color"]["y"] = xy_color[1]
            if self._config[CONF_HS]:
                message["color"]["h"] = hs_color[0]
                message["color"]["s"] = hs_color[1]

            if self._optimistic:
                self._attr_color_temp = None
                self._attr_hs_color = kwargs[ATTR_HS_COLOR]
                should_update = True

        if ATTR_HS_COLOR in kwargs and self._supports_color_mode(ColorMode.HS):
            hs_color = kwargs[ATTR_HS_COLOR]
            message["color"] = {"h": hs_color[0], "s": hs_color[1]}
            if self._optimistic:
                self._attr_color_mode = ColorMode.HS
                self._attr_hs_color = hs_color
                should_update = True

        if ATTR_RGB_COLOR in kwargs and self._supports_color_mode(ColorMode.RGB):
            rgb = self._scale_rgbxx(kwargs[ATTR_RGB_COLOR], kwargs)
            message["color"] = {"r": rgb[0], "g": rgb[1], "b": rgb[2]}
            if self._optimistic:
                self._attr_color_mode = ColorMode.RGB
                self._attr_rgb_color = cast(tuple[int, int, int], rgb)
                should_update = True

        if ATTR_RGBW_COLOR in kwargs and self._supports_color_mode(ColorMode.RGBW):
            rgbw = self._scale_rgbxx(kwargs[ATTR_RGBW_COLOR], kwargs)
            message["color"] = {"r": rgbw[0], "g": rgbw[1], "b": rgbw[2], "w": rgbw[3]}
            if self._optimistic:
                self._attr_color_mode = ColorMode.RGBW
                self._attr_rgbw_color = cast(tuple[int, int, int, int], rgbw)
                should_update = True

        if ATTR_RGBWW_COLOR in kwargs and self._supports_color_mode(ColorMode.RGBWW):
            rgbcw = self._scale_rgbxx(kwargs[ATTR_RGBWW_COLOR], kwargs)
            message["color"] = {
                "r": rgbcw[0],
                "g": rgbcw[1],
                "b": rgbcw[2],
                "c": rgbcw[3],
                "w": rgbcw[4],
            }
            if self._optimistic:
                self._attr_color_mode = ColorMode.RGBWW
                self._attr_rgbww_color = cast(tuple[int, int, int, int, int], rgbcw)
                should_update = True

        if ATTR_XY_COLOR in kwargs and self._supports_color_mode(ColorMode.XY):
            xy_color = kwargs[ATTR_XY_COLOR]
            message["color"] = {"x": xy_color[0], "y": xy_color[1]}
            if self._optimistic:
                self._attr_color_mode = ColorMode.XY
                self._attr_xy_color = xy_color
                should_update = True

        self._set_flash_and_transition(message, **kwargs)

        if ATTR_BRIGHTNESS in kwargs and brightness_supported(
            self.supported_color_modes
        ):
            device_brightness = color_util.brightness_to_value(
                (1, self._config[CONF_BRIGHTNESS_SCALE]),
                kwargs[ATTR_BRIGHTNESS],
            )
            # Make sure the brightness is not rounded down to 0
            device_brightness = max(round(device_brightness), 1)
            message["brightness"] = device_brightness

            if self._optimistic:
                self._attr_brightness = kwargs[ATTR_BRIGHTNESS]
                should_update = True

        if ATTR_COLOR_TEMP in kwargs:
            message["color_temp"] = int(kwargs[ATTR_COLOR_TEMP])

            if self._optimistic:
                self._attr_color_mode = ColorMode.COLOR_TEMP
                self._attr_color_temp = kwargs[ATTR_COLOR_TEMP]
                self._attr_hs_color = None
                should_update = True

        if ATTR_EFFECT in kwargs:
            message["effect"] = kwargs[ATTR_EFFECT]

            if self._optimistic:
                self._attr_effect = kwargs[ATTR_EFFECT]
                should_update = True

        if ATTR_WHITE in kwargs and self._supports_color_mode(ColorMode.WHITE):
            white_normalized = kwargs[ATTR_WHITE] / DEFAULT_WHITE_SCALE
            white_scale = self._config[CONF_WHITE_SCALE]
            device_white_level = min(round(white_normalized * white_scale), white_scale)
            # Make sure the brightness is not rounded down to 0
            device_white_level = max(device_white_level, 1)
            message["white"] = device_white_level

            if self._optimistic:
                self._attr_color_mode = ColorMode.WHITE
                self._attr_brightness = kwargs[ATTR_WHITE]
                should_update = True

        await self.async_publish_with_config(
            str(self._topic[CONF_COMMAND_TOPIC]), json_dumps(message)
        )

        if self._optimistic:
            # Optimistically assume that the light has changed state.
            self._attr_is_on = True
            should_update = True

        if should_update:
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off.

        This method is a coroutine.
        """
        message: dict[str, Any] = {"state": "OFF"}

        self._set_flash_and_transition(message, **kwargs)

        await self.async_publish_with_config(
            str(self._topic[CONF_COMMAND_TOPIC]), json_dumps(message)
        )

        if self._optimistic:
            # Optimistically assume that the light has changed state.
            self._attr_is_on = False
            self.async_write_ha_state()
