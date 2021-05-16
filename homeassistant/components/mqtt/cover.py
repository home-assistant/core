"""Support for MQTT cover devices."""
import functools
import logging

import voluptuous as vol

from homeassistant.components import cover
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
    CoverEntity,
)
from homeassistant.const import (
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
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.typing import ConfigType

from . import (
    CONF_COMMAND_TOPIC,
    CONF_QOS,
    CONF_RETAIN,
    CONF_STATE_TOPIC,
    DOMAIN,
    PLATFORMS,
    subscription,
)
from .. import mqtt
from .debug_info import log_messages
from .mixins import MQTT_ENTITY_COMMON_SCHEMA, MqttEntity, async_setup_entry_helper

_LOGGER = logging.getLogger(__name__)

CONF_GET_POSITION_TOPIC = "position_topic"
CONF_GET_POSITION_TEMPLATE = "position_template"
CONF_SET_POSITION_TOPIC = "set_position_topic"
CONF_SET_POSITION_TEMPLATE = "set_position_template"
CONF_TILT_COMMAND_TOPIC = "tilt_command_topic"
CONF_TILT_COMMAND_TEMPLATE = "tilt_command_template"
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
CONF_STATE_STOPPED = "state_stopped"
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
DEFAULT_STATE_STOPPED = "stopped"
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
            "'set_position_topic' must be set together with 'position_topic'."
        )

    if (
        CONF_GET_POSITION_TOPIC in value
        and CONF_STATE_TOPIC not in value
        and CONF_VALUE_TEMPLATE in value
    ):
        _LOGGER.warning(
            "Using 'value_template' for 'position_topic' is deprecated "
            "and will be removed from Home Assistant in version 2021.6, "
            "please replace it with 'position_template'"
        )

    if CONF_TILT_INVERT_STATE in value:
        _LOGGER.warning(
            "'tilt_invert_state' is deprecated "
            "and will be removed from Home Assistant in version 2021.6, "
            "please invert tilt using 'tilt_min' & 'tilt_max'"
        )

    return value


PLATFORM_SCHEMA = vol.All(
    mqtt.MQTT_BASE_PLATFORM_SCHEMA.extend(
        {
            vol.Optional(CONF_COMMAND_TOPIC): mqtt.valid_publish_topic,
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
            vol.Optional(CONF_STATE_STOPPED, default=DEFAULT_STATE_STOPPED): cv.string,
            vol.Optional(CONF_STATE_TOPIC): mqtt.valid_subscribe_topic,
            vol.Optional(
                CONF_TILT_CLOSED_POSITION, default=DEFAULT_TILT_CLOSED_POSITION
            ): int,
            vol.Optional(CONF_TILT_COMMAND_TOPIC): mqtt.valid_publish_topic,
            vol.Optional(CONF_TILT_INVERT_STATE): cv.boolean,
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
            vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
            vol.Optional(CONF_GET_POSITION_TEMPLATE): cv.template,
            vol.Optional(CONF_TILT_COMMAND_TEMPLATE): cv.template,
        }
    ).extend(MQTT_ENTITY_COMMON_SCHEMA.schema),
    validate_options,
)


