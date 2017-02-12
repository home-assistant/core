"""
Support for interfacing with MQTT enabled Media Players.

Configuration:

To use the media_player/mqtt component you will need to adapt (should be
more or less self explaining) the following configuration and add it to
your configuration.yaml file.

media_player:
  - platform: mqtt
    name: Harmann Kardon AVR265
    min_volume: 0
    max_volume: 35
    volume:
      status_topic: "stat/AVR/VOL"
      command_set_topic: "cmnd/AVR/SET_VOL"
      command_up_topic: "cmnd/AVR/VOL_UP"
      command_down_topic: "cmnd/AVR/VOL_DOWN"
    power:
      status_topic: "stat/AVR/POWER_Z1"
      command_topic: "cmnd/AVR/POWER_Z1"
    mute:
      status_topic: "stat/AVR/MUTE_Z1"
      command_topic: "cmnd/AVR/MUTE"
    sources:
      status_topic: "stat/AVR/INPUT"
      command_topic: "cmnd/AVR/INPUT"
      options:
         - SAT
         - BLURAY
         - BRIDGE
         - DVR
         - SIRIUS
         - FM
         - AM
         - TV
         - GAME
         - MEDIA
         - AUX
         - INET_RADIO
         - NETWORK
         - SRC_A
         - SRC_B
         - SRC_C
         - SRC_D
"""

import voluptuous as vol

