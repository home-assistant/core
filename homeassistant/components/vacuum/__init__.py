"""
Support for vacuum cleaner robots (botvacs).

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/vacuum/
"""
from datetime import timedelta
from functools import partial
import logging

import voluptuous as vol

from homeassistant.components import group
from homeassistant.const import (
    ATTR_BATTERY_LEVEL, ATTR_COMMAND, ATTR_ENTITY_ID, SERVICE_TOGGLE,
    SERVICE_TURN_OFF, SERVICE_TURN_ON, STATE_ON, STATE_PAUSED, STATE_IDLE)
from homeassistant.loader import bind_hass
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import (  # noqa
    PLATFORM_SCHEMA, PLATFORM_SCHEMA_BASE)
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity import (ToggleEntity, Entity)
from homeassistant.helpers.icon import icon_for_battery_level

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'vacuum'
DEPENDENCIES = ['group']

SCAN_INTERVAL = timedelta(seconds=20)

GROUP_NAME_ALL_VACUUMS = 'all vacuum cleaners'
ENTITY_ID_ALL_VACUUMS = group.ENTITY_ID_FORMAT.format('all_vacuum_cleaners')

ATTR_BATTERY_ICON = 'battery_icon'
ATTR_CLEANED_AREA = 'cleaned_area'
ATTR_FAN_SPEED = 'fan_speed'
ATTR_FAN_SPEED_LIST = 'fan_speed_list'
ATTR_PARAMS = 'params'
ATTR_STATUS = 'status'

SERVICE_CLEAN_SPOT = 'clean_spot'
SERVICE_LOCATE = 'locate'
SERVICE_RETURN_TO_BASE = 'return_to_base'
SERVICE_SEND_COMMAND = 'send_command'
SERVICE_SET_FAN_SPEED = 'set_fan_speed'
SERVICE_START_PAUSE = 'start_pause'
SERVICE_START = 'start'
SERVICE_PAUSE = 'pause'
SERVICE_STOP = 'stop'

VACUUM_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.comp_entity_ids,
})

VACUUM_SET_FAN_SPEED_SERVICE_SCHEMA = VACUUM_SERVICE_SCHEMA.extend({
    vol.Required(ATTR_FAN_SPEED): cv.string,
})

VACUUM_SEND_COMMAND_SERVICE_SCHEMA = VACUUM_SERVICE_SCHEMA.extend({
    vol.Required(ATTR_COMMAND): cv.string,
    vol.Optional(ATTR_PARAMS): vol.Any(dict, cv.ensure_list),
})

STATE_CLEANING = 'cleaning'
STATE_DOCKED = 'docked'
STATE_IDLE = STATE_IDLE
STATE_PAUSED = STATE_PAUSED
STATE_RETURNING = 'returning'
STATE_ERROR = 'error'

DEFAULT_NAME = 'Vacuum cleaner robot'

SUPPORT_TURN_ON = 1
SUPPORT_TURN_OFF = 2
SUPPORT_PAUSE = 4
SUPPORT_STOP = 8
SUPPORT_RETURN_HOME = 16
SUPPORT_FAN_SPEED = 32
SUPPORT_BATTERY = 64
SUPPORT_STATUS = 128
SUPPORT_SEND_COMMAND = 256
SUPPORT_LOCATE = 512
SUPPORT_CLEAN_SPOT = 1024
SUPPORT_MAP = 2048
SUPPORT_STATE = 4096
SUPPORT_START = 8192


@bind_hass
def is_on(hass, entity_id=None):
    """Return if the vacuum is on based on the statemachine."""
    entity_id = entity_id or ENTITY_ID_ALL_VACUUMS
    return hass.states.is_state(entity_id, STATE_ON)


