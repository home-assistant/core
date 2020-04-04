"""Support for Anthem Network Receivers and Processors."""
import logging

import pyeiscp
import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = "onkyo"

DEFAULT_PORT = 60128

SUPPORT_ANTHEMAV = (
    SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_SELECT_SOURCE
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)

DEVICE = None


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up our socket to the AVR."""

    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    name = config.get(CONF_NAME)
    device = None

    _LOGGER.info("Provisioning Anthem AVR device at %s:%d", host, port)

    @callback
    def async_anthemav_update_callback(message):
        """Receive notification from transport that new data exists."""
        _LOGGER.debug("Received update callback from AVR: %s", message)
        device.process_update(message)
        hass.async_create_task(device.async_update_ha_state())

    avr = await pyeiscp.Connection.create(
        host=host, port=port, update_callback=async_anthemav_update_callback
    )

    device = AnthemAVR(avr, name)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, device.avr.close)
    async_add_entities([device])


class AnthemAVR(MediaPlayerDevice):
    """Entity reading values from Anthem AVR protocol."""

    def __init__(self, avr, name):
        """Initialize entity with transport."""
        super().__init__()
        self.avr = avr
        self._name = name
        self._volume = 0
        self._powerstate = STATE_ON
        self._muted = False
        self._source = None

    def process_update(self, update):
        zone, command, value = update
        _LOGGER.info("recieved update about %s" % command)
        if command in ["volume", "master-volume"]:
            self._volume = value / 90
        elif command == "power":
            self._powerstate = value == "on"

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_ANTHEMAV

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return name of device."""
        return self._name

    @property
    def state(self):
        """Return state of power on/off."""
        return self._powerstate

    @property
    def is_volume_muted(self):
        """Return boolean reflecting mute state on device."""
        return self._muted

    @property
    def volume_level(self):
        """Return volume level from 0 to 1."""
        return self._volume

    @property
    def source(self):
        """Return currently selected input."""
        return self._source

    @property
    def source_list(self):
        """Return all active, configured inputs."""
        return ["unknown"]

    async def async_select_source(self, source):
        """Change AVR to the designated source (by name)."""
        self._update_avr("input_name", source)

    async def async_turn_off(self):
        """Turn AVR power off."""
        self._update_avr("power", "on")

    async def async_turn_on(self):
        """Turn AVR power on."""
        self._update_avr("power", "off")

    async def async_volume_up(self):
        """Increment volume by 1"""
        self._update_avr("volume", "level-up")

    async def async_volume_down(self):
        """Decrement volume by 1"""
        self._update_avr("volume", "level-down")

    async def async_set_volume_level(self, volume):
        """Set AVR volume (0 to 1)."""
        self._update_avr("volume", round(volume * 90))

    async def async_mute_volume(self, mute):
        """Engage AVR mute."""
        self._update_avr("mute", mute)

    def _update_avr(self, propname, value):
        """Update a property in the AVR."""
        _LOGGER.info("Sending command to AVR: set %s to %s", propname, str(value))
        self.avr.send(f"{propname}={value}")
