"""Support for MQTT Template lights."""
from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_FLASH,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    ENTITY_ID_FORMAT,
    ColorMode,
    LightEntity,
    LightEntityFeature,
    filter_supported_color_modes,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_STATE_TEMPLATE,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, TemplateVarsType
import homeassistant.util.color as color_util

from .. import subscription
from ..config import MQTT_RW_SCHEMA
from ..const import (
    CONF_COMMAND_TOPIC,
    CONF_ENCODING,
    CONF_QOS,
    CONF_RETAIN,
    CONF_STATE_TOPIC,
    PAYLOAD_NONE,
)
from ..debug_info import log_messages
from ..mixins import MQTT_ENTITY_COMMON_SCHEMA, MqttEntity
from ..models import (
    MqttCommandTemplate,
    MqttValueTemplate,
    PublishPayloadType,
    ReceiveMessage,
    ReceivePayloadType,
)
from ..util import get_mqtt_data
from .schema import MQTT_LIGHT_SCHEMA_SCHEMA
from .schema_basic import MQTT_LIGHT_ATTRIBUTES_BLOCKED

_LOGGER = logging.getLogger(__name__)

DOMAIN = "mqtt_template"

DEFAULT_NAME = "MQTT Template Light"

CONF_BLUE_TEMPLATE = "blue_template"
CONF_BRIGHTNESS_TEMPLATE = "brightness_template"
CONF_COLOR_TEMP_TEMPLATE = "color_temp_template"
CONF_COMMAND_OFF_TEMPLATE = "command_off_template"
CONF_COMMAND_ON_TEMPLATE = "command_on_template"
CONF_EFFECT_LIST = "effect_list"
CONF_EFFECT_TEMPLATE = "effect_template"
CONF_GREEN_TEMPLATE = "green_template"
CONF_MAX_MIREDS = "max_mireds"
CONF_MIN_MIREDS = "min_mireds"
CONF_RED_TEMPLATE = "red_template"
CONF_WHITE_VALUE_TEMPLATE = "white_value_template"

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

_PLATFORM_SCHEMA_BASE = (
    MQTT_RW_SCHEMA.extend(
        {
            vol.Optional(CONF_BLUE_TEMPLATE): cv.template,
            vol.Optional(CONF_BRIGHTNESS_TEMPLATE): cv.template,
            vol.Optional(CONF_COLOR_TEMP_TEMPLATE): cv.template,
            vol.Required(CONF_COMMAND_OFF_TEMPLATE): cv.template,
            vol.Required(CONF_COMMAND_ON_TEMPLATE): cv.template,
            vol.Optional(CONF_EFFECT_LIST): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(CONF_EFFECT_TEMPLATE): cv.template,
            vol.Optional(CONF_GREEN_TEMPLATE): cv.template,
            vol.Optional(CONF_MAX_MIREDS): cv.positive_int,
            vol.Optional(CONF_MIN_MIREDS): cv.positive_int,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_RED_TEMPLATE): cv.template,
            vol.Optional(CONF_STATE_TEMPLATE): cv.template,
        }
    )
    .extend(MQTT_ENTITY_COMMON_SCHEMA.schema)
    .extend(MQTT_LIGHT_SCHEMA_SCHEMA.schema)
)

DISCOVERY_SCHEMA_TEMPLATE = vol.All(
    # CONF_WHITE_VALUE_TEMPLATE is no longer supported, support was removed in 2022.9
    cv.removed(CONF_WHITE_VALUE_TEMPLATE),
    _PLATFORM_SCHEMA_BASE.extend({}, extra=vol.REMOVE_EXTRA),
)

PLATFORM_SCHEMA_MODERN_TEMPLATE = vol.All(
    # CONF_WHITE_VALUE_TEMPLATE is no longer supported, support was removed in 2022.9
    cv.removed(CONF_WHITE_VALUE_TEMPLATE),
    _PLATFORM_SCHEMA_BASE,
)


async def async_setup_entity_template(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    config_entry: ConfigEntry,
    discovery_data: DiscoveryInfoType | None,
) -> None:
    """Set up a MQTT Template light."""
    async_add_entities([MqttLightTemplate(hass, config, config_entry, discovery_data)])