from homeassistant.components.media_player import (
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_MUTE, SUPPORT_TURN_ON, SUPPORT_TURN_OFF,
    SUPPORT_VOLUME_STEP, SUPPORT_SELECT_SOURCE, MediaPlayerDevice,
    PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_NAME,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
import homeassistant.components.mqtt as mqtt
import homeassistant.helpers.config_validation as cv

DEPENDENCIES = ['mqtt']

DEFAULT_NAME = 'MQTT Media Player'
DEFAULT_MIN_VOLUME = 0
DEFAULT_MAX_VOLUME = 1

SUPPORT_MQTT_MEDIA = SUPPORT_VOLUME_STEP | SUPPORT_VOLUME_MUTE | \
    SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_VOLUME_SET | \
    SUPPORT_SELECT_SOURCE

CONF_MIN_VOLUME = 'min_volume'
CONF_MAX_VOLUME = 'max_volume'
CONF_SOURCE_DICT = 'sources'
CONF_POWER_DICT = 'power'
CONF_VOL_DICT = 'volume'
CONF_MUTE_DICT = 'mute'


SOURCE_DICT_SCHEMA = vol.Schema({
    vol.Required('status_topic'): cv.string,
    vol.Required('command_topic'): cv.string,
    vol.Required('options'): vol.Any(dict, list),
    vol.Optional('retain', default="0"): cv.string,
    vol.Optional('qos', default="0"): cv.string,
})

BASIC_MQTT_SCHEMA = vol.Schema({
    vol.Required('status_topic'): cv.string,
    vol.Required('command_topic'): cv.string,
    vol.Optional('retain', default=False): cv.boolean,
    vol.Optional('qos', default="0"): cv.string,
    vol.Optional('payload_on', default="ON"): cv.string,
    vol.Optional('payload_off', default="OFF"): cv.string,
})

VOLUME_MQTT_SCHEMA = vol.Schema({
    vol.Required('status_topic'): cv.string,
    vol.Optional('command_set_topic'): cv.string,
    vol.Optional('command_up_topic'): cv.string,
    vol.Optional('command_down_topic'): cv.string,
    vol.Optional('retain', default=False): cv.boolean,
    vol.Optional('qos', default="0"): cv.string,
    vol.Optional('payload', default="1"): cv.string,
})


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_MIN_VOLUME, default=DEFAULT_MIN_VOLUME): int,
    vol.Optional(CONF_MAX_VOLUME, default=DEFAULT_MAX_VOLUME): int,
    vol.Optional(CONF_SOURCE_DICT, default={}): SOURCE_DICT_SCHEMA,
    vol.Optional(CONF_POWER_DICT, default={}): BASIC_MQTT_SCHEMA,
    vol.Optional(CONF_VOL_DICT, default={}): VOLUME_MQTT_SCHEMA,
    vol.Optional(CONF_MUTE_DICT, default={}): BASIC_MQTT_SCHEMA,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the MQTT_MEDIA platform."""
    add_devices([MQTTMedia(
        hass,
        config.get(CONF_NAME),
        config.get(CONF_MIN_VOLUME),
        config.get(CONF_MAX_VOLUME),
        config.get(CONF_POWER_DICT),
        config.get(CONF_VOL_DICT),
        config.get(CONF_MUTE_DICT),
        config.get(CONF_SOURCE_DICT),
    )])


class MQTTMedia(MediaPlayerDevice):
    """Representation of a MQTT_MEDIA Receiver."""

    def __init__(
            self,
            hass,
            name,
            min_volume,
            max_volume,
            power_dict,
            vol_dict,
            mute_dict,
            source_dict):
        """Initialize the MQTT_MEDIA Receiver device."""
        self._name = name
        self._min_volume = min_volume
        self._max_volume = max_volume
        self._source_dict = source_dict
        self._power_dict = power_dict
        self._vol_dict = vol_dict
        self._mute_dict = mute_dict
        self._volume = 0
        self._state = STATE_UNKNOWN
        self._mute = STATE_OFF
        self._source = None
        self._payload_off = "OFF"
        self._payload_on = "ON"
        self._retain = False
        self._qos = 0

        mqtt.subscribe(
            hass,
            self._source_dict["status_topic"],
            self.message_source_selected,
            self._qos)
        mqtt.subscribe(
            hass,
            self._power_dict["status_topic"],
            self.message_power_changed,
            self._qos)
        mqtt.subscribe(
            hass,
            self._vol_dict["status_topic"],
            self.message_volume_changed,
            self._qos)
        mqtt.subscribe(
            hass,
            self._mute_dict["status_topic"],
            self.message_mute_changed,
            self._qos)

    def message_source_selected(self, topic, payload, qos):
        """A new MQTT input select message has been received."""
        self._source = payload
        self.update_ha_state()

    def message_power_changed(self, topic, payload, qos):
        """A new MQTT power message has been received."""
        if payload.upper() == "ON":
            self._state = STATE_ON
        if payload.upper() == "OFF":
            self._state = STATE_OFF
        self.update_ha_state()

    def message_volume_changed(self, topic, payload, qos):
        """A new MQTT volume message has been received."""
        self._volume = abs(self._min_volume - int(payload)) / \
            abs(self._min_volume - self._max_volume)
        self.update_ha_state()

    def message_mute_changed(self, topic, payload, qos):
        """A new MQTT mute message has been received."""
        if payload.upper() == "ON":
            self._mute = True
        if payload.upper() == "OFF":
            self._mute = False
        self.update_ha_state()

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

    def update(self):
        """Retrieve latest state."""

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._mute

    @property
    def supported_media_commands(self):
        """Flag of media commands that are supported."""
        return SUPPORT_MQTT_MEDIA

    def turn_off(self):
        """Turn the media player off."""
        mqtt.publish(
            self.hass,
            self._power_dict["command_topic"],
            self._power_dict["payload_off"],
            self._power_dict["qos"],
            self._power_dict["retain"])

    def turn_on(self):
        """Turn the media player on."""
        mqtt.publish(
            self.hass,
            self._power_dict["command_topic"],
            self._power_dict["payload_on"],
            self._power_dict["qos"],
            self._power_dict["retain"])

    def volume_up(self):
        """Volume up the media player."""
        mqtt.publish(
            self.hass,
            self._vol_dict["command_up_topic"],
            self._vol_dict["payload"],
            self._vol_dict["qos"],
            self._vol_dict["retain"])

    def volume_down(self):
        """Volume down the media player."""
        mqtt.publish(
            self.hass,
            self._vol_dict["command_down_topic"],
            self._vol_dict["payload"],
            self._vol_dict["qos"],
            self._vol_dict["retain"])

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        vol_val = self._min_volume + \
            round(abs(self._min_volume - self._max_volume) * volume)
        mqtt.publish(
            self.hass,
            self._vol_dict["command_set_topic"],
            vol_val,
            self._vol_dict["qos"],
            self._vol_dict["retain"])

    def select_source(self, source):
        """Select input source."""
        mqtt.publish(
            self.hass,
            self._source_dict["command_topic"],
            source,
            self._source_dict["qos"],
            self._source_dict["retain"])

    @property
    def source(self):
        """Name of the current input source."""
        return self._source

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_dict["options"]

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        if self._mute:
            mqtt.publish(
                self.hass,
                self._mute_dict["command_topic"],
                self._mute_dict["payload_on"],
                self._mute_dict["qos"],
                self._mute_dict["retain"])
        else:
            mqtt.publish(
                self.hass,
                self._mute_dict["command_topic"],
                self._mute_dict["payload_off"],
                self._mute_dict["qos"],
                self._mute_dict["retain"])
