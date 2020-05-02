"""Support for vacuum cleaner robots (botvacs)."""
from datetime import timedelta
from functools import partial
import logging

import voluptuous as vol

from homeassistant.const import (  # noqa: F401 # STATE_PAUSED/IDLE are API
    ATTR_BATTERY_LEVEL,
    ATTR_COMMAND,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_IDLE,
    STATE_ON,
    STATE_PAUSED,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
    make_entity_service_schema,
)
from homeassistant.helpers.entity import Entity, ToggleEntity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.loader import bind_hass

# mypy: allow-untyped-defs, no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)

DOMAIN = "vacuum"
SCAN_INTERVAL = timedelta(seconds=20)

ATTR_BATTERY_ICON = "battery_icon"
ATTR_CLEANED_AREA = "cleaned_area"
ATTR_FAN_SPEED = "fan_speed"
ATTR_FAN_SPEED_LIST = "fan_speed_list"
ATTR_PARAMS = "params"
ATTR_STATUS = "status"

SERVICE_CLEAN_SPOT = "clean_spot"
SERVICE_LOCATE = "locate"
SERVICE_RETURN_TO_BASE = "return_to_base"
SERVICE_SEND_COMMAND = "send_command"
SERVICE_SET_FAN_SPEED = "set_fan_speed"
SERVICE_START_PAUSE = "start_pause"
SERVICE_START = "start"
SERVICE_PAUSE = "pause"
SERVICE_STOP = "stop"


STATE_CLEANING = "cleaning"
STATE_DOCKED = "docked"
STATE_RETURNING = "returning"
STATE_ERROR = "error"

STATES = [STATE_CLEANING, STATE_DOCKED, STATE_RETURNING, STATE_ERROR]

DEFAULT_NAME = "Vacuum cleaner robot"

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
def is_on(hass, entity_id):
    """Return if the vacuum is on based on the statemachine."""
    return hass.states.is_state(entity_id, STATE_ON)


async def async_setup(hass, config):
    """Set up the vacuum component."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    await component.async_setup(config)

    component.async_register_entity_service(SERVICE_TURN_ON, {}, "async_turn_on")
    component.async_register_entity_service(SERVICE_TURN_OFF, {}, "async_turn_off")
    component.async_register_entity_service(SERVICE_TOGGLE, {}, "async_toggle")
    component.async_register_entity_service(
        SERVICE_START_PAUSE, {}, "async_start_pause"
    )
    component.async_register_entity_service(SERVICE_START, {}, "async_start")
    component.async_register_entity_service(SERVICE_PAUSE, {}, "async_pause")
    component.async_register_entity_service(
        SERVICE_RETURN_TO_BASE, {}, "async_return_to_base"
    )
    component.async_register_entity_service(SERVICE_CLEAN_SPOT, {}, "async_clean_spot")
    component.async_register_entity_service(SERVICE_LOCATE, {}, "async_locate")
    component.async_register_entity_service(SERVICE_STOP, {}, "async_stop")
    component.async_register_entity_service(
        SERVICE_SET_FAN_SPEED,
        {vol.Required(ATTR_FAN_SPEED): cv.string},
        "async_set_fan_speed",
    )
    component.async_register_entity_service(
        SERVICE_SEND_COMMAND,
        {
            vol.Required(ATTR_COMMAND): cv.string,
            vol.Optional(ATTR_PARAMS): vol.Any(dict, cv.ensure_list),
        },
        "async_send_command",
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
        await self.hass.async_add_executor_job(partial(self.return_to_base, **kwargs))

    def clean_spot(self, **kwargs):
        """Perform a spot clean-up."""
        raise NotImplementedError()

    async def async_clean_spot(self, **kwargs):
        """Perform a spot clean-up.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(partial(self.clean_spot, **kwargs))

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
            partial(self.set_fan_speed, fan_speed, **kwargs)
        )

    def send_command(self, command, params=None, **kwargs):
        """Send a command to a vacuum cleaner."""
        raise NotImplementedError()

    async def async_send_command(self, command, params=None, **kwargs):
        """Send a command to a vacuum cleaner.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(
            partial(self.send_command, command, params=params, **kwargs)
        )


class VacuumEntity(_BaseVacuum, ToggleEntity):
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
            charging = "charg" in self.status.lower()
        return icon_for_battery_level(
            battery_level=self.battery_level, charging=charging
        )

    @property
    def capability_attributes(self):
        """Return capability attributes."""
        if self.fan_speed is not None:
            return {ATTR_FAN_SPEED_LIST: self.fan_speed_list}

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

        return data

    def turn_on(self, **kwargs):
        """Turn the vacuum on and start cleaning."""
        raise NotImplementedError()

    async def async_turn_on(self, **kwargs):
        """Turn the vacuum on and start cleaning.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(partial(self.turn_on, **kwargs))

    def turn_off(self, **kwargs):
        """Turn the vacuum off stopping the cleaning and returning home."""
        raise NotImplementedError()

    async def async_turn_off(self, **kwargs):
        """Turn the vacuum off stopping the cleaning and returning home.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(partial(self.turn_off, **kwargs))

    def start_pause(self, **kwargs):
        """Start, pause or resume the cleaning task."""
        raise NotImplementedError()

    async def async_start_pause(self, **kwargs):
        """Start, pause or resume the cleaning task.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(partial(self.start_pause, **kwargs))

    async def async_pause(self):
        """Not supported."""

    async def async_start(self):
        """Not supported."""


class VacuumDevice(VacuumEntity):
    """Representation of a vacuum (for backwards compatibility)."""

    def __init_subclass__(cls, **kwargs):
        """Print deprecation warning."""
        super().__init_subclass__(**kwargs)
        _LOGGER.warning(
            "VacuumDevice is deprecated, modify %s to extend VacuumEntity",
            cls.__name__,
        )


class StateVacuumEntity(_BaseVacuum):
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
            battery_level=self.battery_level, charging=charging
        )

    @property
    def capability_attributes(self):
        """Return capability attributes."""
        if self.fan_speed is not None:
            return {ATTR_FAN_SPEED_LIST: self.fan_speed_list}

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

    async def async_turn_on(self, **kwargs):
        """Not supported."""

    async def async_turn_off(self, **kwargs):
        """Not supported."""

    async def async_toggle(self, **kwargs):
        """Not supported."""


class StateVacuumDevice(StateVacuumEntity):
    """Representation of a vacuum (for backwards compatibility)."""

    def __init_subclass__(cls, **kwargs):
        """Print deprecation warning."""
        super().__init_subclass__(**kwargs)
        _LOGGER.warning(
            "StateVacuumDevice is deprecated, modify %s to extend StateVacuumEntity",
            cls.__name__,
        )