async def async_setup(hass, config):
    """Set up the vacuum component."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL, GROUP_NAME_ALL_VACUUMS)

    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_TURN_ON, VACUUM_SERVICE_SCHEMA,
        'async_turn_on'
    )
    component.async_register_entity_service(
        SERVICE_TURN_OFF, VACUUM_SERVICE_SCHEMA,
        'async_turn_off'
    )
    component.async_register_entity_service(
        SERVICE_TOGGLE, VACUUM_SERVICE_SCHEMA,
        'async_toggle'
    )
    component.async_register_entity_service(
        SERVICE_START_PAUSE, VACUUM_SERVICE_SCHEMA,
        'async_start_pause'
    )
    component.async_register_entity_service(
        SERVICE_START, VACUUM_SERVICE_SCHEMA,
        'async_start'
    )
    component.async_register_entity_service(
        SERVICE_PAUSE, VACUUM_SERVICE_SCHEMA,
        'async_pause'
    )
    component.async_register_entity_service(
        SERVICE_RETURN_TO_BASE, VACUUM_SERVICE_SCHEMA,
        'async_return_to_base'
    )
    component.async_register_entity_service(
        SERVICE_CLEAN_SPOT, VACUUM_SERVICE_SCHEMA,
        'async_clean_spot'
    )
    component.async_register_entity_service(
        SERVICE_LOCATE, VACUUM_SERVICE_SCHEMA,
        'async_locate'
    )
    component.async_register_entity_service(
        SERVICE_STOP, VACUUM_SERVICE_SCHEMA,
        'async_stop'
    )
    component.async_register_entity_service(
        SERVICE_SET_FAN_SPEED, VACUUM_SET_FAN_SPEED_SERVICE_SCHEMA,
        'async_set_fan_speed'
    )
    component.async_register_entity_service(
        SERVICE_SEND_COMMAND, VACUUM_SEND_COMMAND_SERVICE_SCHEMA,
        'async_send_command'
    )

    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)


class _BaseVacuum(Entity):
    """Representation of a base vacuum.

    Contains common properties and functions for all vacuum devices.
    """

    @property
    def supported_features(self):
        """Flag vacuum cleaner features that are supported."""
        raise NotImplementedError()

    @property
    def battery_level(self):
        """Return the battery level of the vacuum cleaner."""
        return None

    @property
    def fan_speed(self):
        """Return the fan speed of the vacuum cleaner."""
        return None

    @property
    def fan_speed_list(self):
        """Get the list of available fan speed steps of the vacuum cleaner."""
        raise NotImplementedError()

    def stop(self, **kwargs):
        """Stop the vacuum cleaner."""
        raise NotImplementedError()

    async def async_stop(self, **kwargs):
        """Stop the vacuum cleaner.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(partial(self.stop, **kwargs))

    def return_to_base(self, **kwargs):
        """Set the vacuum cleaner to return to the dock."""
        raise NotImplementedError()

    async def async_return_to_base(self, **kwargs):
        """Set the vacuum cleaner to return to the dock.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(
            partial(self.return_to_base, **kwargs))

    def clean_spot(self, **kwargs):
        """Perform a spot clean-up."""
        raise NotImplementedError()

    async def async_clean_spot(self, **kwargs):
        """Perform a spot clean-up.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(
            partial(self.clean_spot, **kwargs))

    def locate(self, **kwargs):
        """Locate the vacuum cleaner."""
        raise NotImplementedError()

    async def async_locate(self, **kwargs):
        """Locate the vacuum cleaner.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(partial(self.locate, **kwargs))

    def set_fan_speed(self, fan_speed, **kwargs):
        """Set fan speed."""
        raise NotImplementedError()

    async def async_set_fan_speed(self, fan_speed, **kwargs):
        """Set fan speed.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(
            partial(self.set_fan_speed, fan_speed, **kwargs))

    def send_command(self, command, params=None, **kwargs):
        """Send a command to a vacuum cleaner."""
        raise NotImplementedError()

    async def async_send_command(self, command, params=None, **kwargs):
        """Send a command to a vacuum cleaner.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(
            partial(self.send_command, command, params=params, **kwargs))


class VacuumDevice(_BaseVacuum, ToggleEntity):
    """Representation of a vacuum cleaner robot."""

    @property
    def status(self):
        """Return the status of the vacuum cleaner."""
        return None

    @property
    def battery_icon(self):
        """Return the battery icon for the vacuum cleaner."""
        charging = False
        if self.status is not None:
            charging = 'charg' in self.status.lower()
        return icon_for_battery_level(
            battery_level=self.battery_level, charging=charging)

    @property
    def state_attributes(self):
        """Return the state attributes of the vacuum cleaner."""
        data = {}

        if self.status is not None:
            data[ATTR_STATUS] = self.status

        if self.battery_level is not None:
            data[ATTR_BATTERY_LEVEL] = self.battery_level
            data[ATTR_BATTERY_ICON] = self.battery_icon

        if self.fan_speed is not None:
            data[ATTR_FAN_SPEED] = self.fan_speed
            data[ATTR_FAN_SPEED_LIST] = self.fan_speed_list

        return data

    def turn_on(self, **kwargs):
        """Turn the vacuum on and start cleaning."""
        raise NotImplementedError()

    async def async_turn_on(self, **kwargs):
        """Turn the vacuum on and start cleaning.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(
            partial(self.turn_on, **kwargs))

    def turn_off(self, **kwargs):
        """Turn the vacuum off stopping the cleaning and returning home."""
        raise NotImplementedError()

    async def async_turn_off(self, **kwargs):
        """Turn the vacuum off stopping the cleaning and returning home.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(
            partial(self.turn_off, **kwargs))

    def start_pause(self, **kwargs):
        """Start, pause or resume the cleaning task."""
        raise NotImplementedError()

    async def async_start_pause(self, **kwargs):
        """Start, pause or resume the cleaning task.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(
            partial(self.start_pause, **kwargs))


class StateVacuumDevice(_BaseVacuum):
    """Representation of a vacuum cleaner robot that supports states."""

    @property
    def state(self):
        """Return the state of the vacuum cleaner."""
        return None

    @property
    def battery_icon(self):
        """Return the battery icon for the vacuum cleaner."""
        charging = bool(self.state == STATE_DOCKED)

        return icon_for_battery_level(
            battery_level=self.battery_level, charging=charging)

    @property
    def state_attributes(self):
        """Return the state attributes of the vacuum cleaner."""
        data = {}

        if self.battery_level is not None:
            data[ATTR_BATTERY_LEVEL] = self.battery_level
            data[ATTR_BATTERY_ICON] = self.battery_icon

        if self.fan_speed is not None:
            data[ATTR_FAN_SPEED] = self.fan_speed
            data[ATTR_FAN_SPEED_LIST] = self.fan_speed_list

        return data

    def start(self):
        """Start or resume the cleaning task."""
        raise NotImplementedError()

    async def async_start(self):
        """Start or resume the cleaning task.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(self.start)

    def pause(self):
        """Pause the cleaning task."""
        raise NotImplementedError()

    async def async_pause(self):
        """Pause the cleaning task.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(self.pause)
