"""Support for MQTT JSON lights."""
from __future__ import annotations

from contextlib import suppress
import logging
from typing import Any, cast

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
from homeassistant.config_entries import ConfigEntry
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
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.json import json_dumps
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.color as color_util
from homeassistant.util.json import json_loads_object

from .. import subscription
from ..config import DEFAULT_QOS, DEFAULT_RETAIN, MQTT_RW_SCHEMA
from ..const import (
    CONF_COMMAND_TOPIC,
    CONF_ENCODING,
    CONF_QOS,
    CONF_RETAIN,
    CONF_STATE_TOPIC,
)
from ..debug_info import log_messages
from ..mixins import MQTT_ENTITY_COMMON_SCHEMA, MqttEntity
from ..models import ReceiveMessage
from ..util import get_mqtt_data, valid_subscribe_topic
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

CONF_WHITE_VALUE = "white_value"


def valid_color_configuration(config: ConfigType) -> ConfigType:
    """Test color_mode is not combined with deprecated config."""
    deprecated = {CONF_COLOR_TEMP, CONF_HS, CONF_RGB, CONF_XY}
    if config[CONF_COLOR_MODE] and any(config.get(key) for key in deprecated):
        raise vol.Invalid(f"color_mode must not be combined with any of {deprecated}")
    return config


_PLATFORM_SCHEMA_BASE = (
    MQTT_RW_SCHEMA.extend(
        {
            vol.Optional(CONF_BRIGHTNESS, default=DEFAULT_BRIGHTNESS): cv.boolean,
            vol.Optional(
                CONF_BRIGHTNESS_SCALE, default=DEFAULT_BRIGHTNESS_SCALE
            ): vol.All(vol.Coerce(int), vol.Range(min=1)),
            vol.Inclusive(
                CONF_COLOR_MODE, "color_mode", default=DEFAULT_COLOR_MODE
            ): cv.boolean,
            vol.Optional(CONF_COLOR_TEMP, default=DEFAULT_COLOR_TEMP): cv.boolean,
            vol.Optional(CONF_EFFECT, default=DEFAULT_EFFECT): cv.boolean,
            vol.Optional(CONF_EFFECT_LIST): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(
                CONF_FLASH_TIME_LONG, default=DEFAULT_FLASH_TIME_LONG
            ): cv.positive_int,
            vol.Optional(
                CONF_FLASH_TIME_SHORT, default=DEFAULT_FLASH_TIME_SHORT
            ): cv.positive_int,
            vol.Optional(CONF_HS, default=DEFAULT_HS): cv.boolean,
            vol.Optional(CONF_MAX_MIREDS): cv.positive_int,
            vol.Optional(CONF_MIN_MIREDS): cv.positive_int,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_QOS, default=DEFAULT_QOS): vol.All(
                vol.Coerce(int), vol.In([0, 1, 2])
            ),
            vol.Optional(CONF_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
            vol.Optional(CONF_RGB, default=DEFAULT_RGB): cv.boolean,
            vol.Optional(CONF_STATE_TOPIC): valid_subscribe_topic,
            vol.Inclusive(CONF_SUPPORTED_COLOR_MODES, "color_mode"): vol.All(
                cv.ensure_list,
                [vol.In(VALID_COLOR_MODES)],
                vol.Unique(),
                valid_supported_color_modes,
            ),
            vol.Optional(CONF_WHITE_SCALE, default=DEFAULT_WHITE_SCALE): vol.All(
                vol.Coerce(int), vol.Range(min=1)
            ),
            vol.Optional(CONF_XY, default=DEFAULT_XY): cv.boolean,
        },
    )
    .extend(MQTT_ENTITY_COMMON_SCHEMA.schema)
    .extend(MQTT_LIGHT_SCHEMA_SCHEMA.schema)
)

DISCOVERY_SCHEMA_JSON = vol.All(
    # CONF_WHITE_VALUE is no longer supported, support was removed in 2022.9
    cv.removed(CONF_WHITE_VALUE),
    _PLATFORM_SCHEMA_BASE.extend({}, extra=vol.REMOVE_EXTRA),
    valid_color_configuration,
)

