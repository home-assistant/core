import asyncio
import json
import logging
import os.path

import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerEntity, PLATFORM_SCHEMA)
from homeassistant.components.media_player.const import (
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_PREVIOUS_TRACK,
    SUPPORT_NEXT_TRACK, SUPPORT_VOLUME_STEP, SUPPORT_VOLUME_MUTE, 
    SUPPORT_SELECT_SOURCE, MEDIA_TYPE_CHANNEL)
from homeassistant.const import (
    CONF_NAME, STATE_OFF, STATE_ON, STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity
from . import COMPONENT_ABS_DIR, Helper
from .controller import Controller

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "SmartIR Media Player"
DEFAULT_DEVICE_CLASS = "tv"

CONF_UNIQUE_ID = 'unique_id'
CONF_DEVICE_CODE = 'device_code'
CONF_CONTROLLER_DATA = "controller_data"
CONF_POWER_SENSOR = 'power_sensor'
CONF_SOURCE_NAMES = 'source_names'
CONF_DEVICE_CLASS = 'device_class'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_UNIQUE_ID): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_DEVICE_CODE): cv.positive_int,
    vol.Required(CONF_CONTROLLER_DATA): cv.string,
    vol.Optional(CONF_POWER_SENSOR): cv.entity_id,
    vol.Optional(CONF_SOURCE_NAMES): dict,
    vol.Optional(CONF_DEVICE_CLASS, default=DEFAULT_DEVICE_CLASS): cv.string
})

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the IR Media Player platform."""
    device_code = config.get(CONF_DEVICE_CODE)
    device_files_subdir = os.path.join('codes', 'media_player')
    device_files_absdir = os.path.join(COMPONENT_ABS_DIR, device_files_subdir)

    if not os.path.isdir(device_files_absdir):
        os.makedirs(device_files_absdir)

    device_json_filename = str(device_code) + '.json'
    device_json_path = os.path.join(device_files_absdir, device_json_filename)

    if not os.path.exists(device_json_path):
        _LOGGER.warning("Couldn't find the device Json file. The component will " \
                        "try to download it from the GitHub repo.")

        try:
            codes_source = ("https://raw.githubusercontent.com/"
                            "smartHomeHub/SmartIR/master/"
                            "codes/media_player/{}.json")

            await Helper.downloader(codes_source.format(device_code), device_json_path)
        except Exception:
            _LOGGER.error("There was an error while downloading the device Json file. " \
                          "Please check your internet connection or if the device code " \
                          "exists on GitHub. If the problem still exists please " \
                          "place the file manually in the proper directory.")
            return

    with open(device_json_path) as j:
        try:
            device_data = json.load(j)
        except Exception:
            _LOGGER.error("The device JSON file is invalid")
            return

    async_add_entities([SmartIRMediaPlayer(
        hass, config, device_data
    )])

class SmartIRMediaPlayer(MediaPlayerEntity, RestoreEntity):
    def __init__(self, hass, config, device_data):
        self.hass = hass
        self._unique_id = config.get(CONF_UNIQUE_ID)
        self._name = config.get(CONF_NAME)
        self._device_code = config.get(CONF_DEVICE_CODE)
        self._controller_data = config.get(CONF_CONTROLLER_DATA)
        self._power_sensor = config.get(CONF_POWER_SENSOR)

        self._manufacturer = device_data['manufacturer']
        self._supported_models = device_data['supportedModels']
        self._supported_controller = device_data['supportedController']
        self._commands_encoding = device_data['commandsEncoding']
        self._commands = device_data['commands']

        self._state = STATE_OFF
        self._sources_list = []
        self._source = None
        self._support_flags = 0

        self._device_class = config.get(CONF_DEVICE_CLASS)

        #Supported features
        if 'off' in self._commands and self._commands['off'] is not None:
            self._support_flags = self._support_flags | SUPPORT_TURN_OFF

        if 'on' in self._commands and self._commands['on'] is not None:
            self._support_flags = self._support_flags | SUPPORT_TURN_ON

        if 'previousChannel' in self._commands and self._commands['previousChannel'] is not None:
            self._support_flags = self._support_flags | SUPPORT_PREVIOUS_TRACK

        if 'nextChannel' in self._commands and self._commands['nextChannel'] is not None:
            self._support_flags = self._support_flags | SUPPORT_NEXT_TRACK

        if ('volumeDown' in self._commands and self._commands['volumeDown'] is not None) \
        or ('volumeUp' in self._commands and self._commands['volumeUp'] is not None):
            self._support_flags = self._support_flags | SUPPORT_VOLUME_STEP

        if 'mute' in self._commands and self._commands['mute'] is not None:
            self._support_flags = self._support_flags | SUPPORT_VOLUME_MUTE

        if 'sources' in self._commands and self._commands['sources'] is not None:
            self._support_flags = self._support_flags | SUPPORT_SELECT_SOURCE

            for source, new_name in config.get(CONF_SOURCE_NAMES, {}).items():
                if source in self._commands['sources']:
                    if new_name is not None:
                        self._commands['sources'][new_name] = self._commands['sources'][source]

                    del self._commands['sources'][source]

            #Sources list
            for key in self._commands['sources']:
                self._sources_list.append(key)

        self._temp_lock = asyncio.Lock()

        #Init the IR/RF controller
        self._controller = Controller(
            self.hass,
            self._supported_controller, 
            self._commands_encoding,
            self._controller_data)

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()

        if last_state is not None:
            self._state = last_state.state

    @property
    def should_poll(self):
        """Push an update after each command."""
        return True

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the media player."""
        return self._name

    @property
    def device_class(self):
        """Return the device_class of the media player."""
        return self._device_class

    @property
    def state(self):
        """Return the state of the player."""
        return self._state

    @property
    def media_title(self):
        """Return the title of current playing media."""
        return None

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_CHANNEL

    @property
    def source_list(self):
        return self._sources_list
        
    @property
    def source(self):
        return self._source

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return self._support_flags

    @property
    def device_state_attributes(self) -> dict:
        """Platform specific attributes."""
        return {
            'device_code': self._device_code,
            'manufacturer': self._manufacturer,
            'supported_models': self._supported_models,
            'supported_controller': self._supported_controller,
            'commands_encoding': self._commands_encoding,
        }

    async def async_turn_off(self):
        """Turn the media player off."""
        await self.send_command(self._commands['off'])
        
        if self._power_sensor is None:
            self._state = STATE_OFF
            self._source = None
            await self.async_update_ha_state()

    async def async_turn_on(self):
        """Turn the media player off."""
        await self.send_command(self._commands['on'])

        if self._power_sensor is None:
            self._state = STATE_ON
            await self.async_update_ha_state()

    async def async_media_previous_track(self):
        """Send previous track command."""
        await self.send_command(self._commands['previousChannel'])
        await self.async_update_ha_state()

    async def async_media_next_track(self):
        """Send next track command."""
        await self.send_command(self._commands['nextChannel'])
        await self.async_update_ha_state()

    async def async_volume_down(self):
        """Turn volume down for media player."""
        await self.send_command(self._commands['volumeDown'])
        await self.async_update_ha_state()

    async def async_volume_up(self):
        """Turn volume up for media player."""
        await self.send_command(self._commands['volumeUp'])
        await self.async_update_ha_state()
    
    async def async_mute_volume(self, mute):
        """Mute the volume."""
        await self.send_command(self._commands['mute'])
        await self.async_update_ha_state()

    async def async_select_source(self, source):
        """Select channel from source."""
        self._source = source
        await self.send_command(self._commands['sources'][source])
        await self.async_update_ha_state()

    async def send_command(self, command):
        async with self._temp_lock:
            try:
                await self._controller.send(command)
            except Exception as e:
                _LOGGER.exception(e)
            
    async def async_update(self):
        if self._power_sensor is None:
            return

        power_state = self.hass.states.get(self._power_sensor)

        if power_state:
            if power_state.state == STATE_OFF:
                self._state = STATE_OFF
                self._source = None
            elif power_state.state == STATE_ON:
                self._state = STATE_ON
