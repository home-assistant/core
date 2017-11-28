"""
Support for generic receivers by delegating actions to user configured scripts.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.template_media_player/
"""
import asyncio
import logging
import math
import time

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.media_player import MediaPlayerDevice, \
    SUPPORT_TURN_ON, PLATFORM_SCHEMA, SUPPORT_TURN_OFF, \
    SUPPORT_SELECT_SOURCE, SUPPORT_VOLUME_SET, SUPPORT_VOLUME_MUTE
from homeassistant.const import CONF_NAME, STATE_ON, STATE_OFF
from homeassistant.helpers.script import Script

_LOGGER = logging.getLogger(__name__)

CONF_ON_ACTION = 'turn_on_action'
CONF_OFF_ACTION = 'turn_off_action'
CONF_VOLUME_UP_ACTION = 'volume_up_action'
CONF_VOLUME_DOWN_ACTION = 'volume_down_action'
CONF_INITIAL_VOLUME = 'initial_volume'
CONF_VOLUME_STEP = 'volume_step'
CONF_VOLUME_STEP_DELAY = 'volume_step_delay'
CONF_VOLUME_SET_ACTION = 'volume_set_action'
CONF_VOLUME_MUTE_ACTION = 'volume_mute_action'
CONF_VOLUME_UNMUTE_ACTION = 'volume_unmute_action'
CONF_SOURCE_NAMES = 'source_names'
CONF_SELECT_SOURCE_ACTION = 'select_source_action'
DEFAULT_NAME = "Template Media Player"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_ON_ACTION): cv.SCRIPT_SCHEMA,
    vol.Optional(CONF_OFF_ACTION): cv.SCRIPT_SCHEMA,
    vol.Optional(CONF_VOLUME_UP_ACTION): cv.SCRIPT_SCHEMA,
    vol.Optional(CONF_VOLUME_DOWN_ACTION): cv.SCRIPT_SCHEMA,
    vol.Optional(CONF_INITIAL_VOLUME, default=50): cv.positive_int,
    vol.Optional(CONF_VOLUME_STEP, default=5): cv.positive_int,
    vol.Optional(CONF_VOLUME_STEP_DELAY, default=0.5): cv.positive_int,
    vol.Optional(CONF_VOLUME_SET_ACTION): cv.SCRIPT_SCHEMA,
    vol.Optional(CONF_VOLUME_MUTE_ACTION): cv.SCRIPT_SCHEMA,
    vol.Optional(CONF_VOLUME_UNMUTE_ACTION): cv.SCRIPT_SCHEMA,
    vol.Optional(CONF_SELECT_SOURCE_ACTION): cv.SCRIPT_SCHEMA,
    vol.Optional(CONF_SOURCE_NAMES, default=None): {cv.string: cv.string},
})

@asyncio.coroutine
def async_setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the template media player platform."""
    add_devices([
        TemplateMediaPlayerDevice(
            config.get(CONF_NAME),
            config,
            hass
        )
    ])


class TemplateMediaPlayerDevice(MediaPlayerDevice):
    """ Represents a generic device that delegates all operations to other services """

    def __init__(self, name, config, hass):
        """Initialize the device."""
        self._name = name
        self._turn_on_action = Script(hass, config.get(
            CONF_ON_ACTION)) if config.get(CONF_ON_ACTION) else None
        self._turn_off_action = Script(hass, config.get(
            CONF_OFF_ACTION)) if config.get(CONF_OFF_ACTION) else None
        self._volume_up_action = Script(hass, config.get(
            CONF_VOLUME_UP_ACTION)) if config.get(
            CONF_VOLUME_UP_ACTION) else None
        self._volume_down_action = Script(hass, config.get(
            CONF_VOLUME_DOWN_ACTION)) if config.get(
            CONF_VOLUME_DOWN_ACTION) else None
        self._volume_set_action = Script(hass, config.get(
            CONF_VOLUME_SET_ACTION)) if config.get(
            CONF_VOLUME_SET_ACTION) else None
        self._volume_mute_action = Script(hass, config.get(
            CONF_VOLUME_MUTE_ACTION)) if config.get(
            CONF_VOLUME_MUTE_ACTION) else None
        self._volume_unmute_action = Script(hass, config.get(
            CONF_VOLUME_UNMUTE_ACTION)) if config.get(
            CONF_VOLUME_UNMUTE_ACTION) else None
        self._select_source_action = Script(hass, config.get(
            CONF_SELECT_SOURCE_ACTION)) if config.get(
            CONF_SELECT_SOURCE_ACTION) else None
        self._sources = config.get(CONF_SOURCE_NAMES)
        self._selected_source = None
        self._state = STATE_OFF
        self._volume = config.get(CONF_INITIAL_VOLUME)
        self._volume_step = config.get(CONF_VOLUME_STEP)
        self._volume_step_delay = config.get(CONF_VOLUME_STEP_DELAY)
        self._is_muted = False
        self._supported_features = 0
        if self._turn_on_action:
            self._supported_features |= SUPPORT_TURN_ON
        if self._turn_off_action:
            self._supported_features |= SUPPORT_TURN_OFF
        if (self._volume_up_action and self._volume_down_action) or \
                self._volume_set_action:
            self._supported_features |= SUPPORT_VOLUME_SET
        if self._volume_mute_action and self._volume_unmute_action:
            self._supported_features |= SUPPORT_VOLUME_MUTE
        if self._sources and self._select_source_action:
            self._supported_features |= SUPPORT_SELECT_SOURCE


    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return self._supported_features


    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def source_list(self):
        """List of available input sources."""
        return list(self._sources.values())

    def turn_on(self):
        """Turn on media player."""
        self._state = STATE_ON
        if self._turn_on_action:
            self._turn_on_action.run()

    def turn_off(self):
        """Turn off media player."""
        self._state = STATE_OFF
        if self._turn_off_action:
            self._turn_off_action.async_run()

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume / 100.0

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._is_muted

    def set_volume_level(self, volume):
        volume = volume * 100
        volume = int(math.ceil(volume / 10.0)) * 10
        if self._volume_set_action:
            self._volume = volume
            self._volume_set_action.async_run({'volume:': volume})
        elif self._volume_up_action and self._volume_down_action:
            adjustment_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(adjustment_loop)
            adjustment_loop.run_until_complete(asyncio.ensure_future(
                self.adjust_volume(volume)
            ))
            adjustment_loop.close()

    @asyncio.coroutine
    def adjust_volume(self, volume):
        if volume < self._volume:
            while volume < self._volume:
                self._volume -= self._volume_step
                self._volume_down_action.async_run()
                yield from asyncio.sleep(self._volume_step_delay)
        else:
            while volume > self._volume:
                self._volume += self._volume_step
                self._volume_up_action.async_run()
                yield from asyncio.sleep(self._volume_step_delay)



    def mute_volume(self, mute):
        """Mute or unmute the media player"""
        if mute:
            self._is_muted = True
            self._volume_mute_action.async_run({'mute': True})
        else:
            self._is_muted = False
            self._volume_unmute_action.async_run({'mute': False})

    @property
    def source(self):
        """Return the current input source."""
        return self._selected_source

    def select_source(self, requested_source_name):
        """Select input source."""
        if self._select_source_action:
            for source_key, source_name in self._sources.items():
                if source_name == requested_source_name:
                    self._select_source_action.async_run(
                        {'source_key': source_key, 'source_name': source_name})
                    self._selected_source = source_name
                    return
            raise ValueError(
                """Source '{requested_source_name}' was 
                not found in source list.""".format(
                    requested_source_name=requested_source_name
                )
            )
