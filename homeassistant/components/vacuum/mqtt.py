"""
Support for a generic MQTT vacuum.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/vacuum.mqtt/
"""
import asyncio
import logging

import voluptuous as vol

import homeassistant.components.mqtt as mqtt
import homeassistant.helpers.config_validation as cv
from homeassistant.components.vacuum import (
    DEFAULT_ICON, services_to_strings, strings_to_services, SUPPORT_BATTERY,
    SUPPORT_CLEAN_SPOT, SUPPORT_LOCATE, SUPPORT_PAUSE, SUPPORT_RETURN_HOME,
    SUPPORT_STATUS, SUPPORT_STOP, SUPPORT_TURN_OFF, SUPPORT_TURN_ON,
    VacuumDevice, STRING_TO_SERVICE)
from homeassistant.const import ATTR_SUPPORTED_FEATURES, CONF_NAME
from homeassistant.core import callback

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['mqtt']

DEFAULT_SERVICES = SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_STOP |\
                   SUPPORT_RETURN_HOME | SUPPORT_STATUS | SUPPORT_BATTERY |\
                   SUPPORT_CLEAN_SPOT
ALL_SERVICES = DEFAULT_SERVICES | SUPPORT_PAUSE | SUPPORT_LOCATE

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
CONF_STATE_TOPIC = 'state_topic'
CONF_STATE_TEMPLATE = 'state_template'

DEFAULT_NAME = 'MQTT Vacuum'
DEFAULT_RETAIN = False
DEFAULT_SERVICE_STRINGS = services_to_strings(DEFAULT_SERVICES)
DEFAULT_COMMAND_TOPIC = 'vacuum/command'
DEFAULT_PAYLOAD_TURN_ON = 'turn_on'
DEFAULT_PAYLOAD_TURN_OFF = 'turn_off'
DEFAULT_PAYLOAD_RETURN_TO_BASE = 'return_to_base'
DEFAULT_PAYLOAD_STOP = 'stop'
DEFAULT_PAYLOAD_CLEAN_SPOT = 'clean_spot'
DEFAULT_PAYLOAD_LOCATE = 'locate'
DEFAULT_PAYLOAD_START_PAUSE = 'start_pause'
DEFAULT_BATTERY_LEVEL_TOPIC = 'vacuum/state'
DEFAULT_BATTERY_LEVEL_TEMPLATE = cv.template('{{ value_json.battery_level }}')
DEFAULT_CHARGING_TOPIC = 'vacuum/state'
DEFAULT_CHARGING_TEMPLATE = cv.template('{{ value_json.charging }}')
DEFAULT_STATE_TOPIC = 'vacuum/state'
DEFAULT_STATE_TEMPLATE = cv.template('{{ value_json.state }}')


PLATFORM_SCHEMA = mqtt.MQTT_BASE_PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(ATTR_SUPPORTED_FEATURES, default=DEFAULT_SERVICE_STRINGS):
        vol.All(cv.ensure_list, [vol.In(STRING_TO_SERVICE.keys())]),

    vol.Optional(mqtt.CONF_RETAIN, default=DEFAULT_RETAIN): cv.boolean,

    vol.Optional(mqtt.CONF_COMMAND_TOPIC, default=DEFAULT_COMMAND_TOPIC):
        mqtt.valid_publish_topic,
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

    vol.Optional(CONF_BATTERY_LEVEL_TOPIC,
                 default=DEFAULT_BATTERY_LEVEL_TOPIC):
        mqtt.valid_publish_topic,
    vol.Optional(CONF_BATTERY_LEVEL_TEMPLATE,
                 default=DEFAULT_BATTERY_LEVEL_TEMPLATE):
        cv.template,

    vol.Optional(CONF_CHARGING_TOPIC,
                 default=DEFAULT_CHARGING_TOPIC):
        mqtt.valid_publish_topic,
    vol.Optional(CONF_CHARGING_TEMPLATE,
                 default=DEFAULT_CHARGING_TEMPLATE):
        cv.template,

    vol.Optional(CONF_STATE_TOPIC,
                 default=DEFAULT_STATE_TOPIC):
        mqtt.valid_publish_topic,
    vol.Optional(CONF_STATE_TEMPLATE,
                 default=DEFAULT_STATE_TEMPLATE):
        cv.template,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the vacuum."""
    name = config.get(CONF_NAME)
    supported_feature_strings = config.get(ATTR_SUPPORTED_FEATURES)
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
    battery_level_template.hass = hass

    charging_topic = config.get(CONF_CHARGING_TOPIC)
    charging_template = config.get(CONF_CHARGING_TEMPLATE)
    charging_template.hass = hass

    state_topic = config.get(mqtt.CONF_STATE_TOPIC)
    state_template = config.get(CONF_STATE_TEMPLATE)
    state_template.hass = hass

    async_add_devices([
        MqttVacuum(name, supported_features, qos, retain, command_topic,
                   payload_turn_on, payload_turn_off,
                   payload_return_to_base, payload_stop,
                   payload_clean_spot, payload_locate,
                   payload_start_pause, battery_level_topic,
                   battery_level_template, charging_topic, charging_template,
                   state_topic, state_template),
    ])


class MqttVacuum(VacuumDevice):
    """Representation of a MQTT-controlled vacuum."""

    # pylint: disable=no-self-use
    def __init__(self, name, supported_features, qos, retain, command_topic,
                 payload_turn_on, payload_turn_off, payload_return_to_base,
                 payload_stop, payload_clean_spot, payload_locate,
                 payload_start_pause, battery_level_topic,
                 battery_level_template, charging_topic, charging_template,
                 state_topic, state_template):
        """Initialize the vacuum."""
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

        self._state_topic = state_topic
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
            battery_level = self._battery_level_template\
                .async_render_with_possible_json_value(payload,
                                                       error_value=None)
            if battery_level is not None:
                self._battery_level = int(battery_level)

            charging = self._charging_template\
                .async_render_with_possible_json_value(payload,
                                                       error_value=False)
            state = self._state_template\
                .async_render_with_possible_json_value(payload,
                                                       error_value=None)

            if state:
                if state == 'cleaning':
                    self._state = True
                    self._status = "Cleaning"
                if state == 'docked':
                    self._state = False
                    if charging:
                        self._status = "Docked & Charging"
                    else:
                        self._status = "Docked"
                if state == 'stopped':
                    self._state = False
                    self._status = "Stopped"

            self.async_schedule_update_ha_state()

        yield from self.hass.components.mqtt.async_subscribe(
            self._state_topic, message_received, self._qos)

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
        """Return the battery level of the vacuum."""
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
