"""Support for Legacy MQTT vacuum."""
import voluptuous as vol

from homeassistant.components.vacuum import (
    ATTR_STATUS,
    DOMAIN as VACUUM_DOMAIN,
    ENTITY_ID_FORMAT,
    VacuumEntity,
    VacuumEntityFeature,
)
from homeassistant.const import ATTR_SUPPORTED_FEATURES, CONF_NAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.helpers.json import json_dumps

from .. import subscription
from ..config import MQTT_BASE_SCHEMA
from ..const import CONF_COMMAND_TOPIC, CONF_ENCODING, CONF_QOS, CONF_RETAIN
from ..debug_info import log_messages
from ..mixins import MQTT_ENTITY_COMMON_SCHEMA, MqttEntity, warn_for_legacy_schema
from ..models import MqttValueTemplate
from ..util import get_mqtt_data, valid_publish_topic
from .const import MQTT_VACUUM_ATTRIBUTES_BLOCKED
from .schema import MQTT_VACUUM_SCHEMA, services_to_strings, strings_to_services

SERVICE_TO_STRING = {
    VacuumEntityFeature.TURN_ON: "turn_on",
    VacuumEntityFeature.TURN_OFF: "turn_off",
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
    VacuumEntityFeature.TURN_ON
    | VacuumEntityFeature.TURN_OFF
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

CONF_SUPPORTED_FEATURES = ATTR_SUPPORTED_FEATURES
CONF_BATTERY_LEVEL_TEMPLATE = "battery_level_template"
CONF_BATTERY_LEVEL_TOPIC = "battery_level_topic"
CONF_CHARGING_TEMPLATE = "charging_template"
CONF_CHARGING_TOPIC = "charging_topic"
CONF_CLEANING_TEMPLATE = "cleaning_template"
CONF_CLEANING_TOPIC = "cleaning_topic"
CONF_DOCKED_TEMPLATE = "docked_template"
CONF_DOCKED_TOPIC = "docked_topic"
CONF_ERROR_TEMPLATE = "error_template"
CONF_ERROR_TOPIC = "error_topic"
CONF_FAN_SPEED_LIST = "fan_speed_list"
CONF_FAN_SPEED_TEMPLATE = "fan_speed_template"
CONF_FAN_SPEED_TOPIC = "fan_speed_topic"
CONF_PAYLOAD_CLEAN_SPOT = "payload_clean_spot"
CONF_PAYLOAD_LOCATE = "payload_locate"
CONF_PAYLOAD_RETURN_TO_BASE = "payload_return_to_base"
CONF_PAYLOAD_START_PAUSE = "payload_start_pause"
CONF_PAYLOAD_STOP = "payload_stop"
CONF_PAYLOAD_TURN_OFF = "payload_turn_off"
CONF_PAYLOAD_TURN_ON = "payload_turn_on"
CONF_SEND_COMMAND_TOPIC = "send_command_topic"
CONF_SET_FAN_SPEED_TOPIC = "set_fan_speed_topic"

DEFAULT_NAME = "MQTT Vacuum"
DEFAULT_PAYLOAD_CLEAN_SPOT = "clean_spot"
DEFAULT_PAYLOAD_LOCATE = "locate"
DEFAULT_PAYLOAD_RETURN_TO_BASE = "return_to_base"
DEFAULT_PAYLOAD_START_PAUSE = "start_pause"
DEFAULT_PAYLOAD_STOP = "stop"
DEFAULT_PAYLOAD_TURN_OFF = "turn_off"
DEFAULT_PAYLOAD_TURN_ON = "turn_on"
DEFAULT_RETAIN = False
DEFAULT_SERVICE_STRINGS = services_to_strings(DEFAULT_SERVICES, SERVICE_TO_STRING)

MQTT_LEGACY_VACUUM_ATTRIBUTES_BLOCKED = MQTT_VACUUM_ATTRIBUTES_BLOCKED | frozenset(
    {ATTR_STATUS}
)

PLATFORM_SCHEMA_LEGACY_MODERN = (
    MQTT_BASE_SCHEMA.extend(
        {
            vol.Inclusive(CONF_BATTERY_LEVEL_TEMPLATE, "battery"): cv.template,
            vol.Inclusive(CONF_BATTERY_LEVEL_TOPIC, "battery"): valid_publish_topic,
            vol.Inclusive(CONF_CHARGING_TEMPLATE, "charging"): cv.template,
            vol.Inclusive(CONF_CHARGING_TOPIC, "charging"): valid_publish_topic,
            vol.Inclusive(CONF_CLEANING_TEMPLATE, "cleaning"): cv.template,
            vol.Inclusive(CONF_CLEANING_TOPIC, "cleaning"): valid_publish_topic,
            vol.Inclusive(CONF_DOCKED_TEMPLATE, "docked"): cv.template,
            vol.Inclusive(CONF_DOCKED_TOPIC, "docked"): valid_publish_topic,
            vol.Inclusive(CONF_ERROR_TEMPLATE, "error"): cv.template,
            vol.Inclusive(CONF_ERROR_TOPIC, "error"): valid_publish_topic,
            vol.Optional(CONF_FAN_SPEED_LIST, default=[]): vol.All(
                cv.ensure_list, [cv.string]
            ),
            vol.Inclusive(CONF_FAN_SPEED_TEMPLATE, "fan_speed"): cv.template,
            vol.Inclusive(CONF_FAN_SPEED_TOPIC, "fan_speed"): valid_publish_topic,
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
            vol.Optional(
                CONF_PAYLOAD_START_PAUSE, default=DEFAULT_PAYLOAD_START_PAUSE
            ): cv.string,
            vol.Optional(CONF_PAYLOAD_STOP, default=DEFAULT_PAYLOAD_STOP): cv.string,
            vol.Optional(
                CONF_PAYLOAD_TURN_OFF, default=DEFAULT_PAYLOAD_TURN_OFF
            ): cv.string,
            vol.Optional(
                CONF_PAYLOAD_TURN_ON, default=DEFAULT_PAYLOAD_TURN_ON
            ): cv.string,
            vol.Optional(CONF_SEND_COMMAND_TOPIC): valid_publish_topic,
            vol.Optional(CONF_SET_FAN_SPEED_TOPIC): valid_publish_topic,
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
PLATFORM_SCHEMA_LEGACY = vol.All(
    cv.PLATFORM_SCHEMA.extend(PLATFORM_SCHEMA_LEGACY_MODERN.schema),
    warn_for_legacy_schema(VACUUM_DOMAIN),
)

DISCOVERY_SCHEMA_LEGACY = PLATFORM_SCHEMA_LEGACY_MODERN.extend(
    {}, extra=vol.REMOVE_EXTRA
)


async def async_setup_entity_legacy(
    hass, config, async_add_entities, config_entry, discovery_data
):
    """Set up a MQTT Vacuum Legacy."""
    async_add_entities([MqttVacuum(hass, config, config_entry, discovery_data)])


class MqttVacuum(MqttEntity, VacuumEntity):
    """Representation of a MQTT-controlled legacy vacuum."""

    _entity_id_format = ENTITY_ID_FORMAT
    _attributes_extra_blocked = MQTT_LEGACY_VACUUM_ATTRIBUTES_BLOCKED

    def __init__(self, hass, config, config_entry, discovery_data):
        """Initialize the vacuum."""
        self._cleaning = False
        self._charging = False
        self._docked = False
        self._error = None
        self._status = "Unknown"
        self._battery_level = 0
        self._fan_speed = "unknown"
        self._fan_speed_list = []

        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema():
        """Return the config schema."""
        return DISCOVERY_SCHEMA_LEGACY

    def _setup_from_config(self, config):
        supported_feature_strings = config[CONF_SUPPORTED_FEATURES]
        self._supported_features = strings_to_services(
            supported_feature_strings, STRING_TO_SERVICE
        )
        self._fan_speed_list = config[CONF_FAN_SPEED_LIST]
        self._qos = config[CONF_QOS]
        self._retain = config[CONF_RETAIN]
        self._encoding = config[CONF_ENCODING] or None

        self._command_topic = config.get(CONF_COMMAND_TOPIC)
        self._set_fan_speed_topic = config.get(CONF_SET_FAN_SPEED_TOPIC)
        self._send_command_topic = config.get(CONF_SEND_COMMAND_TOPIC)

        self._payloads = {
            key: config.get(key)
            for key in (
                CONF_PAYLOAD_TURN_ON,
                CONF_PAYLOAD_TURN_OFF,
                CONF_PAYLOAD_RETURN_TO_BASE,
                CONF_PAYLOAD_STOP,
                CONF_PAYLOAD_CLEAN_SPOT,
                CONF_PAYLOAD_LOCATE,
                CONF_PAYLOAD_START_PAUSE,
            )
        }
        self._state_topics = {
            key: config.get(key)
            for key in (
                CONF_BATTERY_LEVEL_TOPIC,
                CONF_CHARGING_TOPIC,
                CONF_CLEANING_TOPIC,
                CONF_DOCKED_TOPIC,
                CONF_ERROR_TOPIC,
                CONF_FAN_SPEED_TOPIC,
            )
        }
        self._templates = {
            key: config.get(key)
            for key in (
                CONF_BATTERY_LEVEL_TEMPLATE,
                CONF_CHARGING_TEMPLATE,
                CONF_CLEANING_TEMPLATE,
                CONF_DOCKED_TEMPLATE,
                CONF_ERROR_TEMPLATE,
                CONF_FAN_SPEED_TEMPLATE,
            )
        }

    def _prepare_subscribe_topics(self):
        """(Re)Subscribe to topics."""
        for tpl in self._templates.values():
            if tpl is not None:
                tpl = MqttValueTemplate(tpl, entity=self)

        @callback
        @log_messages(self.hass, self.entity_id)
        def message_received(msg):
            """Handle new MQTT message."""
            if (
                msg.topic == self._state_topics[CONF_BATTERY_LEVEL_TOPIC]
                and self._templates[CONF_BATTERY_LEVEL_TEMPLATE]
            ):
                battery_level = self._templates[
                    CONF_BATTERY_LEVEL_TEMPLATE
                ].async_render_with_possible_json_value(msg.payload, None)
                if battery_level:
                    self._battery_level = int(battery_level)

            if (
                msg.topic == self._state_topics[CONF_CHARGING_TOPIC]
                and self._templates[CONF_CHARGING_TEMPLATE]
            ):
                charging = self._templates[
                    CONF_CHARGING_TEMPLATE
                ].async_render_with_possible_json_value(msg.payload, None)
                if charging:
                    self._charging = cv.boolean(charging)

            if (
                msg.topic == self._state_topics[CONF_CLEANING_TOPIC]
                and self._templates[CONF_CLEANING_TEMPLATE]
            ):
                cleaning = self._templates[
                    CONF_CLEANING_TEMPLATE
                ].async_render_with_possible_json_value(msg.payload, None)
                if cleaning:
                    self._cleaning = cv.boolean(cleaning)

            if (
                msg.topic == self._state_topics[CONF_DOCKED_TOPIC]
                and self._templates[CONF_DOCKED_TEMPLATE]
            ):
                docked = self._templates[
                    CONF_DOCKED_TEMPLATE
                ].async_render_with_possible_json_value(msg.payload, None)
                if docked:
                    self._docked = cv.boolean(docked)

            if (
                msg.topic == self._state_topics[CONF_ERROR_TOPIC]
                and self._templates[CONF_ERROR_TEMPLATE]
            ):
                error = self._templates[
                    CONF_ERROR_TEMPLATE
                ].async_render_with_possible_json_value(msg.payload, None)
                if error is not None:
                    self._error = cv.string(error)

            if self._docked:
                if self._charging:
                    self._status = "Docked & Charging"
                else:
                    self._status = "Docked"
            elif self._cleaning:
                self._status = "Cleaning"
            elif self._error:
                self._status = f"Error: {self._error}"
            else:
                self._status = "Stopped"

            if (
                msg.topic == self._state_topics[CONF_FAN_SPEED_TOPIC]
                and self._templates[CONF_FAN_SPEED_TEMPLATE]
            ):
                fan_speed = self._templates[
                    CONF_FAN_SPEED_TEMPLATE
                ].async_render_with_possible_json_value(msg.payload, None)
                if fan_speed:
                    self._fan_speed = fan_speed

            get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

        topics_list = {topic for topic in self._state_topics.values() if topic}
        self._sub_state = subscription.async_prepare_subscribe_topics(
            self.hass,
            self._sub_state,
            {
                f"topic{i}": {
                    "topic": topic,
                    "msg_callback": message_received,
                    "qos": self._qos,
                    "encoding": self._encoding,
                }
                for i, topic in enumerate(topics_list)
            },
        )

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""
        await subscription.async_subscribe_topics(self.hass, self._sub_state)

    @property
    def is_on(self):
        """Return true if vacuum is on."""
        return self._cleaning

    @property
    def status(self):
        """Return a status string for the vacuum."""
        return self._status

    @property
    def fan_speed(self):
        """Return the status of the vacuum."""
        return self._fan_speed

    @property
    def fan_speed_list(self):
        """Return the status of the vacuum."""
        return self._fan_speed_list

    @property
    def battery_level(self):
        """Return the status of the vacuum."""
        return max(0, min(100, self._battery_level))

    @property
    def battery_icon(self):
        """Return the battery icon for the vacuum cleaner.

        No need to check VacuumEntityFeature.BATTERY, this won't be called if battery_level is None.
        """
        return icon_for_battery_level(
            battery_level=self.battery_level, charging=self._charging
        )

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features

    async def async_turn_on(self, **kwargs):
        """Turn the vacuum on."""
        if self.supported_features & VacuumEntityFeature.TURN_ON == 0:
            return

        await self.async_publish(
            self._command_topic,
            self._payloads[CONF_PAYLOAD_TURN_ON],
            self._qos,
            self._retain,
            self._encoding,
        )
        self._status = "Cleaning"
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the vacuum off."""
        if self.supported_features & VacuumEntityFeature.TURN_OFF == 0:
            return None

        await self.async_publish(
            self._command_topic,
            self._payloads[CONF_PAYLOAD_TURN_OFF],
            self._qos,
            self._retain,
            self._encoding,
        )
        self._status = "Turning Off"
        self.async_write_ha_state()

    async def async_stop(self, **kwargs):
        """Stop the vacuum."""
        if self.supported_features & VacuumEntityFeature.STOP == 0:
            return None

        await self.async_publish(
            self._command_topic,
            self._payloads[CONF_PAYLOAD_STOP],
            self._qos,
            self._retain,
            self._encoding,
        )
        self._status = "Stopping the current task"
        self.async_write_ha_state()

    async def async_clean_spot(self, **kwargs):
        """Perform a spot clean-up."""
        if self.supported_features & VacuumEntityFeature.CLEAN_SPOT == 0:
            return None

        await self.async_publish(
            self._command_topic,
            self._payloads[CONF_PAYLOAD_CLEAN_SPOT],
            self._qos,
            self._retain,
            self._encoding,
        )
        self._status = "Cleaning spot"
        self.async_write_ha_state()

    async def async_locate(self, **kwargs):
        """Locate the vacuum (usually by playing a song)."""
        if self.supported_features & VacuumEntityFeature.LOCATE == 0:
            return None

        await self.async_publish(
            self._command_topic,
            self._payloads[CONF_PAYLOAD_LOCATE],
            self._qos,
            self._retain,
            self._encoding,
        )
        self._status = "Hi, I'm over here!"
        self.async_write_ha_state()

    async def async_start_pause(self, **kwargs):
        """Start, pause or resume the cleaning task."""
        if self.supported_features & VacuumEntityFeature.PAUSE == 0:
            return None

        await self.async_publish(
            self._command_topic,
            self._payloads[CONF_PAYLOAD_START_PAUSE],
            self._qos,
            self._retain,
            self._encoding,
        )
        self._status = "Pausing/Resuming cleaning..."
        self.async_write_ha_state()

    async def async_return_to_base(self, **kwargs):
        """Tell the vacuum to return to its dock."""
        if self.supported_features & VacuumEntityFeature.RETURN_HOME == 0:
            return None

        await self.async_publish(
            self._command_topic,
            self._payloads[CONF_PAYLOAD_RETURN_TO_BASE],
            self._qos,
            self._retain,
            self._encoding,
        )
        self._status = "Returning home..."
        self.async_write_ha_state()

    async def async_set_fan_speed(self, fan_speed, **kwargs):
        """Set fan speed."""
        if (
            self.supported_features & VacuumEntityFeature.FAN_SPEED == 0
        ) or fan_speed not in self._fan_speed_list:
            return None

        await self.async_publish(
            self._set_fan_speed_topic,
            fan_speed,
            self._qos,
            self._retain,
            self._encoding,
        )
        self._status = f"Setting fan to {fan_speed}..."
        self.async_write_ha_state()

    async def async_send_command(self, command, params=None, **kwargs):
        """Send a command to a vacuum cleaner."""
        if self.supported_features & VacuumEntityFeature.SEND_COMMAND == 0:
            return
        if params:
            message = {"command": command}
            message.update(params)
            message = json_dumps(message)
        else:
            message = command
        await self.async_publish(
            self._send_command_topic,
            message,
            self._qos,
            self._retain,
            self._encoding,
        )
        self._status = f"Sending command {message}..."
        self.async_write_ha_state()
