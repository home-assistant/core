"""Support for MQTT JSON lights."""
import json
import logging

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_FLASH,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    ATTR_WHITE_VALUE,
    FLASH_LONG,
    FLASH_SHORT,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    SUPPORT_EFFECT,
    SUPPORT_FLASH,
    SUPPORT_TRANSITION,
    SUPPORT_WHITE_VALUE,
    LightEntity,
)
from homeassistant.components.mqtt import (
    CONF_COMMAND_TOPIC,
    CONF_QOS,
    CONF_RETAIN,
    CONF_STATE_TOPIC,
    CONF_UNIQUE_ID,
    MqttAttributes,
    MqttAvailability,
    MqttDiscoveryUpdate,
    MqttEntityDeviceInfo,
    subscription,
)
from homeassistant.const import (
    CONF_BRIGHTNESS,
    CONF_COLOR_TEMP,
    CONF_DEVICE,
    CONF_EFFECT,
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_RGB,
    CONF_WHITE_VALUE,
    CONF_XY,
    STATE_ON,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType
import homeassistant.util.color as color_util

from ..debug_info import log_messages
from .schema import MQTT_LIGHT_SCHEMA_SCHEMA
from .schema_basic import CONF_BRIGHTNESS_SCALE

_LOGGER = logging.getLogger(__name__)

DOMAIN = "mqtt_json"

DEFAULT_BRIGHTNESS = False
DEFAULT_COLOR_TEMP = False
DEFAULT_EFFECT = False
DEFAULT_FLASH_TIME_LONG = 10
DEFAULT_FLASH_TIME_SHORT = 2
DEFAULT_NAME = "MQTT JSON Light"
DEFAULT_OPTIMISTIC = False
DEFAULT_RGB = False
DEFAULT_WHITE_VALUE = False
DEFAULT_XY = False
DEFAULT_HS = False
DEFAULT_BRIGHTNESS_SCALE = 255

CONF_EFFECT_LIST = "effect_list"

CONF_FLASH_TIME_LONG = "flash_time_long"
CONF_FLASH_TIME_SHORT = "flash_time_short"
CONF_HS = "hs"

# Stealing some of these from the base MQTT configs.
PLATFORM_SCHEMA_JSON = (
    mqtt.MQTT_RW_PLATFORM_SCHEMA.extend(
        {
            vol.Optional(CONF_BRIGHTNESS, default=DEFAULT_BRIGHTNESS): cv.boolean,
            vol.Optional(
                CONF_BRIGHTNESS_SCALE, default=DEFAULT_BRIGHTNESS_SCALE
            ): vol.All(vol.Coerce(int), vol.Range(min=1)),
            vol.Optional(CONF_COLOR_TEMP, default=DEFAULT_COLOR_TEMP): cv.boolean,
            vol.Optional(CONF_DEVICE): mqtt.MQTT_ENTITY_DEVICE_INFO_SCHEMA,
            vol.Optional(CONF_EFFECT, default=DEFAULT_EFFECT): cv.boolean,
            vol.Optional(CONF_EFFECT_LIST): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(
                CONF_FLASH_TIME_LONG, default=DEFAULT_FLASH_TIME_LONG
            ): cv.positive_int,
            vol.Optional(
                CONF_FLASH_TIME_SHORT, default=DEFAULT_FLASH_TIME_SHORT
            ): cv.positive_int,
            vol.Optional(CONF_HS, default=DEFAULT_HS): cv.boolean,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
            vol.Optional(CONF_QOS, default=mqtt.DEFAULT_QOS): vol.All(
                vol.Coerce(int), vol.In([0, 1, 2])
            ),
            vol.Optional(CONF_RETAIN, default=mqtt.DEFAULT_RETAIN): cv.boolean,
            vol.Optional(CONF_RGB, default=DEFAULT_RGB): cv.boolean,
            vol.Optional(CONF_STATE_TOPIC): mqtt.valid_subscribe_topic,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
            vol.Optional(CONF_WHITE_VALUE, default=DEFAULT_WHITE_VALUE): cv.boolean,
            vol.Optional(CONF_XY, default=DEFAULT_XY): cv.boolean,
        }
    )
    .extend(mqtt.MQTT_AVAILABILITY_SCHEMA.schema)
    .extend(mqtt.MQTT_JSON_ATTRS_SCHEMA.schema)
    .extend(MQTT_LIGHT_SCHEMA_SCHEMA.schema)
)


async def async_setup_entity_json(
    config: ConfigType, async_add_entities, config_entry, discovery_data
):
    """Set up a MQTT JSON Light."""
    async_add_entities([MqttLightJson(config, config_entry, discovery_data)])


class MqttLightJson(
    MqttAttributes,
    MqttAvailability,
    MqttDiscoveryUpdate,
    MqttEntityDeviceInfo,
    LightEntity,
    RestoreEntity,
):
    """Representation of a MQTT JSON light."""

    def __init__(self, config, config_entry, discovery_data):
        """Initialize MQTT JSON light."""
        self._state = False
        self._sub_state = None
        self._supported_features = 0

        self._topic = None
        self._optimistic = False
        self._brightness = None
        self._color_temp = None
        self._effect = None
        self._hs = None
        self._white_value = None
        self._flash_times = None
        self._unique_id = config.get(CONF_UNIQUE_ID)

        # Load config
        self._setup_from_config(config)

        device_config = config.get(CONF_DEVICE)

        MqttAttributes.__init__(self, config)
        MqttAvailability.__init__(self, config)
        MqttDiscoveryUpdate.__init__(self, discovery_data, self.discovery_update)
        MqttEntityDeviceInfo.__init__(self, device_config, config_entry)

    async def async_added_to_hass(self):
        """Subscribe to MQTT events."""
        await super().async_added_to_hass()
        await self._subscribe_topics()

    async def discovery_update(self, discovery_payload):
        """Handle updated discovery message."""
        config = PLATFORM_SCHEMA_JSON(discovery_payload)
        self._setup_from_config(config)
        await self.attributes_discovery_update(config)
        await self.availability_discovery_update(config)
        await self.device_info_discovery_update(config)
        await self._subscribe_topics()
        self.async_write_ha_state()

    def _setup_from_config(self, config):
        """(Re)Setup the entity."""
        self._config = config

        self._topic = {
            key: config.get(key) for key in (CONF_STATE_TOPIC, CONF_COMMAND_TOPIC)
        }
        optimistic = config[CONF_OPTIMISTIC]
        self._optimistic = optimistic or self._topic[CONF_STATE_TOPIC] is None

        brightness = config[CONF_BRIGHTNESS]
        if brightness:
            self._brightness = 255
        else:
            self._brightness = None

        color_temp = config[CONF_COLOR_TEMP]
        if color_temp:
            self._color_temp = 150
        else:
            self._color_temp = None

        effect = config[CONF_EFFECT]
        if effect:
            self._effect = "none"
        else:
            self._effect = None

        white_value = config[CONF_WHITE_VALUE]
        if white_value:
            self._white_value = 255
        else:
            self._white_value = None

        if config[CONF_HS] or config[CONF_RGB] or config[CONF_XY]:
            self._hs = [0, 0]
        else:
            self._hs = None

        self._flash_times = {
            key: config.get(key)
            for key in (CONF_FLASH_TIME_SHORT, CONF_FLASH_TIME_LONG)
        }

        self._supported_features = SUPPORT_TRANSITION | SUPPORT_FLASH
        self._supported_features |= config[CONF_RGB] and SUPPORT_COLOR
        self._supported_features |= brightness and SUPPORT_BRIGHTNESS
        self._supported_features |= color_temp and SUPPORT_COLOR_TEMP
        self._supported_features |= effect and SUPPORT_EFFECT
        self._supported_features |= white_value and SUPPORT_WHITE_VALUE
        self._supported_features |= config[CONF_XY] and SUPPORT_COLOR
        self._supported_features |= config[CONF_HS] and SUPPORT_COLOR

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""
        last_state = await self.async_get_last_state()

        @callback
        @log_messages(self.hass, self.entity_id)
        def state_received(msg):
            """Handle new MQTT messages."""
            values = json.loads(msg.payload)

            if values["state"] == "ON":
                self._state = True
            elif values["state"] == "OFF":
                self._state = False

            if self._hs is not None:
                try:
                    red = int(values["color"]["r"])
                    green = int(values["color"]["g"])
                    blue = int(values["color"]["b"])

                    self._hs = color_util.color_RGB_to_hs(red, green, blue)
                except KeyError:
                    pass
                except ValueError:
                    _LOGGER.warning("Invalid RGB color value received")

                try:
                    x_color = float(values["color"]["x"])
                    y_color = float(values["color"]["y"])

                    self._hs = color_util.color_xy_to_hs(x_color, y_color)
                except KeyError:
                    pass
                except ValueError:
                    _LOGGER.warning("Invalid XY color value received")

                try:
                    hue = float(values["color"]["h"])
                    saturation = float(values["color"]["s"])

                    self._hs = (hue, saturation)
                except KeyError:
                    pass
                except ValueError:
                    _LOGGER.warning("Invalid HS color value received")

            if self._brightness is not None:
                try:
                    self._brightness = int(
                        values["brightness"]
                        / float(self._config[CONF_BRIGHTNESS_SCALE])
                        * 255
                    )
                except KeyError:
                    pass
                except (TypeError, ValueError):
                    _LOGGER.warning("Invalid brightness value received")

            if self._color_temp is not None:
                try:
                    self._color_temp = int(values["color_temp"])
                except KeyError:
                    pass
                except ValueError:
                    _LOGGER.warning("Invalid color temp value received")

            if self._effect is not None:
                try:
                    self._effect = values["effect"]
                except KeyError:
                    pass

            if self._white_value is not None:
                try:
                    self._white_value = int(values["white_value"])
                except KeyError:
                    pass
                except ValueError:
                    _LOGGER.warning("Invalid white value received")

            self.async_write_ha_state()

        if self._topic[CONF_STATE_TOPIC] is not None:
            self._sub_state = await subscription.async_subscribe_topics(
                self.hass,
                self._sub_state,
                {
                    "state_topic": {
                        "topic": self._topic[CONF_STATE_TOPIC],
                        "msg_callback": state_received,
                        "qos": self._config[CONF_QOS],
                    }
                },
            )

        if self._optimistic and last_state:
            self._state = last_state.state == STATE_ON
            if last_state.attributes.get(ATTR_BRIGHTNESS):
                self._brightness = last_state.attributes.get(ATTR_BRIGHTNESS)
            if last_state.attributes.get(ATTR_HS_COLOR):
                self._hs = last_state.attributes.get(ATTR_HS_COLOR)
            if last_state.attributes.get(ATTR_COLOR_TEMP):
                self._color_temp = last_state.attributes.get(ATTR_COLOR_TEMP)
            if last_state.attributes.get(ATTR_EFFECT):
                self._effect = last_state.attributes.get(ATTR_EFFECT)
            if last_state.attributes.get(ATTR_WHITE_VALUE):
                self._white_value = last_state.attributes.get(ATTR_WHITE_VALUE)

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        self._sub_state = await subscription.async_unsubscribe_topics(
            self.hass, self._sub_state
        )
        await MqttAttributes.async_will_remove_from_hass(self)
        await MqttAvailability.async_will_remove_from_hass(self)
        await MqttDiscoveryUpdate.async_will_remove_from_hass(self)

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def color_temp(self):
        """Return the color temperature in mired."""
        return self._color_temp

    @property
    def effect(self):
        """Return the current effect."""
        return self._effect

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return self._config.get(CONF_EFFECT_LIST)

    @property
    def hs_color(self):
        """Return the hs color value."""
        return self._hs

    @property
    def white_value(self):
        """Return the white property."""
        return self._white_value

    @property
    def should_poll(self):
        """No polling needed for a MQTT light."""
        return False

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._config[CONF_NAME]

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def assumed_state(self):
        """Return true if we do optimistic updates."""
        return self._optimistic

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features

    async def async_turn_on(self, **kwargs):
        """Turn the device on.

        This method is a coroutine.
        """
        should_update = False

        message = {"state": "ON"}

        if ATTR_HS_COLOR in kwargs and (
            self._config[CONF_HS] or self._config[CONF_RGB] or self._config[CONF_XY]
        ):
            hs_color = kwargs[ATTR_HS_COLOR]
            message["color"] = {}
            if self._config[CONF_RGB]:
                # If there's a brightness topic set, we don't want to scale the
                # RGB values given using the brightness.
                if self._brightness is not None:
                    brightness = 255
                else:
                    brightness = kwargs.get(
                        ATTR_BRIGHTNESS, self._brightness if self._brightness else 255
                    )
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
                self._hs = kwargs[ATTR_HS_COLOR]
                should_update = True

        if ATTR_FLASH in kwargs:
            flash = kwargs.get(ATTR_FLASH)

            if flash == FLASH_LONG:
                message["flash"] = self._flash_times[CONF_FLASH_TIME_LONG]
            elif flash == FLASH_SHORT:
                message["flash"] = self._flash_times[CONF_FLASH_TIME_SHORT]

        if ATTR_TRANSITION in kwargs:
            message["transition"] = kwargs[ATTR_TRANSITION]

        if ATTR_BRIGHTNESS in kwargs and self._brightness is not None:
            message["brightness"] = int(
                kwargs[ATTR_BRIGHTNESS]
                / float(DEFAULT_BRIGHTNESS_SCALE)
                * self._config[CONF_BRIGHTNESS_SCALE]
            )

            if self._optimistic:
                self._brightness = kwargs[ATTR_BRIGHTNESS]
                should_update = True

        if ATTR_COLOR_TEMP in kwargs:
            message["color_temp"] = int(kwargs[ATTR_COLOR_TEMP])

            if self._optimistic:
                self._color_temp = kwargs[ATTR_COLOR_TEMP]
                should_update = True

        if ATTR_EFFECT in kwargs:
            message["effect"] = kwargs[ATTR_EFFECT]

            if self._optimistic:
                self._effect = kwargs[ATTR_EFFECT]
                should_update = True

        if ATTR_WHITE_VALUE in kwargs:
            message["white_value"] = int(kwargs[ATTR_WHITE_VALUE])

            if self._optimistic:
                self._white_value = kwargs[ATTR_WHITE_VALUE]
                should_update = True

        mqtt.async_publish(
            self.hass,
            self._topic[CONF_COMMAND_TOPIC],
            json.dumps(message),
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )

        if self._optimistic:
            # Optimistically assume that the light has changed state.
            self._state = True
            should_update = True

        if should_update:
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the device off.

        This method is a coroutine.
        """
        message = {"state": "OFF"}

        if ATTR_TRANSITION in kwargs:
            message["transition"] = kwargs[ATTR_TRANSITION]

        mqtt.async_publish(
            self.hass,
            self._topic[CONF_COMMAND_TOPIC],
            json.dumps(message),
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )

        if self._optimistic:
            # Optimistically assume that the light has changed state.
            self._state = False
            self.async_write_ha_state()
