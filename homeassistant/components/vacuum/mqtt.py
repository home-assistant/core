"""
Support for a generic MQTT vacuum.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/vacuum/
"""
import asyncio
import json
import logging

import voluptuous as vol

import homeassistant.components.mqtt as mqtt
import homeassistant.helpers.config_validation as cv
from homeassistant.components.vacuum import (
    DEFAULT_ICON, SUPPORT_BATTERY, SUPPORT_CLEAN_SPOT,
    SUPPORT_LOCATE, SUPPORT_PAUSE, SUPPORT_RETURN_HOME,
    SUPPORT_STATUS, SUPPORT_STOP, SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON, VacuumDevice, services_to_strings, strings_to_services)
from homeassistant.const import CONF_NAME, ATTR_SUPPORTED_FEATURES,\
    ATTR_BATTERY_LEVEL, ATTR_STATE
from homeassistant.core import callback

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['mqtt']

DEFAULT_SERVICES = SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_STOP |\
                   SUPPORT_RETURN_HOME | SUPPORT_STATUS | SUPPORT_BATTERY |\
                   SUPPORT_CLEAN_SPOT
ALL_SERVICES = DEFAULT_SERVICES | SUPPORT_PAUSE | SUPPORT_LOCATE
DEFAULT_SERVICE_STRINGS = services_to_strings(DEFAULT_SERVICES)

DEFAULT_COMMAND_TOPIC = 'vacuum/command'
DEFAULT_STATE_TOPIC = 'vacuum/state'

DEFAULT_NAME = 'MQTT Vacuum'

