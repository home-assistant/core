"""Support for a State MQTT vacuum."""
import voluptuous as vol

from homeassistant.components.vacuum import (
    DOMAIN as VACUUM_DOMAIN,
    ENTITY_ID_FORMAT,
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_ERROR,
    STATE_RETURNING,
    StateVacuumEntity,
    VacuumEntityFeature,
)
from homeassistant.const import (
    ATTR_SUPPORTED_FEATURES,
    CONF_NAME,
    STATE_IDLE,
    STATE_PAUSED,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.json import json_dumps, json_loads

from .. import subscription
from ..config import MQTT_BASE_SCHEMA
from ..const import (
    CONF_COMMAND_TOPIC,
    CONF_ENCODING,
    CONF_QOS,
    CONF_RETAIN,
    CONF_STATE_TOPIC,
)
from ..debug_info import log_messages
from ..mixins import MQTT_ENTITY_COMMON_SCHEMA, MqttEntity, warn_for_legacy_schema
from ..util import valid_publish_topic
from .const import MQTT_VACUUM_ATTRIBUTES_BLOCKED
from .schema import MQTT_VACUUM_SCHEMA, services_to_strings, strings_to_services

SERVICE_TO_STRING = {
    VacuumEntityFeature.START: "start",
    VacuumEntityFeature.PAUSE: "pause",
    VacuumEntityFeature.STOP: "stop",
    VacuumEntityFeature.RETURN_HOME: "return_home",
    VacuumEntityFeature.FAN_SPEED: "fan_speed",
    VacuumEntityFeature.BATTERY: "battery",
    VacuumEntityFeature.STATUS: "status",
    VacuumEntityFeature.SEND_COMMAND: "send_command",
    VacuumEntityFeature.LOCATE: "locate",
    VacuumEntityFeature.CLEAN_SPOT: "clean_spot",
}

STRING_TO_SERVICE = {v: k for k, v in SERVICE_TO_STRING.items()}


DEFAULT_SERVICES = (
    VacuumEntityFeature.START
    | VacuumEntityFeature.STOP
    | VacuumEntityFeature.RETURN_HOME
    | VacuumEntityFeature.STATUS
    | VacuumEntityFeature.BATTERY
    | VacuumEntityFeature.CLEAN_SPOT
)
ALL_SERVICES = (
    DEFAULT_SERVICES
    | VacuumEntityFeature.PAUSE
    | VacuumEntityFeature.LOCATE
    | VacuumEntityFeature.FAN_SPEED
    | VacuumEntityFeature.SEND_COMMAND
)

BATTERY = "battery_level"
FAN_SPEED = "fan_speed"
STATE = "state"

POSSIBLE_STATES = {
    STATE_IDLE: STATE_IDLE,
    STATE_DOCKED: STATE_DOCKED,
    STATE_ERROR: STATE_ERROR,
    STATE_PAUSED: STATE_PAUSED,
    STATE_RETURNING: STATE_RETURNING,
    STATE_CLEANING: STATE_CLEANING,
}

CONF_SUPPORTED_FEATURES = ATTR_SUPPORTED_FEATURES
CONF_PAYLOAD_TURN_ON = "payload_turn_on"
CONF_PAYLOAD_TURN_OFF = "payload_turn_off"
CONF_PAYLOAD_RETURN_TO_BASE = "payload_return_to_base"
CONF_PAYLOAD_STOP = "payload_stop"
CONF_PAYLOAD_CLEAN_SPOT = "payload_clean_spot"
CONF_PAYLOAD_LOCATE = "payload_locate"
CONF_PAYLOAD_START = "payload_start"
CONF_PAYLOAD_PAUSE = "payload_pause"
CONF_SET_FAN_SPEED_TOPIC = "set_fan_speed_topic"
CONF_FAN_SPEED_LIST = "fan_speed_list"
CONF_SEND_COMMAND_TOPIC = "send_command_topic"

DEFAULT_NAME = "MQTT State Vacuum"
DEFAULT_RETAIN = False
DEFAULT_SERVICE_STRINGS = services_to_strings(DEFAULT_SERVICES, SERVICE_TO_STRING)
DEFAULT_PAYLOAD_RETURN_TO_BASE = "return_to_base"
DEFAULT_PAYLOAD_STOP = "stop"
DEFAULT_PAYLOAD_CLEAN_SPOT = "clean_spot"
DEFAULT_PAYLOAD_LOCATE = "locate"
DEFAULT_PAYLOAD_START = "start"
DEFAULT_PAYLOAD_PAUSE = "pause"

PLATFORM_SCHEMA_STATE_MODERN = (
    MQTT_BASE_SCHEMA.extend(
        {
            vol.Optional(CONF_FAN_SPEED_LIST, default=[]): vol.All(
                cv.ensure_list, [cv.string]
            ),
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(
                CONF_PAYLOAD_CLEAN_SPOT, default=DEFAULT_PAYLOAD_CLEAN_SPOT
            ): cv.string,
            vol.Optional(
                CONF_PAYLOAD_LOCATE, default=DEFAULT_PAYLOAD_LOCATE
            ): cv.string,
            vol.Optional(
                CONF_PAYLOAD_RETURN_TO_BASE, default=DEFAULT_PAYLOAD_RETURN_TO_BASE
            ): cv.string,
            vol.Optional(CONF_PAYLOAD_START, default=DEFAULT_PAYLOAD_START): cv.string,
            vol.Optional(CONF_PAYLOAD_PAUSE, default=DEFAULT_PAYLOAD_PAUSE): cv.string,
            vol.Optional(CONF_PAYLOAD_STOP, default=DEFAULT_PAYLOAD_STOP): cv.string,
            vol.Optional(CONF_SEND_COMMAND_TOPIC): valid_publish_topic,
            vol.Optional(CONF_SET_FAN_SPEED_TOPIC): valid_publish_topic,
            vol.Optional(CONF_STATE_TOPIC): valid_publish_topic,
            vol.Optional(
                CONF_SUPPORTED_FEATURES, default=DEFAULT_SERVICE_STRINGS
            ): vol.All(cv.ensure_list, [vol.In(STRING_TO_SERVICE.keys())]),
            vol.Optional(CONF_COMMAND_TOPIC): valid_publish_topic,
            vol.Optional(CONF_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
        }
    )
    .extend(MQTT_ENTITY_COMMON_SCHEMA.schema)
    .extend(MQTT_VACUUM_SCHEMA.schema)
)

# Configuring MQTT Vacuums under the vacuum platform key is deprecated in HA Core 2022.6
PLATFORM_SCHEMA_STATE = vol.All(
    cv.PLATFORM_SCHEMA.extend(PLATFORM_SCHEMA_STATE_MODERN.schema),
    warn_for_legacy_schema(VACUUM_DOMAIN),
)

DISCOVERY_SCHEMA_STATE = PLATFORM_SCHEMA_STATE_MODERN.extend({}, extra=vol.REMOVE_EXTRA)


async def async_setup_entity_state(
    hass, config, async_add_entities, config_entry, discovery_data
):
    """Set up a State MQTT Vacuum."""
    async_add_entities([MqttStateVacuum(hass, config, config_entry, discovery_data)])


class MqttStateVacuum(MqttEntity, StateVacuumEntity):
    """Representation of a MQTT-controlled state vacuum."""

    _entity_id_format = ENTITY_ID_FORMAT
    _attributes_extra_blocked = MQTT_VACUUM_ATTRIBUTES_BLOCKED

    def __init__(self, hass, config, config_entry, discovery_data):
        """Initialize the vacuum."""
        self._state = None
        self._state_attrs = {}
        self._fan_speed_list = []

        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema():
        """Return the config schema."""
        return DISCOVERY_SCHEMA_STATE

    def _setup_from_config(self, config):
        supported_feature_strings = config[CONF_SUPPORTED_FEATURES]
        self._supported_features = strings_to_services(
            supported_feature_strings, STRING_TO_SERVICE
        )
        self._fan_speed_list = config[CONF_FAN_SPEED_LIST]
        self._command_topic = config.get(CONF_COMMAND_TOPIC)
        self._set_fan_speed_topic = config.get(CONF_SET_FAN_SPEED_TOPIC)
        self._send_command_topic = config.get(CONF_SEND_COMMAND_TOPIC)

        self._payloads = {
            key: config.get(key)
            for key in (
                CONF_PAYLOAD_START,
                CONF_PAYLOAD_PAUSE,
                CONF_PAYLOAD_STOP,
                CONF_PAYLOAD_RETURN_TO_BASE,
                CONF_PAYLOAD_CLEAN_SPOT,
                CONF_PAYLOAD_LOCATE,
            )
        }

    def _prepare_subscribe_topics(self):
        """(Re)Subscribe to topics."""
        topics = {}

        @callback
        @log_messages(self.hass, self.entity_id)
        def state_message_received(msg):
            """Handle state MQTT message."""
            payload = json_loads(msg.payload)
            if STATE in payload and (
                payload[STATE] in POSSIBLE_STATES or payload[STATE] is None
            ):
                self._state = (
                    POSSIBLE_STATES[payload[STATE]] if payload[STATE] else None
                )
                del payload[STATE]
            self._state_attrs.update(payload)
            self.async_write_ha_state()

        if self._config.get(CONF_STATE_TOPIC):
            topics["state_position_topic"] = {
                "topic": self._config.get(CONF_STATE_TOPIC),
                "msg_callback": state_message_received,
                "qos": self._config[CONF_QOS],
                "encoding": self._config[CONF_ENCODING] or None,
            }
        self._sub_state = subscription.async_prepare_subscribe_topics(
            self.hass, self._sub_state, topics
        )

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""
        await subscription.async_subscribe_topics(self.hass, self._sub_state)

    @property
    def state(self):
        """Return state of vacuum."""
        return self._state

    @property
    def fan_speed(self):
        """Return fan speed of the vacuum."""
        return self._state_attrs.get(FAN_SPEED, 0)

    @property
    def fan_speed_list(self):
        """Return fan speed list of the vacuum."""
        return self._fan_speed_list

    @property
    def battery_level(self):
        """Return battery level of the vacuum."""
        return max(0, min(100, self._state_attrs.get(BATTERY, 0)))

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features

    async def async_start(self):
        """Start the vacuum."""
        if self.supported_features & VacuumEntityFeature.START == 0:
            return None
        await self.async_publish(
            self._command_topic,
            self._config[CONF_PAYLOAD_START],
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )

    async def async_pause(self):
        """Pause the vacuum."""
        if self.supported_features & VacuumEntityFeature.PAUSE == 0:
            return None
        await self.async_publish(
            self._command_topic,
            self._config[CONF_PAYLOAD_PAUSE],
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )

    async def async_stop(self, **kwargs):
        """Stop the vacuum."""
        if self.supported_features & VacuumEntityFeature.STOP == 0:
            return None
        await self.async_publish(
            self._command_topic,
            self._config[CONF_PAYLOAD_STOP],
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )

    async def async_set_fan_speed(self, fan_speed, **kwargs):
        """Set fan speed."""
        if (self.supported_features & VacuumEntityFeature.FAN_SPEED == 0) or (
            fan_speed not in self._fan_speed_list
        ):
            return None
        await self.async_publish(
            self._set_fan_speed_topic,
            fan_speed,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )

    async def async_return_to_base(self, **kwargs):
        """Tell the vacuum to return to its dock."""
        if self.supported_features & VacuumEntityFeature.RETURN_HOME == 0:
            return None
        await self.async_publish(
            self._command_topic,
            self._config[CONF_PAYLOAD_RETURN_TO_BASE],
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )

    async def async_clean_spot(self, **kwargs):
        """Perform a spot clean-up."""
        if self.supported_features & VacuumEntityFeature.CLEAN_SPOT == 0:
            return None
        await self.async_publish(
            self._command_topic,
            self._config[CONF_PAYLOAD_CLEAN_SPOT],
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )

    async def async_locate(self, **kwargs):
        """Locate the vacuum (usually by playing a song)."""
        if self.supported_features & VacuumEntityFeature.LOCATE == 0:
            return None
        await self.async_publish(
            self._command_topic,
            self._config[CONF_PAYLOAD_LOCATE],
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )

    async def async_send_command(self, command, params=None, **kwargs):
        """Send a command to a vacuum cleaner."""
        if self.supported_features & VacuumEntityFeature.SEND_COMMAND == 0:
            return None
        if params:
            message = {"command": command}
            message.update(params)
            message = json_dumps(message)
        else:
            message = command
        await self.async_publish(
            self._send_command_topic,
            message,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )
