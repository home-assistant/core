"""Support for a State MQTT vacuum."""
import json
import logging

import voluptuous as vol

from homeassistant.components import mqtt
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
from homeassistant.components.vacuum import (
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_ERROR,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RETURNING,
    SUPPORT_BATTERY,
    SUPPORT_CLEAN_SPOT,
    SUPPORT_FAN_SPEED,
    SUPPORT_LOCATE,
    SUPPORT_PAUSE,
    SUPPORT_RETURN_HOME,
    SUPPORT_SEND_COMMAND,
    SUPPORT_START,
    SUPPORT_STATUS,
    SUPPORT_STOP,
    StateVacuumDevice,
)
from homeassistant.const import ATTR_SUPPORTED_FEATURES, CONF_DEVICE, CONF_NAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from ..debug_info import log_messages
from .schema import MQTT_VACUUM_SCHEMA, services_to_strings, strings_to_services

_LOGGER = logging.getLogger(__name__)

SERVICE_TO_STRING = {
    SUPPORT_START: "start",
    SUPPORT_PAUSE: "pause",
    SUPPORT_STOP: "stop",
    SUPPORT_RETURN_HOME: "return_home",
    SUPPORT_FAN_SPEED: "fan_speed",
    SUPPORT_BATTERY: "battery",
    SUPPORT_STATUS: "status",
    SUPPORT_SEND_COMMAND: "send_command",
    SUPPORT_LOCATE: "locate",
    SUPPORT_CLEAN_SPOT: "clean_spot",
}

STRING_TO_SERVICE = {v: k for k, v in SERVICE_TO_STRING.items()}


DEFAULT_SERVICES = (
    SUPPORT_START
    | SUPPORT_STOP
    | SUPPORT_RETURN_HOME
    | SUPPORT_STATUS
    | SUPPORT_BATTERY
    | SUPPORT_CLEAN_SPOT
)
ALL_SERVICES = (
    DEFAULT_SERVICES
    | SUPPORT_PAUSE
    | SUPPORT_LOCATE
    | SUPPORT_FAN_SPEED
    | SUPPORT_SEND_COMMAND
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

PLATFORM_SCHEMA_STATE = (
    mqtt.MQTT_BASE_PLATFORM_SCHEMA.extend(
        {
            vol.Optional(CONF_DEVICE): mqtt.MQTT_ENTITY_DEVICE_INFO_SCHEMA,
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
            vol.Optional(CONF_SEND_COMMAND_TOPIC): mqtt.valid_publish_topic,
            vol.Optional(CONF_SET_FAN_SPEED_TOPIC): mqtt.valid_publish_topic,
            vol.Optional(CONF_STATE_TOPIC): mqtt.valid_publish_topic,
            vol.Optional(
                CONF_SUPPORTED_FEATURES, default=DEFAULT_SERVICE_STRINGS
            ): vol.All(cv.ensure_list, [vol.In(STRING_TO_SERVICE.keys())]),
            vol.Optional(CONF_UNIQUE_ID): cv.string,
            vol.Optional(CONF_COMMAND_TOPIC): mqtt.valid_publish_topic,
            vol.Optional(CONF_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
        }
    )
    .extend(mqtt.MQTT_AVAILABILITY_SCHEMA.schema)
    .extend(mqtt.MQTT_JSON_ATTRS_SCHEMA.schema)
    .extend(MQTT_VACUUM_SCHEMA.schema)
)


async def async_setup_entity_state(
    config, async_add_entities, config_entry, discovery_data
):
    """Set up a State MQTT Vacuum."""
    async_add_entities([MqttStateVacuum(config, config_entry, discovery_data)])


class MqttStateVacuum(
    MqttAttributes,
    MqttAvailability,
    MqttDiscoveryUpdate,
    MqttEntityDeviceInfo,
    StateVacuumDevice,
):
    """Representation of a MQTT-controlled state vacuum."""

    def __init__(self, config, config_entry, discovery_info):
        """Initialize the vacuum."""
        self._state = None
        self._state_attrs = {}
        self._fan_speed_list = []
        self._sub_state = None
        self._unique_id = config.get(CONF_UNIQUE_ID)

        # Load config
        self._setup_from_config(config)

        device_config = config.get(CONF_DEVICE)

        MqttAttributes.__init__(self, config)
        MqttAvailability.__init__(self, config)
        MqttDiscoveryUpdate.__init__(self, discovery_info, self.discovery_update)
        MqttEntityDeviceInfo.__init__(self, device_config, config_entry)

    def _setup_from_config(self, config):
        self._config = config
        self._name = config[CONF_NAME]
        supported_feature_strings = config[CONF_SUPPORTED_FEATURES]
        self._supported_features = strings_to_services(
            supported_feature_strings, STRING_TO_SERVICE
        )
        self._fan_speed_list = config[CONF_FAN_SPEED_LIST]
        self._command_topic = config.get(mqtt.CONF_COMMAND_TOPIC)
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

    async def discovery_update(self, discovery_payload):
        """Handle updated discovery message."""
        config = PLATFORM_SCHEMA_STATE(discovery_payload)
        self._setup_from_config(config)
        await self.attributes_discovery_update(config)
        await self.availability_discovery_update(config)
        await self.device_info_discovery_update(config)
        await self._subscribe_topics()
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Subscribe MQTT events."""
        await super().async_added_to_hass()
        await self._subscribe_topics()

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        self._sub_state = await subscription.async_unsubscribe_topics(
            self.hass, self._sub_state
        )
        await MqttAttributes.async_will_remove_from_hass(self)
        await MqttAvailability.async_will_remove_from_hass(self)
        await MqttDiscoveryUpdate.async_will_remove_from_hass(self)

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""
        topics = {}

        @callback
        @log_messages(self.hass, self.entity_id)
        def state_message_received(msg):
            """Handle state MQTT message."""
            payload = json.loads(msg.payload)
            if STATE in payload and payload[STATE] in POSSIBLE_STATES:
                self._state = POSSIBLE_STATES[payload[STATE]]
                del payload[STATE]
            self._state_attrs.update(payload)
            self.async_write_ha_state()

        if self._config.get(CONF_STATE_TOPIC):
            topics["state_position_topic"] = {
                "topic": self._config.get(CONF_STATE_TOPIC),
                "msg_callback": state_message_received,
                "qos": self._config[CONF_QOS],
            }
        self._sub_state = await subscription.async_subscribe_topics(
            self.hass, self._sub_state, topics
        )

    @property
    def name(self):
        """Return the name of the vacuum."""
        return self._name

    @property
    def state(self):
        """Return state of vacuum."""
        return self._state

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def fan_speed(self):
        """Return fan speed of the vacuum."""
        if self.supported_features & SUPPORT_FAN_SPEED == 0:
            return None

        return self._state_attrs.get(FAN_SPEED, 0)

    @property
    def fan_speed_list(self):
        """Return fan speed list of the vacuum."""
        if self.supported_features & SUPPORT_FAN_SPEED == 0:
            return None
        return self._fan_speed_list

    @property
    def battery_level(self):
        """Return battery level of the vacuum."""
        if self.supported_features & SUPPORT_BATTERY == 0:
            return None
        return max(0, min(100, self._state_attrs.get(BATTERY, 0)))

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features

    async def async_start(self):
        """Start the vacuum."""
        if self.supported_features & SUPPORT_START == 0:
            return None
        mqtt.async_publish(
            self.hass,
            self._command_topic,
            self._config[CONF_PAYLOAD_START],
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )

    async def async_pause(self):
        """Pause the vacuum."""
        if self.supported_features & SUPPORT_PAUSE == 0:
            return None
        mqtt.async_publish(
            self.hass,
            self._command_topic,
            self._config[CONF_PAYLOAD_PAUSE],
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )

    async def async_stop(self, **kwargs):
        """Stop the vacuum."""
        if self.supported_features & SUPPORT_STOP == 0:
            return None
        mqtt.async_publish(
            self.hass,
            self._command_topic,
            self._config[CONF_PAYLOAD_STOP],
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )

    async def async_set_fan_speed(self, fan_speed, **kwargs):
        """Set fan speed."""
        if (self.supported_features & SUPPORT_FAN_SPEED == 0) or (
            fan_speed not in self._fan_speed_list
        ):
            return None
        mqtt.async_publish(
            self.hass,
            self._set_fan_speed_topic,
            fan_speed,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )

    async def async_return_to_base(self, **kwargs):
        """Tell the vacuum to return to its dock."""
        if self.supported_features & SUPPORT_RETURN_HOME == 0:
            return None
        mqtt.async_publish(
            self.hass,
            self._command_topic,
            self._config[CONF_PAYLOAD_RETURN_TO_BASE],
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )

    async def async_clean_spot(self, **kwargs):
        """Perform a spot clean-up."""
        if self.supported_features & SUPPORT_CLEAN_SPOT == 0:
            return None
        mqtt.async_publish(
            self.hass,
            self._command_topic,
            self._config[CONF_PAYLOAD_CLEAN_SPOT],
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )

    async def async_locate(self, **kwargs):
        """Locate the vacuum (usually by playing a song)."""
        if self.supported_features & SUPPORT_LOCATE == 0:
            return None
        mqtt.async_publish(
            self.hass,
            self._command_topic,
            self._config[CONF_PAYLOAD_LOCATE],
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )

    async def async_send_command(self, command, params=None, **kwargs):
        """Send a command to a vacuum cleaner."""
        if self.supported_features & SUPPORT_SEND_COMMAND == 0:
            return None
        if params:
            message = {"command": command}
            message.update(params)
            message = json.dumps(message)
        else:
            message = command
        mqtt.async_publish(
            self.hass,
            self._send_command_topic,
            message,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )
