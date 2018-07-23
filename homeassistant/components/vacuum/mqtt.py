"""
Support for a generic MQTT vacuum.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/vacuum.mqtt/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.components.mqtt import MqttAvailability
from homeassistant.components.vacuum import (
    SUPPORT_BATTERY, SUPPORT_CLEAN_SPOT, SUPPORT_FAN_SPEED,
    SUPPORT_LOCATE, SUPPORT_PAUSE, SUPPORT_RETURN_HOME, SUPPORT_SEND_COMMAND,
    SUPPORT_STATUS, SUPPORT_STOP, SUPPORT_TURN_OFF, SUPPORT_TURN_ON,
    VacuumDevice)
from homeassistant.const import ATTR_SUPPORTED_FEATURES, CONF_NAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.icon import icon_for_battery_level

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['mqtt']

SERVICE_TO_STRING = {
    SUPPORT_TURN_ON: 'turn_on',
    SUPPORT_TURN_OFF: 'turn_off',
    SUPPORT_PAUSE: 'pause',
    SUPPORT_STOP: 'stop',
    SUPPORT_RETURN_HOME: 'return_home',
    SUPPORT_FAN_SPEED: 'fan_speed',
    SUPPORT_BATTERY: 'battery',
    SUPPORT_STATUS: 'status',
    SUPPORT_SEND_COMMAND: 'send_command',
    SUPPORT_LOCATE: 'locate',
    SUPPORT_CLEAN_SPOT: 'clean_spot',
}

STRING_TO_SERVICE = {v: k for k, v in SERVICE_TO_STRING.items()}


def services_to_strings(services):
    """Convert SUPPORT_* service bitmask to list of service strings."""
    strings = []
    for service in SERVICE_TO_STRING:
        if service & services:
            strings.append(SERVICE_TO_STRING[service])
    return strings


def strings_to_services(strings):
    """Convert service strings to SUPPORT_* service bitmask."""
    services = 0
    for string in strings:
        services |= STRING_TO_SERVICE[string]
    return services


DEFAULT_SERVICES = SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_STOP |\
                   SUPPORT_RETURN_HOME | SUPPORT_STATUS | SUPPORT_BATTERY |\
                   SUPPORT_CLEAN_SPOT
ALL_SERVICES = DEFAULT_SERVICES | SUPPORT_PAUSE | SUPPORT_LOCATE |\
               SUPPORT_FAN_SPEED | SUPPORT_SEND_COMMAND

CONF_SUPPORTED_FEATURES = ATTR_SUPPORTED_FEATURES
CONF_PAYLOAD_TURN_ON = 'payload_turn_on'
CONF_PAYLOAD_TURN_OFF = 'payload_turn_off'
CONF_PAYLOAD_RETURN_TO_BASE = 'payload_return_to_base'
CONF_PAYLOAD_STOP = 'payload_stop'
CONF_PAYLOAD_CLEAN_SPOT = 'payload_clean_spot'
CONF_PAYLOAD_LOCATE = 'payload_locate'
CONF_PAYLOAD_START_PAUSE = 'payload_start_pause'
CONF_BATTERY_LEVEL_TOPIC = 'battery_level_topic'
CONF_BATTERY_LEVEL_TEMPLATE = 'battery_level_template'
CONF_CHARGING_TOPIC = 'charging_topic'
CONF_CHARGING_TEMPLATE = 'charging_template'
CONF_CLEANING_TOPIC = 'cleaning_topic'
CONF_CLEANING_TEMPLATE = 'cleaning_template'
CONF_DOCKED_TOPIC = 'docked_topic'
CONF_DOCKED_TEMPLATE = 'docked_template'
CONF_STATE_TOPIC = 'state_topic'
CONF_STATE_TEMPLATE = 'state_template'
CONF_FAN_SPEED_TOPIC = 'fan_speed_topic'
CONF_FAN_SPEED_TEMPLATE = 'fan_speed_template'
CONF_SET_FAN_SPEED_TOPIC = 'set_fan_speed_topic'
CONF_FAN_SPEED_LIST = 'fan_speed_list'
CONF_SEND_COMMAND_TOPIC = 'send_command_topic'

DEFAULT_NAME = 'MQTT Vacuum'
DEFAULT_RETAIN = False
DEFAULT_SERVICE_STRINGS = services_to_strings(DEFAULT_SERVICES)
DEFAULT_PAYLOAD_TURN_ON = 'turn_on'
DEFAULT_PAYLOAD_TURN_OFF = 'turn_off'
DEFAULT_PAYLOAD_RETURN_TO_BASE = 'return_to_base'
DEFAULT_PAYLOAD_STOP = 'stop'
DEFAULT_PAYLOAD_CLEAN_SPOT = 'clean_spot'
DEFAULT_PAYLOAD_LOCATE = 'locate'
DEFAULT_PAYLOAD_START_PAUSE = 'start_pause'

PLATFORM_SCHEMA = mqtt.MQTT_BASE_PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_SUPPORTED_FEATURES, default=DEFAULT_SERVICE_STRINGS):
        vol.All(cv.ensure_list, [vol.In(STRING_TO_SERVICE.keys())]),
    vol.Optional(mqtt.CONF_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
    vol.Optional(mqtt.CONF_COMMAND_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_PAYLOAD_TURN_ON,
                 default=DEFAULT_PAYLOAD_TURN_ON): cv.string,
    vol.Optional(CONF_PAYLOAD_TURN_OFF,
                 default=DEFAULT_PAYLOAD_TURN_OFF): cv.string,
    vol.Optional(CONF_PAYLOAD_RETURN_TO_BASE,
                 default=DEFAULT_PAYLOAD_RETURN_TO_BASE): cv.string,
    vol.Optional(CONF_PAYLOAD_STOP,
                 default=DEFAULT_PAYLOAD_STOP): cv.string,
    vol.Optional(CONF_PAYLOAD_CLEAN_SPOT,
                 default=DEFAULT_PAYLOAD_CLEAN_SPOT): cv.string,
    vol.Optional(CONF_PAYLOAD_LOCATE,
                 default=DEFAULT_PAYLOAD_LOCATE): cv.string,
    vol.Optional(CONF_PAYLOAD_START_PAUSE,
                 default=DEFAULT_PAYLOAD_START_PAUSE): cv.string,
    vol.Optional(CONF_BATTERY_LEVEL_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_BATTERY_LEVEL_TEMPLATE): cv.template,
    vol.Optional(CONF_CHARGING_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_CHARGING_TEMPLATE): cv.template,
    vol.Optional(CONF_CLEANING_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_CLEANING_TEMPLATE): cv.template,
    vol.Optional(CONF_DOCKED_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_DOCKED_TEMPLATE): cv.template,
    vol.Optional(CONF_STATE_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_STATE_TEMPLATE): cv.template,
    vol.Optional(CONF_FAN_SPEED_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_FAN_SPEED_TEMPLATE): cv.template,
    vol.Optional(CONF_SET_FAN_SPEED_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_FAN_SPEED_LIST, default=[]):
        vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_SEND_COMMAND_TOPIC): mqtt.valid_publish_topic,
}).extend(mqtt.MQTT_AVAILABILITY_SCHEMA.schema)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the vacuum."""
    name = config.get(CONF_NAME)
    supported_feature_strings = config.get(CONF_SUPPORTED_FEATURES)
    supported_features = strings_to_services(supported_feature_strings)

    qos = config.get(mqtt.CONF_QOS)
    retain = config.get(mqtt.CONF_RETAIN)

    command_topic = config.get(mqtt.CONF_COMMAND_TOPIC)
    payload_turn_on = config.get(CONF_PAYLOAD_TURN_ON)
    payload_turn_off = config.get(CONF_PAYLOAD_TURN_OFF)
    payload_return_to_base = config.get(CONF_PAYLOAD_RETURN_TO_BASE)
    payload_stop = config.get(CONF_PAYLOAD_STOP)
    payload_clean_spot = config.get(CONF_PAYLOAD_CLEAN_SPOT)
    payload_locate = config.get(CONF_PAYLOAD_LOCATE)
    payload_start_pause = config.get(CONF_PAYLOAD_START_PAUSE)

    battery_level_topic = config.get(CONF_BATTERY_LEVEL_TOPIC)
    battery_level_template = config.get(CONF_BATTERY_LEVEL_TEMPLATE)
    if battery_level_template:
        battery_level_template.hass = hass

    charging_topic = config.get(CONF_CHARGING_TOPIC)
    charging_template = config.get(CONF_CHARGING_TEMPLATE)
    if charging_template:
        charging_template.hass = hass

    cleaning_topic = config.get(CONF_CLEANING_TOPIC)
    cleaning_template = config.get(CONF_CLEANING_TEMPLATE)
    if cleaning_template:
        cleaning_template.hass = hass

    docked_topic = config.get(CONF_DOCKED_TOPIC)
    docked_template = config.get(CONF_DOCKED_TEMPLATE)
    if docked_template:
        docked_template.hass = hass

    fan_speed_topic = config.get(CONF_FAN_SPEED_TOPIC)
    fan_speed_template = config.get(CONF_FAN_SPEED_TEMPLATE)
    if fan_speed_template:
        fan_speed_template.hass = hass

    set_fan_speed_topic = config.get(CONF_SET_FAN_SPEED_TOPIC)
    fan_speed_list = config.get(CONF_FAN_SPEED_LIST)

    send_command_topic = config.get(CONF_SEND_COMMAND_TOPIC)

    availability_topic = config.get(mqtt.CONF_AVAILABILITY_TOPIC)
    payload_available = config.get(mqtt.CONF_PAYLOAD_AVAILABLE)
    payload_not_available = config.get(mqtt.CONF_PAYLOAD_NOT_AVAILABLE)

    async_add_devices([
        MqttVacuum(
            name, supported_features, qos, retain, command_topic,
            payload_turn_on, payload_turn_off, payload_return_to_base,
            payload_stop, payload_clean_spot, payload_locate,
            payload_start_pause, battery_level_topic, battery_level_template,
            charging_topic, charging_template, cleaning_topic,
            cleaning_template, docked_topic, docked_template, fan_speed_topic,
            fan_speed_template, set_fan_speed_topic, fan_speed_list,
            send_command_topic, availability_topic, payload_available,
            payload_not_available
        ),
    ])


