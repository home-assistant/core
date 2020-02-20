"""Support for MQTT cover devices."""
import logging

import voluptuous as vol

from homeassistant.components import cover, mqtt
from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DEVICE_CLASSES_SCHEMA,
    SUPPORT_CLOSE,
    SUPPORT_CLOSE_TILT,
    SUPPORT_OPEN,
    SUPPORT_OPEN_TILT,
    SUPPORT_SET_POSITION,
    SUPPORT_SET_TILT_POSITION,
    SUPPORT_STOP,
    SUPPORT_STOP_TILT,
    CoverDevice,
)
from homeassistant.const import (
    CONF_DEVICE,
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_VALUE_TEMPLATE,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
    STATE_UNKNOWN,
)
from homeassistant.core import callback
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from . import (
    ATTR_DISCOVERY_HASH,
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
from .discovery import MQTT_DISCOVERY_NEW, clear_discovery_hash

_LOGGER = logging.getLogger(__name__)

CONF_GET_POSITION_TOPIC = "position_topic"
CONF_SET_POSITION_TEMPLATE = "set_position_template"
CONF_SET_POSITION_TOPIC = "set_position_topic"
CONF_TILT_COMMAND_TOPIC = "tilt_command_topic"
CONF_TILT_STATUS_TOPIC = "tilt_status_topic"
CONF_TILT_STATUS_TEMPLATE = "tilt_status_template"

CONF_PAYLOAD_CLOSE = "payload_close"
CONF_PAYLOAD_OPEN = "payload_open"
CONF_PAYLOAD_STOP = "payload_stop"
CONF_POSITION_CLOSED = "position_closed"
CONF_POSITION_OPEN = "position_open"
CONF_STATE_CLOSED = "state_closed"
CONF_STATE_CLOSING = "state_closing"
CONF_STATE_OPEN = "state_open"
CONF_STATE_OPENING = "state_opening"
CONF_TILT_CLOSED_POSITION = "tilt_closed_value"
CONF_TILT_INVERT_STATE = "tilt_invert_state"
CONF_TILT_MAX = "tilt_max"
CONF_TILT_MIN = "tilt_min"
CONF_TILT_OPEN_POSITION = "tilt_opened_value"
CONF_TILT_STATE_OPTIMISTIC = "tilt_optimistic"

TILT_PAYLOAD = "tilt"
COVER_PAYLOAD = "cover"

DEFAULT_NAME = "MQTT Cover"
DEFAULT_OPTIMISTIC = False
DEFAULT_PAYLOAD_CLOSE = "CLOSE"
DEFAULT_PAYLOAD_OPEN = "OPEN"
DEFAULT_PAYLOAD_STOP = "STOP"
DEFAULT_POSITION_CLOSED = 0
DEFAULT_POSITION_OPEN = 100
DEFAULT_RETAIN = False
DEFAULT_TILT_CLOSED_POSITION = 0
DEFAULT_TILT_INVERT_STATE = False
DEFAULT_TILT_MAX = 100
DEFAULT_TILT_MIN = 0
DEFAULT_TILT_OPEN_POSITION = 100
DEFAULT_TILT_OPTIMISTIC = False

OPEN_CLOSE_FEATURES = SUPPORT_OPEN | SUPPORT_CLOSE
TILT_FEATURES = (
    SUPPORT_OPEN_TILT
    | SUPPORT_CLOSE_TILT
    | SUPPORT_STOP_TILT
    | SUPPORT_SET_TILT_POSITION
)


def validate_options(value):
    """Validate options.

    If set position topic is set then get position topic is set as well.
    """
    if CONF_SET_POSITION_TOPIC in value and CONF_GET_POSITION_TOPIC not in value:
        raise vol.Invalid(
            "set_position_topic must be set together with position_topic."
        )
    return value


PLATFORM_SCHEMA = vol.All(
    mqtt.MQTT_BASE_PLATFORM_SCHEMA.extend(
        {
            vol.Optional(CONF_COMMAND_TOPIC): mqtt.valid_publish_topic,
            vol.Optional(CONF_DEVICE): mqtt.MQTT_ENTITY_DEVICE_INFO_SCHEMA,
            vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
            vol.Optional(CONF_GET_POSITION_TOPIC): mqtt.valid_subscribe_topic,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
            vol.Optional(CONF_PAYLOAD_CLOSE, default=DEFAULT_PAYLOAD_CLOSE): cv.string,
            vol.Optional(CONF_PAYLOAD_OPEN, default=DEFAULT_PAYLOAD_OPEN): cv.string,
            vol.Optional(CONF_PAYLOAD_STOP, default=DEFAULT_PAYLOAD_STOP): vol.Any(
                cv.string, None
            ),
            vol.Optional(CONF_POSITION_CLOSED, default=DEFAULT_POSITION_CLOSED): int,
            vol.Optional(CONF_POSITION_OPEN, default=DEFAULT_POSITION_OPEN): int,
            vol.Optional(CONF_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
            vol.Optional(CONF_SET_POSITION_TEMPLATE): cv.template,
            vol.Optional(CONF_SET_POSITION_TOPIC): mqtt.valid_publish_topic,
            vol.Optional(CONF_STATE_CLOSED, default=STATE_CLOSED): cv.string,
            vol.Optional(CONF_STATE_CLOSING, default=STATE_CLOSING): cv.string,
            vol.Optional(CONF_STATE_OPEN, default=STATE_OPEN): cv.string,
            vol.Optional(CONF_STATE_OPENING, default=STATE_OPENING): cv.string,
            vol.Optional(CONF_STATE_TOPIC): mqtt.valid_subscribe_topic,
            vol.Optional(
                CONF_TILT_CLOSED_POSITION, default=DEFAULT_TILT_CLOSED_POSITION
            ): int,
            vol.Optional(CONF_TILT_COMMAND_TOPIC): mqtt.valid_publish_topic,
            vol.Optional(
                CONF_TILT_INVERT_STATE, default=DEFAULT_TILT_INVERT_STATE
            ): cv.boolean,
            vol.Optional(CONF_TILT_MAX, default=DEFAULT_TILT_MAX): int,
            vol.Optional(CONF_TILT_MIN, default=DEFAULT_TILT_MIN): int,
            vol.Optional(
                CONF_TILT_OPEN_POSITION, default=DEFAULT_TILT_OPEN_POSITION
            ): int,
            vol.Optional(
                CONF_TILT_STATE_OPTIMISTIC, default=DEFAULT_TILT_OPTIMISTIC
            ): cv.boolean,
            vol.Optional(CONF_TILT_STATUS_TOPIC): mqtt.valid_subscribe_topic,
            vol.Optional(CONF_TILT_STATUS_TEMPLATE): cv.template,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
            vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        }
    )
    .extend(mqtt.MQTT_AVAILABILITY_SCHEMA.schema)
    .extend(mqtt.MQTT_JSON_ATTRS_SCHEMA.schema),
    validate_options,
)


async def async_setup_platform(
    hass: HomeAssistantType, config: ConfigType, async_add_entities, discovery_info=None
):
    """Set up MQTT cover through configuration.yaml."""
    await _async_setup_entity(config, async_add_entities)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MQTT cover dynamically through MQTT discovery."""

    async def async_discover(discovery_payload):
        """Discover and add an MQTT cover."""
        discovery_hash = discovery_payload.pop(ATTR_DISCOVERY_HASH)
        try:
            config = PLATFORM_SCHEMA(discovery_payload)
            await _async_setup_entity(
                config, async_add_entities, config_entry, discovery_hash
            )
        except Exception:
            clear_discovery_hash(hass, discovery_hash)
            raise

    async_dispatcher_connect(
        hass, MQTT_DISCOVERY_NEW.format(cover.DOMAIN, "mqtt"), async_discover
    )


async def _async_setup_entity(
    config, async_add_entities, config_entry=None, discovery_hash=None
):
    """Set up the MQTT Cover."""
    async_add_entities([MqttCover(config, config_entry, discovery_hash)])


class MqttCover(
    MqttAttributes,
    MqttAvailability,
    MqttDiscoveryUpdate,
    MqttEntityDeviceInfo,
    CoverDevice,
):
    """Representation of a cover that can be controlled using MQTT."""

    def __init__(self, config, config_entry, discovery_hash):
        """Initialize the cover."""
        self._unique_id = config.get(CONF_UNIQUE_ID)
        self._position = None
        self._state = None
        self._sub_state = None

        self._optimistic = None
        self._tilt_value = None
        self._tilt_optimistic = None

        # Load config
        self._setup_from_config(config)

        device_config = config.get(CONF_DEVICE)

        MqttAttributes.__init__(self, config)
        MqttAvailability.__init__(self, config)
        MqttDiscoveryUpdate.__init__(self, discovery_hash, self.discovery_update)
        MqttEntityDeviceInfo.__init__(self, device_config, config_entry)

    async def async_added_to_hass(self):
        """Subscribe MQTT events."""
        await super().async_added_to_hass()
        await self._subscribe_topics()

    async def discovery_update(self, discovery_payload):
        """Handle updated discovery message."""
        config = PLATFORM_SCHEMA(discovery_payload)
        self._setup_from_config(config)
        await self.attributes_discovery_update(config)
        await self.availability_discovery_update(config)
        await self.device_info_discovery_update(config)
        await self._subscribe_topics()
        self.async_write_ha_state()

    def _setup_from_config(self, config):
        self._config = config
        self._optimistic = config[CONF_OPTIMISTIC] or (
            config.get(CONF_STATE_TOPIC) is None
            and config.get(CONF_GET_POSITION_TOPIC) is None
        )
        self._tilt_optimistic = config[CONF_TILT_STATE_OPTIMISTIC]

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""
        template = self._config.get(CONF_VALUE_TEMPLATE)
        if template is not None:
            template.hass = self.hass
        set_position_template = self._config.get(CONF_SET_POSITION_TEMPLATE)
        if set_position_template is not None:
            set_position_template.hass = self.hass
        tilt_status_template = self._config.get(CONF_TILT_STATUS_TEMPLATE)
        if tilt_status_template is not None:
            tilt_status_template.hass = self.hass

        topics = {}

        @callback
        def tilt_updated(msg):
            """Handle tilt updates."""
            payload = msg.payload
            if tilt_status_template is not None:
                payload = tilt_status_template.async_render_with_possible_json_value(
                    payload
                )

            if payload.isnumeric() and (
                self._config[CONF_TILT_MIN]
                <= int(payload)
                <= self._config[CONF_TILT_MAX]
            ):

                level = self.find_percentage_in_range(float(payload))
                self._tilt_value = level
                self.async_write_ha_state()

        @callback
        def state_message_received(msg):
            """Handle new MQTT state messages."""
            payload = msg.payload
            if template is not None:
                payload = template.async_render_with_possible_json_value(payload)

            if payload == self._config[CONF_STATE_OPEN]:
                self._state = STATE_OPEN
            elif payload == self._config[CONF_STATE_OPENING]:
                self._state = STATE_OPENING
            elif payload == self._config[CONF_STATE_CLOSED]:
                self._state = STATE_CLOSED
            elif payload == self._config[CONF_STATE_CLOSING]:
                self._state = STATE_CLOSING
            else:
                _LOGGER.warning(
                    "Payload is not supported (e.g. open, closed, opening, closing): %s",
                    payload,
                )
                return

            self.async_write_ha_state()

        @callback
        def position_message_received(msg):
            """Handle new MQTT state messages."""
            payload = msg.payload
            if template is not None:
                payload = template.async_render_with_possible_json_value(payload)

            if payload.isnumeric():
                percentage_payload = self.find_percentage_in_range(
                    float(payload), COVER_PAYLOAD
                )
                self._position = percentage_payload
                self._state = (
                    STATE_CLOSED
                    if percentage_payload == DEFAULT_POSITION_CLOSED
                    else STATE_OPEN
                )
            else:
                _LOGGER.warning("Payload is not integer within range: %s", payload)
                return
            self.async_write_ha_state()

        if self._config.get(CONF_GET_POSITION_TOPIC):
            topics["get_position_topic"] = {
                "topic": self._config.get(CONF_GET_POSITION_TOPIC),
                "msg_callback": position_message_received,
                "qos": self._config[CONF_QOS],
            }
        elif self._config.get(CONF_STATE_TOPIC):
            topics["state_topic"] = {
                "topic": self._config.get(CONF_STATE_TOPIC),
                "msg_callback": state_message_received,
                "qos": self._config[CONF_QOS],
            }
        else:
            # Force into optimistic mode.
            self._optimistic = True

        if self._config.get(CONF_TILT_STATUS_TOPIC) is None:
            self._tilt_optimistic = True
        else:
            self._tilt_value = STATE_UNKNOWN
            topics["tilt_status_topic"] = {
                "topic": self._config.get(CONF_TILT_STATUS_TOPIC),
                "msg_callback": tilt_updated,
                "qos": self._config[CONF_QOS],
            }

        self._sub_state = await subscription.async_subscribe_topics(
            self.hass, self._sub_state, topics
        )

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        self._sub_state = await subscription.async_unsubscribe_topics(
            self.hass, self._sub_state
        )
        await MqttAttributes.async_will_remove_from_hass(self)
        await MqttAvailability.async_will_remove_from_hass(self)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def assumed_state(self):
        """Return true if we do optimistic updates."""
        return self._optimistic

    @property
    def name(self):
        """Return the name of the cover."""
        return self._config[CONF_NAME]

    @property
    def is_closed(self):
        """Return true if the cover is closed or None if the status is unknown."""
        if self._state is None:
            return None

        return self._state == STATE_CLOSED

    @property
    def is_opening(self):
        """Return true if the cover is actively opening."""
        return self._state == STATE_OPENING

    @property
    def is_closing(self):
        """Return true if the cover is actively closing."""
        return self._state == STATE_CLOSING

    @property
    def current_cover_position(self):
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return self._position

    @property
    def current_cover_tilt_position(self):
        """Return current position of cover tilt."""
        return self._tilt_value

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._config.get(CONF_DEVICE_CLASS)

    @property
    def supported_features(self):
        """Flag supported features."""
        supported_features = 0
        if self._config.get(CONF_COMMAND_TOPIC) is not None:
            supported_features = OPEN_CLOSE_FEATURES

            if self._config.get(CONF_PAYLOAD_STOP) is not None:
                supported_features |= SUPPORT_STOP

        if self._config.get(CONF_SET_POSITION_TOPIC) is not None:
            supported_features |= SUPPORT_SET_POSITION

        if self._config.get(CONF_TILT_COMMAND_TOPIC) is not None:
            supported_features |= TILT_FEATURES

        return supported_features

    async def async_open_cover(self, **kwargs):
        """Move the cover up.

        This method is a coroutine.
        """
        mqtt.async_publish(
            self.hass,
            self._config.get(CONF_COMMAND_TOPIC),
            self._config[CONF_PAYLOAD_OPEN],
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )
        if self._optimistic:
            # Optimistically assume that cover has changed state.
            self._state = STATE_OPEN
            if self._config.get(CONF_GET_POSITION_TOPIC):
                self._position = self.find_percentage_in_range(
                    self._config[CONF_POSITION_OPEN], COVER_PAYLOAD
                )
            self.async_write_ha_state()

    async def async_close_cover(self, **kwargs):
        """Move the cover down.

        This method is a coroutine.
        """
        mqtt.async_publish(
            self.hass,
            self._config.get(CONF_COMMAND_TOPIC),
            self._config[CONF_PAYLOAD_CLOSE],
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )
        if self._optimistic:
            # Optimistically assume that cover has changed state.
            self._state = STATE_CLOSED
            if self._config.get(CONF_GET_POSITION_TOPIC):
                self._position = self.find_percentage_in_range(
                    self._config[CONF_POSITION_CLOSED], COVER_PAYLOAD
                )
            self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs):
        """Stop the device.

        This method is a coroutine.
        """
        mqtt.async_publish(
            self.hass,
            self._config.get(CONF_COMMAND_TOPIC),
            self._config[CONF_PAYLOAD_STOP],
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )

    async def async_open_cover_tilt(self, **kwargs):
        """Tilt the cover open."""
        mqtt.async_publish(
            self.hass,
            self._config.get(CONF_TILT_COMMAND_TOPIC),
            self._config[CONF_TILT_OPEN_POSITION],
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )
        if self._tilt_optimistic:
            self._tilt_value = self.find_percentage_in_range(
                float(self._config[CONF_TILT_OPEN_POSITION])
            )
            self.async_write_ha_state()

    async def async_close_cover_tilt(self, **kwargs):
        """Tilt the cover closed."""
        mqtt.async_publish(
            self.hass,
            self._config.get(CONF_TILT_COMMAND_TOPIC),
            self._config[CONF_TILT_CLOSED_POSITION],
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )
        if self._tilt_optimistic:
            self._tilt_value = self.find_percentage_in_range(
                float(self._config[CONF_TILT_CLOSED_POSITION])
            )
            self.async_write_ha_state()

    async def async_set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific position."""
        if ATTR_TILT_POSITION not in kwargs:
            return

        position = float(kwargs[ATTR_TILT_POSITION])

        # The position needs to be between min and max
        level = self.find_in_range_from_percent(position)

        mqtt.async_publish(
            self.hass,
            self._config.get(CONF_TILT_COMMAND_TOPIC),
            level,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        set_position_template = self._config.get(CONF_SET_POSITION_TEMPLATE)
        if ATTR_POSITION in kwargs:
            position = kwargs[ATTR_POSITION]
            percentage_position = position
            if set_position_template is not None:
                try:
                    position = set_position_template.async_render(**kwargs)
                except TemplateError as ex:
                    _LOGGER.error(ex)
                    self._state = None
            elif (
                self._config[CONF_POSITION_OPEN] != 100
                and self._config[CONF_POSITION_CLOSED] != 0
            ):
                position = self.find_in_range_from_percent(position, COVER_PAYLOAD)

            mqtt.async_publish(
                self.hass,
                self._config.get(CONF_SET_POSITION_TOPIC),
                position,
                self._config[CONF_QOS],
                self._config[CONF_RETAIN],
            )
            if self._optimistic:
                self._state = (
                    STATE_CLOSED
                    if percentage_position == self._config[CONF_POSITION_CLOSED]
                    else STATE_OPEN
                )
                self._position = percentage_position
                self.async_write_ha_state()

    async def async_toggle_tilt(self, **kwargs):
        """Toggle the entity."""
        if self.is_tilt_closed():
            await self.async_open_cover_tilt(**kwargs)
        else:
            await self.async_close_cover_tilt(**kwargs)

    def is_tilt_closed(self):
        """Return if the cover is tilted closed."""
        return self._tilt_value == self.find_percentage_in_range(
            float(self._config[CONF_TILT_CLOSED_POSITION])
        )

    def find_percentage_in_range(self, position, range_type=TILT_PAYLOAD):
        """Find the 0-100% value within the specified range."""
        # the range of motion as defined by the min max values
        if range_type == COVER_PAYLOAD:
            max_range = self._config[CONF_POSITION_OPEN]
            min_range = self._config[CONF_POSITION_CLOSED]
        else:
            max_range = self._config[CONF_TILT_MAX]
            min_range = self._config[CONF_TILT_MIN]
        current_range = max_range - min_range
        # offset to be zero based
        offset_position = position - min_range
        position_percentage = round(float(offset_position) / current_range * 100.0)

        max_percent = 100
        min_percent = 0
        position_percentage = min(max(position_percentage, min_percent), max_percent)
        if range_type == TILT_PAYLOAD and self._config[CONF_TILT_INVERT_STATE]:
            return 100 - position_percentage
        return position_percentage

    def find_in_range_from_percent(self, percentage, range_type=TILT_PAYLOAD):
        """
        Find the adjusted value for 0-100% within the specified range.

        if the range is 80-180 and the percentage is 90
        this method would determine the value to send on the topic
        by offsetting the max and min, getting the percentage value and
        returning the offset
        """
        if range_type == COVER_PAYLOAD:
            max_range = self._config[CONF_POSITION_OPEN]
            min_range = self._config[CONF_POSITION_CLOSED]
        else:
            max_range = self._config[CONF_TILT_MAX]
            min_range = self._config[CONF_TILT_MIN]
        offset = min_range
        current_range = max_range - min_range
        position = round(current_range * (percentage / 100.0))
        position += offset

        if range_type == TILT_PAYLOAD and self._config[CONF_TILT_INVERT_STATE]:
            position = max_range - position + offset
        return position

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id