PLATFORM_SCHEMA_MODERN_JSON = vol.All(
    # CONF_WHITE_VALUE is no longer supported, support was removed in 2022.9
    cv.removed(CONF_WHITE_VALUE),
    _PLATFORM_SCHEMA_BASE,
    valid_color_configuration,
)


async def async_setup_entity_json(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    config_entry: ConfigEntry,
    discovery_data: DiscoveryInfoType | None,
) -> None:
    """Set up a MQTT JSON Light."""
    async_add_entities([MqttLightJson(hass, config, config_entry, discovery_data)])


class MqttLightJson(MqttEntity, LightEntity, RestoreEntity):
    """Representation of a MQTT JSON light."""

    _entity_id_format = ENTITY_ID_FORMAT
    _attributes_extra_blocked = MQTT_LIGHT_ATTRIBUTES_BLOCKED

    _flash_times: dict[str, int | None]
    _topic: dict[str, str | None]
    _optimistic: bool

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        config_entry: ConfigEntry,
        discovery_data: DiscoveryInfoType | None,
    ) -> None:
        """Initialize MQTT JSON light."""
        self._fixed_color_mode: ColorMode | str | None = None
        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema() -> vol.Schema:
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
        if not self._config[CONF_COLOR_MODE]:
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
        else:
            self._attr_supported_color_modes = self._config[CONF_SUPPORTED_COLOR_MODES]
            if self.supported_color_modes and len(self.supported_color_modes) == 1:
                self._attr_color_mode = next(iter(self.supported_color_modes))

    def _update_color(self, values: dict[str, Any]) -> None:
        if not self._config[CONF_COLOR_MODE]:
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
                    "Invalid RGB color value received for entity %s", self.entity_id
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
                    "Invalid XY color value received for entity %s", self.entity_id
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
                    "Invalid HS color value received for entity %s", self.entity_id
                )
                return
        else:
            color_mode: str = values["color_mode"]
            if not self._supports_color_mode(color_mode):
                _LOGGER.warning(
                    "Invalid color mode received for entity %s", self.entity_id
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
                    r = int(values["color"]["r"])  # pylint: disable=invalid-name
                    g = int(values["color"]["g"])  # pylint: disable=invalid-name
                    b = int(values["color"]["b"])  # pylint: disable=invalid-name
                    self._attr_color_mode = ColorMode.RGB
                    self._attr_rgb_color = (r, g, b)
                elif color_mode == ColorMode.RGBW:
                    r = int(values["color"]["r"])  # pylint: disable=invalid-name
                    g = int(values["color"]["g"])  # pylint: disable=invalid-name
                    b = int(values["color"]["b"])  # pylint: disable=invalid-name
                    w = int(values["color"]["w"])  # pylint: disable=invalid-name
                    self._attr_color_mode = ColorMode.RGBW
                    self._attr_rgbw_color = (r, g, b, w)
                elif color_mode == ColorMode.RGBWW:
                    r = int(values["color"]["r"])  # pylint: disable=invalid-name
                    g = int(values["color"]["g"])  # pylint: disable=invalid-name
                    b = int(values["color"]["b"])  # pylint: disable=invalid-name
                    c = int(values["color"]["c"])  # pylint: disable=invalid-name
                    w = int(values["color"]["w"])  # pylint: disable=invalid-name
                    self._attr_color_mode = ColorMode.RGBWW
                    self._attr_rgbww_color = (r, g, b, c, w)
                elif color_mode == ColorMode.WHITE:
                    self._attr_color_mode = ColorMode.WHITE
                elif color_mode == ColorMode.XY:
                    x = float(values["color"]["x"])  # pylint: disable=invalid-name
                    y = float(values["color"]["y"])  # pylint: disable=invalid-name
                    self._attr_color_mode = ColorMode.XY
                    self._attr_xy_color = (x, y)
            except (KeyError, ValueError):
                _LOGGER.warning(
                    "Invalid or incomplete color value received for entity %s",
                    self.entity_id,
                )

    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""

        @callback
        @log_messages(self.hass, self.entity_id)
        def state_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT messages."""
            values = json_loads_object(msg.payload)

            if values["state"] == "ON":
                self._attr_is_on = True
            elif values["state"] == "OFF":
                self._attr_is_on = False
            elif values["state"] is None:
                self._attr_is_on = None

            if (
                not self._config[CONF_COLOR_MODE]
                and color_supported(self.supported_color_modes)
                and "color" in values
            ):
                # Deprecated color handling
                if values["color"] is None:
                    self._attr_hs_color = None
                else:
                    self._update_color(values)

            if self._config[CONF_COLOR_MODE] and "color_mode" in values:
                self._update_color(values)

            if brightness_supported(self.supported_color_modes):
                try:
                    self._attr_brightness = int(
                        values["brightness"]  # type: ignore[operator]
                        / float(self._config[CONF_BRIGHTNESS_SCALE])
                        * 255
                    )
                except KeyError:
                    pass
                except (TypeError, ValueError):
                    _LOGGER.warning(
                        "Invalid brightness value received for entity %s",
                        self.entity_id,
                    )

            if (
                self.supported_color_modes
                and ColorMode.COLOR_TEMP in self.supported_color_modes
                and not self._config[CONF_COLOR_MODE]
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
                        "Invalid color temp value received for entity %s",
                        self.entity_id,
                    )

            if self.supported_features and LightEntityFeature.EFFECT:
                with suppress(KeyError):
                    self._attr_effect = cast(str, values["effect"])

            get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

        if self._topic[CONF_STATE_TOPIC] is not None:
            self._sub_state = subscription.async_prepare_subscribe_topics(
                self.hass,
                self._sub_state,
                {
                    "state_topic": {
                        "topic": self._topic[CONF_STATE_TOPIC],
                        "msg_callback": state_received,
                        "qos": self._config[CONF_QOS],
                        "encoding": self._config[CONF_ENCODING] or None,
                    }
                },
            )

    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        await subscription.async_subscribe_topics(self.hass, self._sub_state)

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
    def assumed_state(self) -> bool:
        """Return true if we do optimistic updates."""
        return self._optimistic

    @property
    def color_mode(self) -> ColorMode | str | None:
        """Return current color mode."""
        if self._config[CONF_COLOR_MODE]:
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
        # If there's a brightness topic set, we don't want to scale the
        # RGBxx values given using the brightness.
        brightness: int
        if self._config[CONF_BRIGHTNESS]:
            brightness = 255
        else:
            brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
        return tuple(round(i / 255 * brightness) for i in rgbxx)

    def _supports_color_mode(self, color_mode: ColorMode | str) -> bool:
        """Return True if the light natively supports a color mode."""
        return (
            self._config[CONF_COLOR_MODE]
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
                # If there's a brightness topic set, we don't want to scale the
                # RGB values given using the brightness.
                if self._config[CONF_BRIGHTNESS]:
                    brightness = 255
                else:
                    brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
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

        if ATTR_BRIGHTNESS in kwargs and self._config[CONF_BRIGHTNESS]:
            brightness_normalized = kwargs[ATTR_BRIGHTNESS] / DEFAULT_BRIGHTNESS_SCALE
            brightness_scale = self._config[CONF_BRIGHTNESS_SCALE]
            device_brightness = min(
                round(brightness_normalized * brightness_scale), brightness_scale
            )
            # Make sure the brightness is not rounded down to 0
            device_brightness = max(device_brightness, 1)
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

        await self.async_publish(
            str(self._topic[CONF_COMMAND_TOPIC]),
            json_dumps(message),
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
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

        await self.async_publish(
            str(self._topic[CONF_COMMAND_TOPIC]),
            json_dumps(message),
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )

        if self._optimistic:
            # Optimistically assume that the light has changed state.
            self._attr_is_on = False
            self.async_write_ha_state()
