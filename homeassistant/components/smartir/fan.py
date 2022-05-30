import asyncio
import json
import logging
import os.path

import voluptuous as vol

from homeassistant.components.fan import (
    FanEntity, PLATFORM_SCHEMA,
    DIRECTION_REVERSE, DIRECTION_FORWARD,
    SUPPORT_SET_SPEED, SUPPORT_DIRECTION, SUPPORT_OSCILLATE, 
    ATTR_OSCILLATING )
from homeassistant.const import (
    CONF_NAME, STATE_OFF, STATE_ON, STATE_UNKNOWN)
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item
)
from . import COMPONENT_ABS_DIR, Helper
from .controller import get_controller

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "SmartIR Fan"
DEFAULT_DELAY = 0.5

CONF_UNIQUE_ID = 'unique_id'
CONF_DEVICE_CODE = 'device_code'
CONF_CONTROLLER_DATA = "controller_data"
CONF_DELAY = "delay"
CONF_POWER_SENSOR = 'power_sensor'

SPEED_OFF = "off"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_UNIQUE_ID): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_DEVICE_CODE): cv.positive_int,
    vol.Required(CONF_CONTROLLER_DATA): cv.string,
    vol.Optional(CONF_DELAY, default=DEFAULT_DELAY): cv.string,
    vol.Optional(CONF_POWER_SENSOR): cv.entity_id
})

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the IR Fan platform."""
    device_code = config.get(CONF_DEVICE_CODE)
    device_files_subdir = os.path.join('codes', 'fan')
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
                            "codes/fan/{}.json")

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

    async_add_entities([SmartIRFan(
        hass, config, device_data
    )])

class SmartIRFan(FanEntity, RestoreEntity):
    def __init__(self, hass, config, device_data):
        self.hass = hass
        self._unique_id = config.get(CONF_UNIQUE_ID)
        self._name = config.get(CONF_NAME)
        self._device_code = config.get(CONF_DEVICE_CODE)
        self._controller_data = config.get(CONF_CONTROLLER_DATA)
        self._delay = config.get(CONF_DELAY)
        self._power_sensor = config.get(CONF_POWER_SENSOR)

        self._manufacturer = device_data['manufacturer']
        self._supported_models = device_data['supportedModels']
        self._supported_controller = device_data['supportedController']
        self._commands_encoding = device_data['commandsEncoding']
        self._speed_list = device_data['speed']
        self._commands = device_data['commands']
        
        self._speed = SPEED_OFF
        self._direction = None
        self._last_on_speed = None
        self._oscillating = None
        self._support_flags = SUPPORT_SET_SPEED

        if (DIRECTION_REVERSE in self._commands and \
            DIRECTION_FORWARD in self._commands):
            self._direction = DIRECTION_REVERSE
            self._support_flags = (
                self._support_flags | SUPPORT_DIRECTION)
        if ('oscillate' in self._commands):
            self._oscillating = False
            self._support_flags = (
                self._support_flags | SUPPORT_OSCILLATE)


        self._temp_lock = asyncio.Lock()
        self._on_by_remote = False

        #Init the IR/RF controller
        self._controller = get_controller(
            self.hass,
            self._supported_controller, 
            self._commands_encoding,
            self._controller_data,
            self._delay)

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()
    
        last_state = await self.async_get_last_state()

        if last_state is not None:
            if 'speed' in last_state.attributes:
                self._speed = last_state.attributes['speed']

            #If _direction has a value the direction controls appears 
            #in UI even if SUPPORT_DIRECTION is not provided in the flags
            if ('direction' in last_state.attributes and \
                self._support_flags & SUPPORT_DIRECTION):
                self._direction = last_state.attributes['direction']

            if 'last_on_speed' in last_state.attributes:
                self._last_on_speed = last_state.attributes['last_on_speed']

            if self._power_sensor:
                async_track_state_change(self.hass, self._power_sensor, 
                                         self._async_power_sensor_changed)

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def name(self):
        """Return the display name of the fan."""
        return self._name

    @property
    def state(self):
        """Return the current state."""
        if (self._on_by_remote or \
            self._speed != SPEED_OFF):
            return STATE_ON
        return SPEED_OFF

    @property
    def percentage(self):
        """Return speed percentage of the fan."""
        if (self._speed == SPEED_OFF):
            return 0

        return ordered_list_item_to_percentage(self._speed_list, self._speed)

    @property
    def speed_count(self):
        """Return the number of speeds the fan supports."""
        return len(self._speed_list)

    @property
    def oscillating(self):
        """Return the oscillation state."""
        return self._oscillating

    @property
    def current_direction(self):
        """Return the direction state."""
        return self._direction

    @property
    def last_on_speed(self):
        """Return the last non-idle speed."""
        return self._last_on_speed

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

    @property
    def extra_state_attributes(self):
        """Platform specific attributes."""
        return {
            'last_on_speed': self._last_on_speed,
            'device_code': self._device_code,
            'manufacturer': self._manufacturer,
            'supported_models': self._supported_models,
            'supported_controller': self._supported_controller,
            'commands_encoding': self._commands_encoding,
        }

    async def async_set_percentage(self, percentage: int):
        """Set the desired speed for the fan."""
        if (percentage == 0):
             self._speed = SPEED_OFF
        else:
            self._speed = percentage_to_ordered_list_item(
                self._speed_list, percentage)

        if not self._speed == SPEED_OFF:
            self._last_on_speed = self._speed

        await self.send_command()
        await self.async_update_ha_state()

    async def async_oscillate(self, oscillating: bool) -> None:
        """Set oscillation of the fan."""
        self._oscillating = oscillating

        await self.send_command()
        await self.async_update_ha_state()

    async def async_set_direction(self, direction: str):
        """Set the direction of the fan"""
        self._direction = direction

        if not self._speed.lower() == SPEED_OFF:
            await self.send_command()

        await self.async_update_ha_state()

    async def async_turn_on(self, percentage: int = None, **kwargs):
        """Turn on the fan."""
        if percentage is None:
            percentage = ordered_list_item_to_percentage(
                self._speed_list, self._last_on_speed or self._speed_list[0])

        await self.async_set_percentage(percentage)

    async def async_turn_off(self):
        """Turn off the fan."""
        await self.async_set_percentage(0)

    async def send_command(self):
        async with self._temp_lock:
            self._on_by_remote = False
            speed = self._speed
            direction = self._direction or 'default'
            oscillating = self._oscillating

            if speed.lower() == SPEED_OFF:
                command = self._commands['off']
            elif oscillating:
                command = self._commands['oscillate']
            else:
                command = self._commands[direction][speed] 

            try:
                await self._controller.send(command)
            except Exception as e:
                _LOGGER.exception(e)

    async def _async_power_sensor_changed(self, entity_id, old_state, new_state):
        """Handle power sensor changes."""
        if new_state is None:
            return

        if new_state.state == old_state.state:
            return

        if new_state.state == STATE_ON and self._speed == SPEED_OFF:
            self._on_by_remote = True
            self._speed = None
            await self.async_update_ha_state()

        if new_state.state == STATE_OFF:
            self._on_by_remote = False
            if self._speed != SPEED_OFF:
                self._speed = SPEED_OFF
            await self.async_update_ha_state()