async def async_setup_platform(
    hass: HomeAssistant, config: ConfigType, async_add_entities, discovery_info=None
):
    """Set up MQTT cover through configuration.yaml."""
    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)
    await _async_setup_entity(hass, async_add_entities, config)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MQTT cover dynamically through MQTT discovery."""
    setup = functools.partial(
        _async_setup_entity, hass, async_add_entities, config_entry=config_entry
    )
    await async_setup_entry_helper(hass, cover.DOMAIN, setup, PLATFORM_SCHEMA)


async def _async_setup_entity(
    hass, async_add_entities, config, config_entry=None, discovery_data=None
):
    """Set up the MQTT Cover."""
    async_add_entities([MqttCover(hass, config, config_entry, discovery_data)])


class MqttCover(MqttEntity, CoverEntity):
    """Representation of a cover that can be controlled using MQTT."""

    def __init__(self, hass, config, config_entry, discovery_data):
        """Initialize the cover."""
        self._position = None
        self._state = None

        self._optimistic = None
        self._tilt_value = None
        self._tilt_optimistic = None

        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema():
        """Return the config schema."""
        return PLATFORM_SCHEMA

    def _setup_from_config(self, config):
        self._optimistic = config[CONF_OPTIMISTIC] or (
            config.get(CONF_STATE_TOPIC) is None
            and config.get(CONF_GET_POSITION_TOPIC) is None
        )
        self._tilt_optimistic = config[CONF_TILT_STATE_OPTIMISTIC]

        value_template = self._config.get(CONF_VALUE_TEMPLATE)
        if value_template is not None:
            value_template.hass = self.hass

        set_position_template = self._config.get(CONF_SET_POSITION_TEMPLATE)
        if set_position_template is not None:
            set_position_template.hass = self.hass

        get_position_template = self._config.get(CONF_GET_POSITION_TEMPLATE)
        if get_position_template is not None:
            get_position_template.hass = self.hass

        set_tilt_template = self._config.get(CONF_TILT_COMMAND_TEMPLATE)
        if set_tilt_template is not None:
            set_tilt_template.hass = self.hass

        tilt_status_template = self._config.get(CONF_TILT_STATUS_TEMPLATE)
        if tilt_status_template is not None:
            tilt_status_template.hass = self.hass

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""
        topics = {}

        @callback
        @log_messages(self.hass, self.entity_id)
        def tilt_message_received(msg):
            """Handle tilt updates."""
            payload = msg.payload
            tilt_status_template = self._config.get(CONF_TILT_STATUS_TEMPLATE)
            if tilt_status_template is not None:
                payload = tilt_status_template.async_render_with_possible_json_value(
                    payload
                )

            if not payload:
                _LOGGER.debug("Ignoring empty tilt message from '%s'", msg.topic)
                return

            if not payload.isnumeric():
                _LOGGER.warning("Payload '%s' is not numeric", payload)
            elif (
                self._config[CONF_TILT_MIN]
                <= int(payload)
                <= self._config[CONF_TILT_MAX]
                or self._config[CONF_TILT_MAX]
                <= int(payload)
                <= self._config[CONF_TILT_MIN]
            ):
                level = self.find_percentage_in_range(float(payload))
                self._tilt_value = level
                self.async_write_ha_state()
            else:
                _LOGGER.warning(
                    "Payload '%s' is out of range, must be between '%s' and '%s' inclusive",
                    payload,
                    self._config[CONF_TILT_MIN],
                    self._config[CONF_TILT_MAX],
                )

        @callback
        @log_messages(self.hass, self.entity_id)
        def state_message_received(msg):
            """Handle new MQTT state messages."""
            payload = msg.payload
            value_template = self._config.get(CONF_VALUE_TEMPLATE)
            if value_template is not None:
                payload = value_template.async_render_with_possible_json_value(payload)

            if not payload:
                _LOGGER.debug("Ignoring empty state message from '%s'", msg.topic)
                return

            if payload == self._config[CONF_STATE_STOPPED]:
                if self._config.get(CONF_GET_POSITION_TOPIC) is not None:
                    self._state = (
                        STATE_CLOSED
                        if self._position == DEFAULT_POSITION_CLOSED
                        else STATE_OPEN
                    )
                else:
                    self._state = (
                        STATE_CLOSED if self._state == STATE_CLOSING else STATE_OPEN
                    )
            elif payload == self._config[CONF_STATE_OPENING]:
                self._state = STATE_OPENING
            elif payload == self._config[CONF_STATE_CLOSING]:
                self._state = STATE_CLOSING
            elif payload == self._config[CONF_STATE_OPEN]:
                self._state = STATE_OPEN
            elif payload == self._config[CONF_STATE_CLOSED]:
                self._state = STATE_CLOSED
            else:
                _LOGGER.warning(
                    "Payload is not supported (e.g. open, closed, opening, closing, stopped): %s",
                    payload,
                )
                return

            self.async_write_ha_state()

        @callback
        @log_messages(self.hass, self.entity_id)
        def position_message_received(msg):
            """Handle new MQTT position messages."""
            payload = msg.payload

            template = self._config.get(CONF_GET_POSITION_TEMPLATE)

            # To be removed in 2021.6:
            # allow using `value_template` as position template if no `state_topic`
            if template is None and self._config.get(CONF_STATE_TOPIC) is None:
                template = self._config.get(CONF_VALUE_TEMPLATE)

            if template is not None:
                payload = template.async_render_with_possible_json_value(payload)

            if not payload:
                _LOGGER.debug("Ignoring empty position message from '%s'", msg.topic)
                return

            if payload.isnumeric():
                percentage_payload = self.find_percentage_in_range(
                    float(payload), COVER_PAYLOAD
                )
                self._position = percentage_payload
                if self._config.get(CONF_STATE_TOPIC) is None:
                    self._state = (
                        STATE_CLOSED
                        if percentage_payload == DEFAULT_POSITION_CLOSED
                        else STATE_OPEN
                    )
            else:
                _LOGGER.warning("Payload '%s' is not numeric", payload)
                return
            self.async_write_ha_state()

        if self._config.get(CONF_GET_POSITION_TOPIC):
            topics["get_position_topic"] = {
                "topic": self._config.get(CONF_GET_POSITION_TOPIC),
                "msg_callback": position_message_received,
                "qos": self._config[CONF_QOS],
            }

        if self._config.get(CONF_STATE_TOPIC):
            topics["state_topic"] = {
                "topic": self._config.get(CONF_STATE_TOPIC),
                "msg_callback": state_message_received,
                "qos": self._config[CONF_QOS],
            }

        if (
            self._config.get(CONF_GET_POSITION_TOPIC) is None
            and self._config.get(CONF_STATE_TOPIC) is None
        ):
            # Force into optimistic mode.
            self._optimistic = True

        if self._config.get(CONF_TILT_STATUS_TOPIC) is None:
            self._tilt_optimistic = True
        else:
            self._tilt_value = STATE_UNKNOWN
            topics["tilt_status_topic"] = {
                "topic": self._config.get(CONF_TILT_STATUS_TOPIC),
                "msg_callback": tilt_message_received,
                "qos": self._config[CONF_QOS],
            }

        self._sub_state = await subscription.async_subscribe_topics(
            self.hass, self._sub_state, topics
        )

    @property
    def assumed_state(self):
        """Return true if we do optimistic updates."""
        return self._optimistic

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
        set_tilt_template = self._config.get(CONF_TILT_COMMAND_TEMPLATE)
        tilt = kwargs[ATTR_TILT_POSITION]
        percentage_tilt = tilt
        tilt = self.find_in_range_from_percent(tilt)
        if set_tilt_template is not None:
            tilt = set_tilt_template.async_render(parse_result=False, **kwargs)

        mqtt.async_publish(
            self.hass,
            self._config.get(CONF_TILT_COMMAND_TOPIC),
            tilt,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )
        if self._tilt_optimistic:
            self._tilt_value = percentage_tilt
            self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        set_position_template = self._config.get(CONF_SET_POSITION_TEMPLATE)
        position = kwargs[ATTR_POSITION]
        percentage_position = position
        position = self.find_in_range_from_percent(position, COVER_PAYLOAD)
        if set_position_template is not None:
            position = set_position_template.async_render(parse_result=False, **kwargs)

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
        if range_type == TILT_PAYLOAD and self._config.get(CONF_TILT_INVERT_STATE):
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

        if range_type == TILT_PAYLOAD and self._config.get(CONF_TILT_INVERT_STATE):
            position = max_range - position + offset
        return position
