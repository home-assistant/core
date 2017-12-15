"""
Support for generic receivers by delegating actions to user configured scripts.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.template_media_player/
"""
import asyncio
import logging
import math

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.media_player import MediaPlayerDevice, \
    SUPPORT_TURN_ON, PLATFORM_SCHEMA, SUPPORT_TURN_OFF, \
    SUPPORT_SELECT_SOURCE, SUPPORT_VOLUME_SET, SUPPORT_VOLUME_MUTE, \
    SUPPORT_VOLUME_STEP
from homeassistant.const import CONF_NAME, STATE_ON, STATE_OFF
from homeassistant.helpers.script import Script

CONF_ON_ACTION = 'turn_on_action'
CONF_OFF_ACTION = 'turn_off_action'
CONF_VOLUME_UP_ACTION = 'volume_up_action'
CONF_VOLUME_DOWN_ACTION = 'volume_down_action'
CONF_INITIAL_VOLUME = 'initial_volume'
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
        self._actions = {
            key: Script(hass, value) for key, value in config.items()
            if key.endswith("_action")
        }

        self._sources = config.get(CONF_SOURCE_NAMES)
        self._selected_source = None
        self._state = STATE_OFF
        self._volume = config.get(CONF_INITIAL_VOLUME)
        self._is_muted = False

        self._supported_features = 0
        if CONF_ON_ACTION in self._actions:
            self._supported_features |= SUPPORT_TURN_ON
        if CONF_OFF_ACTION in self._actions:
            self._supported_features |= SUPPORT_TURN_OFF
        if (CONF_VOLUME_UP_ACTION in self._actions and
            CONF_VOLUME_DOWN_ACTION in self._actions):
            self._supported_features |= SUPPORT_VOLUME_STEP
        if CONF_VOLUME_SET_ACTION in self._actions:
            self._supported_features |= SUPPORT_VOLUME_SET
        if CONF_VOLUME_MUTE_ACTION in self._actions and \
           CONF_VOLUME_UNMUTE_ACTION in self._actions:
            self._supported_features |= SUPPORT_VOLUME_MUTE
        if self._sources and CONF_SELECT_SOURCE_ACTION in self._actions:
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

    @asyncio.coroutine
    def turn_on(self):
        """Turn on media player."""
        self._state = STATE_ON
        if CONF_ON_ACTION in self._actions:
            yield from self._actions[CONF_ON_ACTION].async_run()

    @asyncio.coroutine
    def turn_off(self):
        """Turn off media player."""
        self._state = STATE_OFF
        if CONF_OFF_ACTION in self._actions:
            yield from self._actions[CONF_OFF_ACTION].async_run()

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume / 100.0

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._is_muted

    @asyncio.coroutine
    def set_volume_level(self, volume):
        volume = volume * 100
        volume = int(math.ceil(volume / 10.0)) * 10
        if CONF_VOLUME_SET_ACTION in self._actions:
            self._volume = volume
            yield from self._actions[CONF_VOLUME_SET_ACTION].async_run(
                {'volume:': volume})

    @asyncio.coroutine
    def volume_up(self):
        if CONF_VOLUME_UP_ACTION in self._actions:
            yield from self._actions[CONF_VOLUME_UP_ACTION].async_run()

    @asyncio.coroutine
    def volume_down(self):
        if CONF_VOLUME_DOWN_ACTION in self._actions:
            yield from self._actions[CONF_VOLUME_DOWN_ACTION].async_run()


    @asyncio.coroutine
    def mute_volume(self, mute):
        """Mute or unmute the media player"""
        if mute:
            self._is_muted = True
            yield from self._actions[CONF_VOLUME_MUTE_ACTION].async_run(
                {'mute': True}
            )
        else:
            self._is_muted = False
            yield from self._actions[CONF_VOLUME_UNMUTE_ACTION].async_run(
                {'mute': False}
            )

    @property
    def source(self):
        """Return the current input source."""
        return self._selected_source

    @asyncio.coroutine
    def select_source(self, requested_source_name):
        """Select input source."""
        if CONF_SELECT_SOURCE_ACTION in self._actions:
            for source_key, source_name in self._sources.items():
                if source_name == requested_source_name:
                    yield from self._actions[CONF_SELECT_SOURCE_ACTION].async_run(
                        {'source_key': source_key, 'source_name': source_name}
                    )
                    self._selected_source = source_name
                    return

            raise ValueError(
                """Source '{requested_source_name}' was not found in source list.""".format(
                    requested_source_name=requested_source_name)
            )