class MqttLightTemplate(MqttEntity, LightEntity, RestoreEntity):
    """Representation of a MQTT Template light."""

    _entity_id_format = ENTITY_ID_FORMAT
    _attributes_extra_blocked = MQTT_LIGHT_ATTRIBUTES_BLOCKED
    _optimistic: bool
    _command_templates: dict[
        str, Callable[[PublishPayloadType, TemplateVarsType], PublishPayloadType]
    ]
    _value_templates: dict[str, Callable[[ReceivePayloadType], ReceivePayloadType]]
    _fixed_color_mode: ColorMode | str | None
    _topics: dict[str, str | None]

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        config_entry: ConfigEntry,
        discovery_data: DiscoveryInfoType | None,
    ) -> None:
        """Initialize a MQTT Template light."""
        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema() -> vol.Schema:
        """Return the config schema."""
        return DISCOVERY_SCHEMA_TEMPLATE

    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""
        self._attr_max_mireds = config.get(CONF_MAX_MIREDS, super().max_mireds)
        self._attr_min_mireds = config.get(CONF_MIN_MIREDS, super().min_mireds)
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

    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""

        @callback
        @log_messages(self.hass, self.entity_id)
        def state_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT messages."""
            state = self._value_templates[CONF_STATE_TEMPLATE](msg.payload)
            if state == STATE_ON:
                self._attr_is_on = True
            elif state == STATE_OFF:
                self._attr_is_on = False
            elif state == PAYLOAD_NONE:
                self._attr_is_on = None
            else:
                _LOGGER.warning("Invalid state value received")

            if CONF_BRIGHTNESS_TEMPLATE in self._config:
                try:
                    if brightness := int(
                        self._value_templates[CONF_BRIGHTNESS_TEMPLATE](msg.payload)
                    ):
                        self._attr_brightness = brightness
                    else:
                        _LOGGER.debug(
                            "Ignoring zero brightness value for entity %s",
                            self.entity_id,
                        )

                except ValueError:
                    _LOGGER.warning(
                        "Invalid brightness value received from %s", msg.topic
                    )

            if CONF_COLOR_TEMP_TEMPLATE in self._config:
                try:
                    color_temp = self._value_templates[CONF_COLOR_TEMP_TEMPLATE](
                        msg.payload
                    )
                    self._attr_color_temp = (
                        int(color_temp) if color_temp != "None" else None
                    )
                except ValueError:
                    _LOGGER.warning("Invalid color temperature value received")

            if (
                CONF_RED_TEMPLATE in self._config
                and CONF_GREEN_TEMPLATE in self._config
                and CONF_BLUE_TEMPLATE in self._config
            ):
                try:
                    red = self._value_templates[CONF_RED_TEMPLATE](msg.payload)
                    green = self._value_templates[CONF_GREEN_TEMPLATE](msg.payload)
                    blue = self._value_templates[CONF_BLUE_TEMPLATE](msg.payload)
                    if red == "None" and green == "None" and blue == "None":
                        self._attr_hs_color = None
                    else:
                        self._attr_hs_color = color_util.color_RGB_to_hs(
                            int(red), int(green), int(blue)
                        )
                    self._update_color_mode()
                except ValueError:
                    _LOGGER.warning("Invalid color value received")

            if CONF_EFFECT_TEMPLATE in self._config:
                effect = str(self._value_templates[CONF_EFFECT_TEMPLATE](msg.payload))
                if (
                    effect_list := self._config[CONF_EFFECT_LIST]
                ) and effect in effect_list:
                    self._attr_effect = effect
                else:
                    _LOGGER.warning("Unsupported effect value received")

            get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

        if self._topics[CONF_STATE_TOPIC] is not None:
            self._sub_state = subscription.async_prepare_subscribe_topics(
                self.hass,
                self._sub_state,
                {
                    "state_topic": {
                        "topic": self._topics[CONF_STATE_TOPIC],
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
            if last_state.attributes.get(ATTR_BRIGHTNESS):
                self._attr_brightness = last_state.attributes.get(ATTR_BRIGHTNESS)
            if last_state.attributes.get(ATTR_HS_COLOR):
                self._attr_hs_color = last_state.attributes.get(ATTR_HS_COLOR)
                self._update_color_mode()
            if last_state.attributes.get(ATTR_COLOR_TEMP):
                self._attr_color_temp = last_state.attributes.get(ATTR_COLOR_TEMP)
            if last_state.attributes.get(ATTR_EFFECT):
                self._attr_effect = last_state.attributes.get(ATTR_EFFECT)

    @property
    def assumed_state(self) -> bool:
        """Return True if unable to access real state of the entity."""
        return self._optimistic

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

        if ATTR_COLOR_TEMP in kwargs:
            values["color_temp"] = int(kwargs[ATTR_COLOR_TEMP])

            if self._optimistic:
                self._attr_color_temp = kwargs[ATTR_COLOR_TEMP]
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
                self._attr_color_temp = None
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

        await self.async_publish(
            str(self._topics[CONF_COMMAND_TOPIC]),
            self._command_templates[CONF_COMMAND_ON_TEMPLATE](None, values),
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
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

        await self.async_publish(
            str(self._topics[CONF_COMMAND_TOPIC]),
            self._command_templates[CONF_COMMAND_OFF_TEMPLATE](None, values),
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )

        if self._optimistic:
            self.async_write_ha_state()