PLATFORM_SCHEMA = mqtt.MQTT_BASE_PLATFORM_SCHEMA.extend({
    vol.Optional(ATTR_SUPPORTED_FEATURES, default=DEFAULT_SERVICE_STRINGS):
        vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(mqtt.CONF_COMMAND_TOPIC, default=DEFAULT_COMMAND_TOPIC):
        mqtt.valid_publish_topic,
    vol.Optional(mqtt.CONF_STATE_TOPIC, default=DEFAULT_STATE_TOPIC):
        mqtt.valid_publish_topic,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the vacuum."""
    name = config.get(CONF_NAME)
    command_topic = config.get(mqtt.CONF_COMMAND_TOPIC)
    state_topic = config.get(mqtt.CONF_STATE_TOPIC)
    supported_feature_strings = config.get(ATTR_SUPPORTED_FEATURES)
    supported_features = strings_to_services(supported_feature_strings)
    qos = config.get(mqtt.CONF_QOS)
    state_template = cv.template('{{value_json.battery_level}}')
    state_template.hass = hass

    add_devices([
        MqttVacuum(name, supported_features, command_topic, state_topic, qos,
                   state_template),
    ])


class MqttVacuum(VacuumDevice):
    """Representation of a MQTT-controlled vacuum."""

    # pylint: disable=no-self-use
    def __init__(self, name, supported_features, command_topic, state_topic,
                 qos, state_template):
        """Initialize the vacuum."""
        self._name = name
        self._command_topic = command_topic
        self._state_topic = state_topic
        self._supported_features = supported_features
        self._qos = qos

        self._payload_turn_on = "turn_on"
        self._payload_turn_off = "turn_off"
        self._payload_return_to_base = "return_to_base"
        self._payload_stop = "stop"
        self._payload_clean_spot = "clean_spot"
        self._payload_locate = "locate"
        self._payload_start_pause = "start_pause"
        self._retain = False

        self._state_template = state_template

        self._state = False
        self._status = 'Unknown'
        self._battery_level = 0

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Subscribe MQTT events.

        This method is a coroutine.
        """
        @callback
        def message_received(topic, payload, qos):
            """Handle new MQTT message."""
            try:
                payload = json.loads(payload)
            except ValueError:  # e.g. json.decoder.JSONDecodeError:
                _LOGGER.warning("JSONDecodeError in vacuum.mqtt payload: %s",
                                payload)
                return

            battery_level = payload.get(ATTR_BATTERY_LEVEL)
            if battery_level is not None:
                self._battery_level = int(battery_level)

            charging = payload.get("charging")
            state = payload.get(ATTR_STATE)
            if payload[ATTR_STATE]:
                if state == "cleaning":
                    self._state = True
                    self._status = "Cleaning"
                if state == "docked":
                    self._state = False
                    if charging:
                        self._status = "Docked & Charging"
                    else:
                        self._status = "Docked"
                if state == "stopped":
                    self._state = False
                    self._status = "Stopped"

            self.hass.async_add_job(self.async_update_ha_state())

        yield from mqtt.async_subscribe(
            self.hass, self._state_topic, message_received, self._qos)

    @property
    def name(self):
        """Return the name of the vacuum."""
        return self._name

    @property
    def icon(self):
        """Return the icon for the vacuum."""
        return DEFAULT_ICON

    @property
    def should_poll(self):
        """No polling needed for an MQTT vacuum."""
        return False

    @property
    def is_on(self):
        """Return true if vacuum is on."""
        return self._state

    @property
    def status(self):
        """Return the status of the vacuum."""
        if self.supported_features & SUPPORT_STATUS == 0:
            return

        return self._status

    @property
    def battery_level(self):
        """Return the status of the vacuum."""
        if self.supported_features & SUPPORT_BATTERY == 0:
            return

        return max(0, min(100, self._battery_level))

    @property
    def device_state_attributes(self):
        """Return device state attributes."""
        return {}

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features

    def turn_on(self, **kwargs):
        """Turn the vacuum on."""
        if self.supported_features & SUPPORT_TURN_ON == 0:
            return

        mqtt.async_publish(self.hass, self._command_topic,
                           self._payload_turn_on, self._qos, self._retain)
        self._status = 'Cleaning'
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the vacuum off."""
        if self.supported_features & SUPPORT_TURN_OFF == 0:
            return

        mqtt.async_publish(self.hass, self._command_topic,
                           self._payload_turn_off, self._qos, self._retain)
        self._status = 'Turning Off'
        self.schedule_update_ha_state()

    def stop(self, **kwargs):
        """Turn the vacuum off."""
        if self.supported_features & SUPPORT_STOP == 0:
            return

        mqtt.async_publish(self.hass, self._command_topic, self._payload_stop,
                           self._qos, self._retain)
        self._status = 'Stopping the current task'
        self.schedule_update_ha_state()

    def clean_spot(self, **kwargs):
        """Perform a spot clean-up."""
        if self.supported_features & SUPPORT_CLEAN_SPOT == 0:
            return

        mqtt.async_publish(self.hass, self._command_topic,
                           self._payload_clean_spot, self._qos, self._retain)
        self._status = "Cleaning spot"
        self.schedule_update_ha_state()

    def locate(self, **kwargs):
        """Turn the vacuum off."""
        if self.supported_features & SUPPORT_LOCATE == 0:
            return

        mqtt.async_publish(self.hass, self._command_topic,
                           self._payload_locate, self._qos, self._retain)
        self._status = "Hi, I'm over here!"
        self.schedule_update_ha_state()

    def start_pause(self, **kwargs):
        """Start, pause or resume the cleaning task."""
        if self.supported_features & SUPPORT_PAUSE == 0:
            return

        mqtt.async_publish(self.hass, self._command_topic,
                           self._payload_start_pause, self._qos, self._retain)
        self._status = 'Pausing/Resuming cleaning...'
        self.schedule_update_ha_state()

    def return_to_base(self, **kwargs):
        """Tell the vacuum to return to its dock."""
        if self.supported_features & SUPPORT_RETURN_HOME == 0:
            return

        mqtt.async_publish(self.hass, self._command_topic,
                           self._payload_return_to_base, self._qos,
                           self._retain)
        self._status = 'Returning home...'
        self.schedule_update_ha_state()
