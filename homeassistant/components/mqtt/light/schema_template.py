"""Support for MQTT Template lights."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_FLASH,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    DEFAULT_MAX_KELVIN,
    DEFAULT_MIN_KELVIN,
    ENTITY_ID_FORMAT,
    ColorMode,
    LightEntity,
    LightEntityFeature,
    filter_supported_color_modes,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_STATE_TEMPLATE,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.service_info.mqtt import ReceivePayloadType
from homeassistant.helpers.typing import ConfigType, TemplateVarsType, VolSchemaType
from homeassistant.util import color as color_util

from .. import subscription
from ..config import MQTT_RW_SCHEMA
from ..const import (
    CONF_BLUE_TEMPLATE,
    CONF_BRIGHTNESS_TEMPLATE,
    CONF_COLOR_TEMP_KELVIN,
    CONF_COLOR_TEMP_TEMPLATE,
    CONF_COMMAND_OFF_TEMPLATE,
    CONF_COMMAND_ON_TEMPLATE,
    CONF_COMMAND_TOPIC,
    CONF_EFFECT_LIST,
    CONF_EFFECT_TEMPLATE,
    CONF_GREEN_TEMPLATE,
    CONF_MAX_KELVIN,
    CONF_MAX_MIREDS,
    CONF_MIN_KELVIN,
    CONF_MIN_MIREDS,
    CONF_RED_TEMPLATE,
    CONF_STATE_TOPIC,
    PAYLOAD_NONE,
)
from ..entity import MqttEntity
from ..models import (
    MqttCommandTemplate,
    MqttValueTemplate,
    PayloadSentinel,
    PublishPayloadType,
    ReceiveMessage,
)
from ..schemas import MQTT_ENTITY_COMMON_SCHEMA
from .schema import MQTT_LIGHT_SCHEMA_SCHEMA
from .schema_basic import MQTT_LIGHT_ATTRIBUTES_BLOCKED

_LOGGER = logging.getLogger(__name__)

DOMAIN = "mqtt_template"

DEFAULT_NAME = "MQTT Template Light"

COMMAND_TEMPLATES = (CONF_COMMAND_ON_TEMPLATE, CONF_COMMAND_OFF_TEMPLATE)
VALUE_TEMPLATES = (
    CONF_BLUE_TEMPLATE,
    CONF_BRIGHTNESS_TEMPLATE,
    CONF_COLOR_TEMP_TEMPLATE,
    CONF_EFFECT_TEMPLATE,
    CONF_GREEN_TEMPLATE,
    CONF_RED_TEMPLATE,
    CONF_STATE_TEMPLATE,
)

PLATFORM_SCHEMA_MODERN_TEMPLATE = (
    MQTT_RW_SCHEMA.extend(
        {
            vol.Optional(CONF_BLUE_TEMPLATE): cv.template,
            vol.Optional(CONF_BRIGHTNESS_TEMPLATE): cv.template,
            vol.Optional(CONF_COLOR_TEMP_KELVIN, default=False): cv.boolean,
            vol.Optional(CONF_COLOR_TEMP_TEMPLATE): cv.template,
            vol.Required(CONF_COMMAND_OFF_TEMPLATE): cv.template,
            vol.Required(CONF_COMMAND_ON_TEMPLATE): cv.template,
            vol.Optional(CONF_EFFECT_LIST): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(CONF_EFFECT_TEMPLATE): cv.template,
            vol.Optional(CONF_GREEN_TEMPLATE): cv.template,
            vol.Optional(CONF_MAX_KELVIN): cv.positive_int,
            vol.Optional(CONF_MIN_KELVIN): cv.positive_int,
            vol.Optional(CONF_MAX_MIREDS): cv.positive_int,
            vol.Optional(CONF_MIN_MIREDS): cv.positive_int,
            vol.Optional(CONF_NAME): vol.Any(cv.string, None),
            vol.Optional(CONF_RED_TEMPLATE): cv.template,
            vol.Optional(CONF_STATE_TEMPLATE): cv.template,
        }
    )
    .extend(MQTT_ENTITY_COMMON_SCHEMA.schema)
    .extend(MQTT_LIGHT_SCHEMA_SCHEMA.schema)
)

DISCOVERY_SCHEMA_TEMPLATE = vol.All(
    PLATFORM_SCHEMA_MODERN_TEMPLATE.extend({}, extra=vol.REMOVE_EXTRA),
)


class MqttLightTemplate(MqttEntity, LightEntity, RestoreEntity):
    """Representation of a MQTT Template light."""

    _default_name = DEFAULT_NAME
    _entity_id_format = ENTITY_ID_FORMAT
    _attributes_extra_blocked = MQTT_LIGHT_ATTRIBUTES_BLOCKED
    _optimistic: bool
    _command_templates: dict[
        str, Callable[[PublishPayloadType, TemplateVarsType], PublishPayloadType]
    ]
    _value_templates: dict[
        str, Callable[[ReceivePayloadType, ReceivePayloadType], ReceivePayloadType]
    ]
    _fixed_color_mode: ColorMode | str | None
    _topics: dict[str, str | None]

    @staticmethod
    def config_schema() -> VolSchemaType:
        """Return the config schema."""
        return DISCOVERY_SCHEMA_TEMPLATE

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

        self._topics = {
            key: config.get(key) for key in (CONF_STATE_TOPIC, CONF_COMMAND_TOPIC)
        }
        self._command_templates = {
            key: MqttCommandTemplate(config[key], entity=self).async_render
            for key in COMMAND_TEMPLATES
        }
        self._value_templates = {
            key: MqttValueTemplate(
                config.get(key), entity=self
            ).async_render_with_possible_json_value
            for key in VALUE_TEMPLATES
        }
        optimistic: bool = config[CONF_OPTIMISTIC]
        self._optimistic = (
            optimistic
            or self._topics[CONF_STATE_TOPIC] is None
            or CONF_STATE_TEMPLATE not in self._config
        )
        self._attr_assumed_state = bool(self._optimistic)

        color_modes = {ColorMode.ONOFF}
        if CONF_BRIGHTNESS_TEMPLATE in config:
            color_modes.add(ColorMode.BRIGHTNESS)
        if CONF_COLOR_TEMP_TEMPLATE in config:
            color_modes.add(ColorMode.COLOR_TEMP)
        if (
            CONF_RED_TEMPLATE in config
            and CONF_GREEN_TEMPLATE in config
            and CONF_BLUE_TEMPLATE in config
        ):
            color_modes.add(ColorMode.HS)
        self._attr_supported_color_modes = filter_supported_color_modes(color_modes)
        self._fixed_color_mode = None
        if self.supported_color_modes and len(self.supported_color_modes) == 1:
            self._fixed_color_mode = next(iter(self.supported_color_modes))
            self._attr_color_mode = self._fixed_color_mode

        features = LightEntityFeature.FLASH | LightEntityFeature.TRANSITION
        if config.get(CONF_EFFECT_LIST) is not None:
            features = features | LightEntityFeature.EFFECT
        self._attr_supported_features = features

    def _update_color_mode(self) -> None:
        """Update the color_mode attribute."""
        if self._fixed_color_mode:
            return
        # Support for ct + hs, prioritize hs
        self._attr_color_mode = ColorMode.HS if self.hs_color else ColorMode.COLOR_TEMP

    @callback
    def _state_received(self, msg: ReceiveMessage) -> None:
        """Handle new MQTT messages."""
        state_value = self._value_templates[CONF_STATE_TEMPLATE](
            msg.payload,
            PayloadSentinel.NONE,
        )
        if not state_value:
            _LOGGER.debug(
                "Ignoring message from '%s' with empty state value", msg.topic
            )
        elif state_value == STATE_ON:
            self._attr_is_on = True
        elif state_value == STATE_OFF:
            self._attr_is_on = False
        elif state_value == PAYLOAD_NONE:
            self._attr_is_on = None
        else:
            _LOGGER.warning(
                "Invalid state value '%s' received from %s",
                state_value,
                msg.topic,
            )

        if CONF_BRIGHTNESS_TEMPLATE in self._config:
            brightness_value = self._value_templates[CONF_BRIGHTNESS_TEMPLATE](
                msg.payload,
                PayloadSentinel.NONE,
            )
            if not brightness_value:
                _LOGGER.debug(
                    "Ignoring message from '%s' with empty brightness value",
                    msg.topic,
                )
            else:
                try:
                    if brightness := int(brightness_value):
                        self._attr_brightness = brightness
                    else:
                        _LOGGER.debug(
                            "Ignoring zero brightness value for entity %s",
                            self.entity_id,
                        )
                except ValueError:
                    _LOGGER.warning(
                        "Invalid brightness value '%s' received from %s",
                        brightness_value,
                        msg.topic,
                    )

        if CONF_COLOR_TEMP_TEMPLATE in self._config:
            color_temp_value = self._value_templates[CONF_COLOR_TEMP_TEMPLATE](
                msg.payload,
                PayloadSentinel.NONE,
            )
            if not color_temp_value:
                _LOGGER.debug(
                    "Ignoring message from '%s' with empty color temperature value",
                    msg.topic,
                )
            else:
                try:
                    self._attr_color_temp_kelvin = (
                        int(color_temp_value)
                        if self._color_temp_kelvin
                        else color_util.color_temperature_mired_to_kelvin(
                            int(color_temp_value)
                        )
                        if color_temp_value != "None"
                        else None
                    )
                except ValueError:
                    _LOGGER.warning(
                        "Invalid color temperature value '%s' received from %s",
                        color_temp_value,
                        msg.topic,
                    )

        if (
            CONF_RED_TEMPLATE in self._config
            and CONF_GREEN_TEMPLATE in self._config
            and CONF_BLUE_TEMPLATE in self._config
        ):
            red_value = self._value_templates[CONF_RED_TEMPLATE](
                msg.payload,
                PayloadSentinel.NONE,
            )
            green_value = self._value_templates[CONF_GREEN_TEMPLATE](
                msg.payload,
                PayloadSentinel.NONE,
            )
            blue_value = self._value_templates[CONF_BLUE_TEMPLATE](
                msg.payload,
                PayloadSentinel.NONE,
            )
            if not red_value or not green_value or not blue_value:
                _LOGGER.debug(
                    "Ignoring message from '%s' with empty color value", msg.topic
                )
            elif red_value == "None" and green_value == "None" and blue_value == "None":
                self._attr_hs_color = None
                self._update_color_mode()
            else:
                try:
                    self._attr_hs_color = color_util.color_RGB_to_hs(
                        int(red_value), int(green_value), int(blue_value)
                    )
                    self._update_color_mode()
                except ValueError:
                    _LOGGER.warning("Invalid color value received from %s", msg.topic)

        if CONF_EFFECT_TEMPLATE in self._config:
            effect_value = self._value_templates[CONF_EFFECT_TEMPLATE](
                msg.payload,
                PayloadSentinel.NONE,
            )
            if not effect_value:
                _LOGGER.debug(
                    "Ignoring message from '%s' with empty effect value", msg.topic
                )
            elif (effect_list := self._config[CONF_EFFECT_LIST]) and str(
                effect_value
            ) in effect_list:
                self._attr_effect = str(effect_value)
            else:
                _LOGGER.warning(
                    "Unsupported effect value '%s' received from %s",
                    effect_value,
                    msg.topic,
                )

    @callback
    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        self.add_subscription(
            CONF_STATE_TOPIC,
            self._state_received,
            {
                "_attr_brightness",
                "_attr_color_mode",
                "_attr_color_temp_kelvin",
                "_attr_effect",
                "_attr_hs_color",
                "_attr_is_on",
            },
        )

    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        subscription.async_subscribe_topics_internal(self.hass, self._sub_state)

        last_state = await self.async_get_last_state()
        if self._optimistic and last_state:
            self._attr_is_on = last_state.state == STATE_ON
            if last_state.attributes.get(ATTR_BRIGHTNESS):
                self._attr_brightness = last_state.attributes.get(ATTR_BRIGHTNESS)
            if last_state.attributes.get(ATTR_HS_COLOR):
                self._attr_hs_color = last_state.attributes.get(ATTR_HS_COLOR)
                self._update_color_mode()
            if last_state.attributes.get(ATTR_COLOR_TEMP_KELVIN):
                self._attr_color_temp_kelvin = last_state.attributes.get(
                    ATTR_COLOR_TEMP_KELVIN
                )
            if last_state.attributes.get(ATTR_EFFECT):
                self._attr_effect = last_state.attributes.get(ATTR_EFFECT)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on.

        This method is a coroutine.
        """
        values: dict[str, Any] = {"state": True}
        if self._optimistic:
            self._attr_is_on = True

        if ATTR_BRIGHTNESS in kwargs:
            values["brightness"] = int(kwargs[ATTR_BRIGHTNESS])

            if self._optimistic:
                self._attr_brightness = kwargs[ATTR_BRIGHTNESS]

        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            values["color_temp"] = (
                kwargs[ATTR_COLOR_TEMP_KELVIN]
                if self._color_temp_kelvin
                else color_util.color_temperature_kelvin_to_mired(
                    kwargs[ATTR_COLOR_TEMP_KELVIN]
                )
            )

            if self._optimistic:
                self._attr_color_temp_kelvin = kwargs[ATTR_COLOR_TEMP_KELVIN]
                self._attr_hs_color = None
                self._update_color_mode()

        if ATTR_HS_COLOR in kwargs:
            hs_color = kwargs[ATTR_HS_COLOR]

            # If there's a brightness topic set, we don't want to scale the RGB
            # values given using the brightness.
            if CONF_BRIGHTNESS_TEMPLATE in self._config:
                brightness = 255
            else:
                brightness = kwargs.get(
                    ATTR_BRIGHTNESS,
                    self._attr_brightness if self._attr_brightness is not None else 255,
                )
            rgb = color_util.color_hsv_to_RGB(
                hs_color[0], hs_color[1], brightness / 255 * 100
            )
            values["red"] = rgb[0]
            values["green"] = rgb[1]
            values["blue"] = rgb[2]
            values["hue"] = hs_color[0]
            values["sat"] = hs_color[1]

            if self._optimistic:
                self._attr_color_temp_kelvin = None
                self._attr_hs_color = kwargs[ATTR_HS_COLOR]
                self._update_color_mode()

        if ATTR_EFFECT in kwargs:
            values["effect"] = kwargs.get(ATTR_EFFECT)

            if self._optimistic:
                self._attr_effect = kwargs[ATTR_EFFECT]

        if ATTR_FLASH in kwargs:
            values["flash"] = kwargs.get(ATTR_FLASH)

        if ATTR_TRANSITION in kwargs:
            values["transition"] = kwargs[ATTR_TRANSITION]

        await self.async_publish_with_config(
            str(self._topics[CONF_COMMAND_TOPIC]),
            self._command_templates[CONF_COMMAND_ON_TEMPLATE](None, values),
        )

        if self._optimistic:
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off.

        This method is a coroutine.
        """
        values: dict[str, Any] = {"state": False}
        if self._optimistic:
            self._attr_is_on = False

        if ATTR_TRANSITION in kwargs:
            values["transition"] = kwargs[ATTR_TRANSITION]

        await self.async_publish_with_config(
            str(self._topics[CONF_COMMAND_TOPIC]),
            self._command_templates[CONF_COMMAND_OFF_TEMPLATE](None, values),
        )

        if self._optimistic:
            self.async_write_ha_state()
