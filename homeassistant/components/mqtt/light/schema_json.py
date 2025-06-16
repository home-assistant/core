"""Support for MQTT JSON lights."""

from __future__ import annotations

from contextlib import suppress
import logging
from typing import TYPE_CHECKING, Any, cast

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_FLASH,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_TRANSITION,
    ATTR_WHITE,
    ATTR_XY_COLOR,
    DEFAULT_MAX_KELVIN,
    DEFAULT_MIN_KELVIN,
    ENTITY_ID_FORMAT,
    FLASH_LONG,
    FLASH_SHORT,
    VALID_COLOR_MODES,
    ColorMode,
    LightEntity,
    LightEntityFeature,
    brightness_supported,
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
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.json import json_dumps
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, VolSchemaType
from homeassistant.util import color as color_util
from homeassistant.util.json import json_loads_object

from .. import subscription
from ..config import DEFAULT_QOS, DEFAULT_RETAIN, MQTT_RW_SCHEMA
from ..const import (
    CONF_COLOR_MODE,
    CONF_COLOR_TEMP_KELVIN,
    CONF_COMMAND_TOPIC,
    CONF_EFFECT_LIST,
    CONF_FLASH,
    CONF_FLASH_TIME_LONG,
    CONF_FLASH_TIME_SHORT,
    CONF_MAX_KELVIN,
    CONF_MAX_MIREDS,
    CONF_MIN_KELVIN,
    CONF_MIN_MIREDS,
    CONF_QOS,
    CONF_RETAIN,
    CONF_STATE_TOPIC,
    CONF_SUPPORTED_COLOR_MODES,
    CONF_TRANSITION,
    DEFAULT_BRIGHTNESS,
    DEFAULT_BRIGHTNESS_SCALE,
    DEFAULT_EFFECT,
    DEFAULT_FLASH_TIME_LONG,
    DEFAULT_FLASH_TIME_SHORT,
    DEFAULT_WHITE_SCALE,
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

DEFAULT_NAME = "MQTT JSON Light"

DEFAULT_FLASH = True
DEFAULT_TRANSITION = True

_PLATFORM_SCHEMA_BASE = (
    MQTT_RW_SCHEMA.extend(
        {
            vol.Optional(CONF_BRIGHTNESS, default=DEFAULT_BRIGHTNESS): cv.boolean,
            vol.Optional(
                CONF_BRIGHTNESS_SCALE, default=DEFAULT_BRIGHTNESS_SCALE
            ): vol.All(vol.Coerce(int), vol.Range(min=1)),
            vol.Optional(CONF_COLOR_TEMP_KELVIN, default=False): cv.boolean,
            vol.Optional(CONF_EFFECT, default=DEFAULT_EFFECT): cv.boolean,
            vol.Optional(CONF_EFFECT_LIST): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(CONF_FLASH, default=DEFAULT_FLASH): cv.boolean,
            vol.Optional(
                CONF_FLASH_TIME_LONG, default=DEFAULT_FLASH_TIME_LONG
            ): cv.positive_int,
            vol.Optional(
                CONF_FLASH_TIME_SHORT, default=DEFAULT_FLASH_TIME_SHORT
            ): cv.positive_int,
            vol.Optional(CONF_MAX_MIREDS): cv.positive_int,
            vol.Optional(CONF_MIN_MIREDS): cv.positive_int,
            vol.Optional(CONF_MAX_KELVIN): cv.positive_int,
            vol.Optional(CONF_MIN_KELVIN): cv.positive_int,
            vol.Optional(CONF_NAME): vol.Any(cv.string, None),
            vol.Optional(CONF_QOS, default=DEFAULT_QOS): vol.All(
                vol.Coerce(int), vol.In([0, 1, 2])
            ),
            vol.Optional(CONF_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
            vol.Optional(CONF_STATE_TOPIC): valid_subscribe_topic,
            vol.Optional(CONF_SUPPORTED_COLOR_MODES): vol.All(
                cv.ensure_list,
                [vol.In(VALID_COLOR_MODES)],
                vol.Unique(),
                valid_supported_color_modes,
            ),
            vol.Optional(CONF_TRANSITION, default=DEFAULT_TRANSITION): cv.boolean,
            vol.Optional(CONF_WHITE_SCALE, default=DEFAULT_WHITE_SCALE): vol.All(
                vol.Coerce(int), vol.Range(min=1)
            ),
        },
    )
    .extend(MQTT_ENTITY_COMMON_SCHEMA.schema)
    .extend(MQTT_LIGHT_SCHEMA_SCHEMA.schema)
)

# Support for legacy color_mode handling was removed with HA Core 2025.3
# The removed attributes can be removed from the schema's from HA Core 2026.3
DISCOVERY_SCHEMA_JSON = vol.All(
    cv.removed(CONF_COLOR_MODE, raise_if_present=False),
    cv.removed(CONF_COLOR_TEMP, raise_if_present=False),
    cv.removed(CONF_HS, raise_if_present=False),
    cv.removed(CONF_RGB, raise_if_present=False),
    cv.removed(CONF_XY, raise_if_present=False),
    _PLATFORM_SCHEMA_BASE.extend({}, extra=vol.REMOVE_EXTRA),
)

PLATFORM_SCHEMA_MODERN_JSON = vol.All(
    cv.removed(CONF_COLOR_MODE),
    cv.removed(CONF_COLOR_TEMP),
    cv.removed(CONF_HS),
    cv.removed(CONF_RGB),
    cv.removed(CONF_XY),
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

    @staticmethod
    def config_schema() -> VolSchemaType:
        """Return the config schema."""
        return DISCOVERY_SCHEMA_JSON

    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""
        self._color_temp_kelvin = config[CONF_COLOR_TEMP_KELVIN]
        self._attr_min_color_temp_kelvin = (
            color_util.color_temperature_mired_to_kelvin(max_mireds)
            if (max_mireds := config.get(CONF_MAX_MIREDS))
            else config.get(CONF_MIN_KELVIN, DEFAULT_MIN_KELVIN)
        )
        self._attr_max_color_temp_kelvin = (
            color_util.color_temperature_mired_to_kelvin(min_mireds)
            if (min_mireds := config.get(CONF_MIN_MIREDS))
            else config.get(CONF_MAX_KELVIN, DEFAULT_MAX_KELVIN)
        )
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

        self._attr_supported_features |= (
            config[CONF_EFFECT] and LightEntityFeature.EFFECT
        )
        self._attr_supported_features |= config[CONF_FLASH] and LightEntityFeature.FLASH
        self._attr_supported_features |= (
            config[CONF_TRANSITION] and LightEntityFeature.TRANSITION
        )
        if supported_color_modes := self._config.get(CONF_SUPPORTED_COLOR_MODES):
            self._attr_supported_color_modes = supported_color_modes
            if self.supported_color_modes and len(self.supported_color_modes) == 1:
                self._attr_color_mode = next(iter(self.supported_color_modes))
            else:
                self._attr_color_mode = ColorMode.UNKNOWN
        elif config.get(CONF_BRIGHTNESS):
            # Brightness is supported and no supported_color_modes are set,
            # so set brightness as the supported color mode.
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def _update_color(self, values: dict[str, Any]) -> None:
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
                self._attr_color_temp_kelvin = (
                    values["color_temp"]
                    if self._color_temp_kelvin
                    else color_util.color_temperature_mired_to_kelvin(
                        values["color_temp"]
                    )
                )
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
        except (KeyError, TypeError, ValueError):
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

        if "color_mode" in values:
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
                "_attr_color_temp_kelvin",
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
            self._attr_color_temp_kelvin = last_attributes.get(
                ATTR_COLOR_TEMP_KELVIN, self.color_temp_kelvin
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
            self.supported_color_modes is not None
            and color_mode in self.supported_color_modes
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on.

        This method is a coroutine.
        """
        should_update = False
        hs_color: tuple[float, float]
        message: dict[str, Any] = {"state": "ON"}
        rgb: tuple[int, ...]
        rgbw: tuple[int, ...]
        rgbcw: tuple[int, ...]
        xy_color: tuple[float, float]

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

        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            message["color_temp"] = (
                kwargs[ATTR_COLOR_TEMP_KELVIN]
                if self._color_temp_kelvin
                else color_util.color_temperature_kelvin_to_mired(
                    kwargs[ATTR_COLOR_TEMP_KELVIN]
                )
            )
            if self._optimistic:
                self._attr_color_mode = ColorMode.COLOR_TEMP
                self._attr_color_temp_kelvin = kwargs[ATTR_COLOR_TEMP_KELVIN]
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