class MqttVacuum(MqttAvailability, VacuumDevice):
    """Representation of a MQTT-controlled vacuum."""

    def __init__(
            self, name, supported_features, qos, retain, command_topic,
            payload_turn_on, payload_turn_off, payload_return_to_base,
            payload_stop, payload_clean_spot, payload_locate,
            payload_start_pause, battery_level_topic, battery_level_template,
            charging_topic, charging_template, cleaning_topic,
            cleaning_template, docked_topic, docked_template, fan_speed_topic,
            fan_speed_template, set_fan_speed_topic, fan_speed_list,
            send_command_topic, availability_topic, payload_available,
            payload_not_available):
        """Initialize the vacuum."""
        super().__init__(availability_topic, qos, payload_available,
                         payload_not_available)

        self._name = name
        self._supported_features = supported_features
        self._qos = qos
        self._retain = retain

        self._command_topic = command_topic
        self._payload_turn_on = payload_turn_on
        self._payload_turn_off = payload_turn_off
        self._payload_return_to_base = payload_return_to_base
        self._payload_stop = payload_stop
        self._payload_clean_spot = payload_clean_spot
        self._payload_locate = payload_locate
        self._payload_start_pause = payload_start_pause

        self._battery_level_topic = battery_level_topic
        self._battery_level_template = battery_level_template

        self._charging_topic = charging_topic
        self._charging_template = charging_template

        self._cleaning_topic = cleaning_topic
        self._cleaning_template = cleaning_template

        self._docked_topic = docked_topic
        self._docked_template = docked_template

        self._fan_speed_topic = fan_speed_topic
        self._fan_speed_template = fan_speed_template

        self._set_fan_speed_topic = set_fan_speed_topic
        self._fan_speed_list = fan_speed_list
        self._send_command_topic = send_command_topic

        self._cleaning = False
        self._charging = False
        self._docked = False
        self._status = 'Unknown'
        self._battery_level = 0
        self._fan_speed = 'unknown'

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Subscribe MQTT events."""
        yield from super().async_added_to_hass()

        @callback
        def message_received(topic, payload, qos):
            """Handle new MQTT message."""
            if topic == self._battery_level_topic and \
                    self._battery_level_template:
                battery_level = self._battery_level_template\
                    .async_render_with_possible_json_value(
                        payload,
                        error_value=None)
                if battery_level is not None:
                    self._battery_level = int(battery_level)

            if topic == self._charging_topic and self._charging_template:
                charging = self._charging_template\
                    .async_render_with_possible_json_value(
                        payload,
                        error_value=None)
                if charging is not None:
                    self._charging = cv.boolean(charging)

            if topic == self._cleaning_topic and self._cleaning_template:
                cleaning = self._cleaning_template \
                    .async_render_with_possible_json_value(
                        payload,
                        error_value=None)
                if cleaning is not None:
                    self._cleaning = cv.boolean(cleaning)

            if topic == self._docked_topic and self._docked_template:
                docked = self._docked_template \
                    .async_render_with_possible_json_value(
                        payload,
                        error_value=None)
                if docked is not None:
                    self._docked = cv.boolean(docked)

            if self._docked:
                if self._charging:
                    self._status = "Docked & Charging"
                else:
                    self._status = "Docked"
            elif self._cleaning:
                self._status = "Cleaning"
            else:
                self._status = "Stopped"

            if topic == self._fan_speed_topic and self._fan_speed_template:
                fan_speed = self._fan_speed_template\
                    .async_render_with_possible_json_value(
                        payload,
                        error_value=None)
                if fan_speed is not None:
                    self._fan_speed = fan_speed

            self.async_schedule_update_ha_state()

        topics_list = [topic for topic in (self._battery_level_topic,
                                           self._charging_topic,
                                           self._cleaning_topic,
                                           self._docked_topic,
                                           self._fan_speed_topic) if topic]
        for topic in set(topics_list):
            yield from self.hass.components.mqtt.async_subscribe(
                topic, message_received, self._qos)

    @property
    def name(self):
        """Return the name of the vacuum."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed for an MQTT vacuum."""
        return False

    @property
    def is_on(self):
        """Return true if vacuum is on."""
        return self._cleaning

    @property
    def status(self):
        """Return a status string for the vacuum."""
        if self.supported_features & SUPPORT_STATUS == 0:
            return

        return self._status

    @property
    def fan_speed(self):
        """Return the status of the vacuum."""
        if self.supported_features & SUPPORT_FAN_SPEED == 0:
            return

        return self._fan_speed

    @property
    def fan_speed_list(self):
        """Return the status of the vacuum."""
        if self.supported_features & SUPPORT_FAN_SPEED == 0:
            return []
        return self._fan_speed_list

    @property
    def battery_level(self):
        """Return the status of the vacuum."""
        if self.supported_features & SUPPORT_BATTERY == 0:
            return

        return max(0, min(100, self._battery_level))

    @property
    def battery_icon(self):
        """Return the battery icon for the vacuum cleaner."""
        if self.supported_features & SUPPORT_BATTERY == 0:
            return

        return icon_for_battery_level(
            battery_level=self.battery_level, charging=self._charging)

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn the vacuum on."""
        if self.supported_features & SUPPORT_TURN_ON == 0:
            return

        mqtt.async_publish(self.hass, self._command_topic,
                           self._payload_turn_on, self._qos, self._retain)
        self._status = 'Cleaning'
        self.async_schedule_update_ha_state()

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn the vacuum off."""
        if self.supported_features & SUPPORT_TURN_OFF == 0:
            return

        mqtt.async_publish(self.hass, self._command_topic,
                           self._payload_turn_off, self._qos, self._retain)
        self._status = 'Turning Off'
        self.async_schedule_update_ha_state()

    @asyncio.coroutine
    def async_stop(self, **kwargs):
        """Stop the vacuum."""
        if self.supported_features & SUPPORT_STOP == 0:
            return

        mqtt.async_publish(self.hass, self._command_topic, self._payload_stop,
                           self._qos, self._retain)
        self._status = 'Stopping the current task'
        self.async_schedule_update_ha_state()

    @asyncio.coroutine
    def async_clean_spot(self, **kwargs):
        """Perform a spot clean-up."""
        if self.supported_features & SUPPORT_CLEAN_SPOT == 0:
            return

        mqtt.async_publish(self.hass, self._command_topic,
                           self._payload_clean_spot, self._qos, self._retain)
        self._status = "Cleaning spot"
        self.async_schedule_update_ha_state()

    @asyncio.coroutine
    def async_locate(self, **kwargs):
        """Locate the vacuum (usually by playing a song)."""
        if self.supported_features & SUPPORT_LOCATE == 0:
            return

        mqtt.async_publish(self.hass, self._command_topic,
                           self._payload_locate, self._qos, self._retain)
        self._status = "Hi, I'm over here!"
        self.async_schedule_update_ha_state()

    @asyncio.coroutine
    def async_start_pause(self, **kwargs):
        """Start, pause or resume the cleaning task."""
        if self.supported_features & SUPPORT_PAUSE == 0:
            return

        mqtt.async_publish(self.hass, self._command_topic,
                           self._payload_start_pause, self._qos, self._retain)
        self._status = 'Pausing/Resuming cleaning...'
        self.async_schedule_update_ha_state()

    @asyncio.coroutine
    def async_return_to_base(self, **kwargs):
        """Tell the vacuum to return to its dock."""
        if self.supported_features & SUPPORT_RETURN_HOME == 0:
            return

        mqtt.async_publish(self.hass, self._command_topic,
                           self._payload_return_to_base, self._qos,
                           self._retain)
        self._status = 'Returning home...'
        self.async_schedule_update_ha_state()

    @asyncio.coroutine
    def async_set_fan_speed(self, fan_speed, **kwargs):
        """Set fan speed."""
        if self.supported_features & SUPPORT_FAN_SPEED == 0:
            return
        if not self._fan_speed_list or fan_speed not in self._fan_speed_list:
            return

        mqtt.async_publish(
            self.hass, self._set_fan_speed_topic, fan_speed, self._qos,
            self._retain)
        self._status = "Setting fan to {}...".format(fan_speed)
        self.async_schedule_update_ha_state()

    @asyncio.coroutine
    def async_send_command(self, command, params=None, **kwargs):
        """Send a command to a vacuum cleaner."""
        if self.supported_features & SUPPORT_SEND_COMMAND == 0:
            return

        mqtt.async_publish(
            self.hass, self._send_command_topic, command, self._qos,
            self._retain)
        self._status = "Sending command {}...".format(command)
        self.async_schedule_update_ha_state()
