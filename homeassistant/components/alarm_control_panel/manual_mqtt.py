"""
Support for manual alarms controllable via MQTT.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.manual_mqtt/
"""
import asyncio
import logging

import homeassistant.components.mqtt as mqtt
from homeassistant.components.alarm_control_panel import (
    manual as manual_alarm, mqtt as mqtt_alarm)
from homeassistant.components.alarm_control_panel.mqtt import (
    CONF_PAYLOAD_DISARM, CONF_PAYLOAD_ARM_HOME, CONF_PAYLOAD_ARM_AWAY)
from homeassistant.const import (
    STATE_UNKNOWN, CONF_NAME, CONF_CODE,
    CONF_PENDING_TIME, CONF_TRIGGER_TIME, CONF_DISARM_AFTER_TRIGGER)
from homeassistant.helpers.event import async_track_state_change
from homeassistant.core import callback

DEFAULT_ALARM_NAME = 'HA Alarm'
DEFAULT_PENDING_TIME = 60
DEFAULT_TRIGGER_TIME = 120
DEFAULT_DISARM_AFTER_TRIGGER = False

PLATFORM_SCHEMA = manual_alarm.PLATFORM_SCHEMA.extend(
    mqtt_alarm.PLATFORM_SCHEMA.schema)

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the manual alarm platform."""
    add_devices([ManualMQTTAlarm(
        hass,
        config[CONF_NAME],
        config.get(CONF_CODE),
        config.get(CONF_PENDING_TIME, DEFAULT_PENDING_TIME),
        config.get(CONF_TRIGGER_TIME, DEFAULT_TRIGGER_TIME),
        config.get(CONF_DISARM_AFTER_TRIGGER, DEFAULT_DISARM_AFTER_TRIGGER),
        config.get(mqtt.CONF_STATE_TOPIC),
        config.get(mqtt.CONF_COMMAND_TOPIC),
        config.get(mqtt.CONF_QOS),
        config.get(CONF_PAYLOAD_DISARM),
        config.get(CONF_PAYLOAD_ARM_HOME),
        config.get(CONF_PAYLOAD_ARM_AWAY))])


class ManualMQTTAlarm(manual_alarm.ManualAlarm):
    """
    Representation of an alarm status.

    When armed, will be pending for 'pending_time', after that armed.
    When triggered, will be pending for 'trigger_time'. After that will be
    triggered for 'trigger_time', after that we return to the previous state
    or disarm if `disarm_after_trigger` is true.
    """

    def __init__(self, hass, name, code, pending_time,
                 trigger_time, disarm_after_trigger,
                 state_topic, command_topic, qos,
                 payload_disarm, payload_arm_home, payload_arm_away):
        """Init the manual MQTT alarm panel."""
        super().__init__(hass, name, code, pending_time, trigger_time,
                         disarm_after_trigger)

        self._state = STATE_UNKNOWN
        self._state_topic = state_topic
        self._command_topic = command_topic
        self._qos = qos
        self._payload_disarm = payload_disarm
        self._payload_arm_home = payload_arm_home
        self._payload_arm_away = payload_arm_away

    def async_added_to_hass(self):
        """Subscribe mqtt events.

        This method must be run in the event loop and returns a coroutine.
        """
        async_track_state_change(
            self.hass, self.entity_id, self._async_state_changed_listener
        )

        @callback
        def message_received(topic, payload, qos):
            """Run when new MQTT message has been received."""
            if payload == self._payload_disarm:
                self.async_alarm_disarm(self._code)
            elif payload == self._payload_arm_home:
                self.async_alarm_arm_home(self._code)
            elif payload == self._payload_arm_away:
                self.async_alarm_arm_away(self._code)
            else:
                _LOGGER.warning("Received unexpected payload: %s", payload)
                return

        return mqtt.async_subscribe(
            self.hass, self._command_topic, message_received, self._qos)

    @asyncio.coroutine
    def _async_state_changed_listener(self, entity_id, old_state, new_state):
        """Publish state change to MQTT."""
        mqtt.async_publish(self.hass, self._state_topic, new_state.state,
                           self._qos, True)
