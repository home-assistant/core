"""
This platform enables the possibility to control a MQTT alarm.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.mqtt/
"""
import logging
import re

import voluptuous as vol

from homeassistant.core import callback
import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components import mqtt
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING, STATE_ALARM_TRIGGERED, STATE_UNKNOWN,
    CONF_NAME, CONF_CODE)
from homeassistant.components.mqtt import (
    ATTR_DISCOVERY_HASH, CONF_AVAILABILITY_TOPIC, CONF_STATE_TOPIC,
    CONF_COMMAND_TOPIC, CONF_PAYLOAD_AVAILABLE, CONF_PAYLOAD_NOT_AVAILABLE,
    CONF_QOS, CONF_RETAIN, MqttAvailability, MqttDiscoveryUpdate)
from homeassistant.components.mqtt.discovery import MQTT_DISCOVERY_NEW
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import HomeAssistantType, ConfigType

_LOGGER = logging.getLogger(__name__)

CONF_PAYLOAD_DISARM = 'payload_disarm'
CONF_PAYLOAD_ARM_HOME = 'payload_arm_home'
CONF_PAYLOAD_ARM_AWAY = 'payload_arm_away'

DEFAULT_ARM_AWAY = 'ARM_AWAY'
DEFAULT_ARM_HOME = 'ARM_HOME'
DEFAULT_DISARM = 'DISARM'
DEFAULT_NAME = 'MQTT Alarm'
DEPENDENCIES = ['mqtt']

PLATFORM_SCHEMA = mqtt.MQTT_BASE_PLATFORM_SCHEMA.extend({
    vol.Required(CONF_COMMAND_TOPIC): mqtt.valid_publish_topic,
    vol.Required(CONF_STATE_TOPIC): mqtt.valid_subscribe_topic,
    vol.Optional(CONF_CODE): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PAYLOAD_ARM_AWAY, default=DEFAULT_ARM_AWAY): cv.string,
    vol.Optional(CONF_PAYLOAD_ARM_HOME, default=DEFAULT_ARM_HOME): cv.string,
    vol.Optional(CONF_PAYLOAD_DISARM, default=DEFAULT_DISARM): cv.string,
}).extend(mqtt.MQTT_AVAILABILITY_SCHEMA.schema)


async def async_setup_platform(hass: HomeAssistantType, config: ConfigType,
                               async_add_entities, discovery_info=None):
    """Set up MQTT alarm control panel through configuration.yaml."""
    await _async_setup_entity(hass, config, async_add_entities)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MQTT alarm control panel dynamically through MQTT discovery."""
    async def async_discover(discovery_payload):
        """Discover and add an MQTT alarm control panel."""
        config = PLATFORM_SCHEMA(discovery_payload)
        await _async_setup_entity(hass, config, async_add_entities,
                                  discovery_payload[ATTR_DISCOVERY_HASH])

    async_dispatcher_connect(
        hass, MQTT_DISCOVERY_NEW.format(alarm.DOMAIN, 'mqtt'),
        async_discover)


async def _async_setup_entity(hass, config, async_add_entities,
                              discovery_hash=None):
    """Set up the MQTT Alarm Control Panel platform."""
    async_add_entities([MqttAlarm(
        config.get(CONF_NAME),
        config.get(CONF_STATE_TOPIC),
        config.get(CONF_COMMAND_TOPIC),
        config.get(CONF_QOS),
        config.get(CONF_RETAIN),
        config.get(CONF_PAYLOAD_DISARM),
        config.get(CONF_PAYLOAD_ARM_HOME),
        config.get(CONF_PAYLOAD_ARM_AWAY),
        config.get(CONF_CODE),
        config.get(CONF_AVAILABILITY_TOPIC),
        config.get(CONF_PAYLOAD_AVAILABLE),
        config.get(CONF_PAYLOAD_NOT_AVAILABLE),
        discovery_hash,)])


class MqttAlarm(MqttAvailability, MqttDiscoveryUpdate,
                alarm.AlarmControlPanel):
    """Representation of a MQTT alarm status."""

    def __init__(self, name, state_topic, command_topic, qos, retain,
                 payload_disarm, payload_arm_home, payload_arm_away, code,
                 availability_topic, payload_available, payload_not_available,
                 discovery_hash):
        """Init the MQTT Alarm Control Panel."""
        MqttAvailability.__init__(self, availability_topic, qos,
                                  payload_available, payload_not_available)
        MqttDiscoveryUpdate.__init__(self, discovery_hash)
        self._state = STATE_UNKNOWN
        self._name = name
        self._state_topic = state_topic
        self._command_topic = command_topic
        self._qos = qos
        self._retain = retain
        self._payload_disarm = payload_disarm
        self._payload_arm_home = payload_arm_home
        self._payload_arm_away = payload_arm_away
        self._code = code
        self._discovery_hash = discovery_hash

    async def async_added_to_hass(self):
        """Subscribe mqtt events."""
        await MqttAvailability.async_added_to_hass(self)
        await MqttDiscoveryUpdate.async_added_to_hass(self)

        @callback
        def message_received(topic, payload, qos):
            """Run when new MQTT message has been received."""
            if payload not in (STATE_ALARM_DISARMED, STATE_ALARM_ARMED_HOME,
                               STATE_ALARM_ARMED_AWAY, STATE_ALARM_PENDING,
                               STATE_ALARM_TRIGGERED):
                _LOGGER.warning("Received unexpected payload: %s", payload)
                return
            self._state = payload
            self.async_schedule_update_ha_state()

        await mqtt.async_subscribe(
            self.hass, self._state_topic, message_received, self._qos)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def code_format(self):
        """Return one or more digits/characters."""
        if self._code is None:
            return None
        if isinstance(self._code, str) and re.search('^\\d+$', self._code):
            return 'Number'
        return 'Any'

    async def async_alarm_disarm(self, code=None):
        """Send disarm command.

        This method is a coroutine.
        """
        if not self._validate_code(code, 'disarming'):
            return
        mqtt.async_publish(
            self.hass, self._command_topic, self._payload_disarm, self._qos,
            self._retain)

    async def async_alarm_arm_home(self, code=None):
        """Send arm home command.

        This method is a coroutine.
        """
        if not self._validate_code(code, 'arming home'):
            return
        mqtt.async_publish(
            self.hass, self._command_topic, self._payload_arm_home, self._qos,
            self._retain)

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command.

        This method is a coroutine.
        """
        if not self._validate_code(code, 'arming away'):
            return
        mqtt.async_publish(
            self.hass, self._command_topic, self._payload_arm_away, self._qos,
            self._retain)

    def _validate_code(self, code, state):
        """Validate given code."""
        check = self._code is None or code == self._code
        if not check:
            _LOGGER.warning('Wrong code entered for %s', state)
        return check
