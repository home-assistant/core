"""
Provides functionality to interact with fans.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/fan/
"""
import asyncio
from datetime import timedelta
import functools as ft
import logging

import voluptuous as vol

from homeassistant.components import group
from homeassistant.const import (SERVICE_TURN_ON, SERVICE_TOGGLE,
                                 SERVICE_TURN_OFF, ATTR_ENTITY_ID,
                                 STATE_UNKNOWN)
from homeassistant.loader import bind_hass
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'fan'
DEPENDENCIES = ['group']
SCAN_INTERVAL = timedelta(seconds=30)

GROUP_NAME_ALL_FANS = 'all fans'
ENTITY_ID_ALL_FANS = group.ENTITY_ID_FORMAT.format(GROUP_NAME_ALL_FANS)

ENTITY_ID_FORMAT = DOMAIN + '.{}'

# Bitfield of features supported by the fan entity
SUPPORT_SET_SPEED = 1
SUPPORT_OSCILLATE = 2
SUPPORT_DIRECTION = 4

SERVICE_SET_SPEED = 'set_speed'
SERVICE_OSCILLATE = 'oscillate'
SERVICE_SET_DIRECTION = 'set_direction'

SPEED_OFF = 'off'
SPEED_LOW = 'low'
SPEED_MEDIUM = 'medium'
SPEED_HIGH = 'high'

DIRECTION_FORWARD = 'forward'
DIRECTION_REVERSE = 'reverse'

ATTR_SPEED = 'speed'
ATTR_SPEED_LIST = 'speed_list'
ATTR_OSCILLATING = 'oscillating'
ATTR_DIRECTION = 'direction'

PROP_TO_ATTR = {
    'speed': ATTR_SPEED,
    'speed_list': ATTR_SPEED_LIST,
    'oscillating': ATTR_OSCILLATING,
    'direction': ATTR_DIRECTION,
}  # type: dict

FAN_SET_SPEED_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_SPEED): cv.string
})  # type: dict

FAN_TURN_ON_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional(ATTR_SPEED): cv.string
})  # type: dict

FAN_TURN_OFF_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids
})  # type: dict

FAN_OSCILLATE_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_OSCILLATING): cv.boolean
})  # type: dict

FAN_TOGGLE_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids
})

FAN_SET_DIRECTION_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional(ATTR_DIRECTION): cv.string
})  # type: dict

SERVICE_TO_METHOD = {
    SERVICE_TURN_ON: {
        'method': 'async_turn_on',
        'schema': FAN_TURN_ON_SCHEMA,
    },
    SERVICE_TURN_OFF: {
        'method': 'async_turn_off',
        'schema': FAN_TURN_OFF_SCHEMA,
    },
    SERVICE_TOGGLE: {
        'method': 'async_toggle',
        'schema': FAN_TOGGLE_SCHEMA,
    },
    SERVICE_SET_SPEED: {
        'method': 'async_set_speed',
        'schema': FAN_SET_SPEED_SCHEMA,
    },
    SERVICE_OSCILLATE: {
        'method': 'async_oscillate',
        'schema': FAN_OSCILLATE_SCHEMA,
    },
    SERVICE_SET_DIRECTION: {
        'method': 'async_set_direction',
        'schema': FAN_SET_DIRECTION_SCHEMA,
    },
}


@bind_hass
def is_on(hass, entity_id: str=None) -> bool:
    """Return if the fans are on based on the statemachine."""
    entity_id = entity_id or ENTITY_ID_ALL_FANS
    state = hass.states.get(entity_id)
    return state.attributes[ATTR_SPEED] not in [SPEED_OFF, STATE_UNKNOWN]


@bind_hass
def turn_on(hass, entity_id: str=None, speed: str=None) -> None:
    """Turn all or specified fan on."""
    data = {
        key: value for key, value in [
            (ATTR_ENTITY_ID, entity_id),
            (ATTR_SPEED, speed),
        ] if value is not None
    }

    hass.services.call(DOMAIN, SERVICE_TURN_ON, data)


@bind_hass
def turn_off(hass, entity_id: str=None) -> None:
    """Turn all or specified fan off."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}

    hass.services.call(DOMAIN, SERVICE_TURN_OFF, data)


@bind_hass
def toggle(hass, entity_id: str=None) -> None:
    """Toggle all or specified fans."""
    data = {
        ATTR_ENTITY_ID: entity_id
    }

    hass.services.call(DOMAIN, SERVICE_TOGGLE, data)


@bind_hass
def oscillate(hass, entity_id: str=None, should_oscillate: bool=True) -> None:
    """Set oscillation on all or specified fan."""
    data = {
        key: value for key, value in [
            (ATTR_ENTITY_ID, entity_id),
            (ATTR_OSCILLATING, should_oscillate),
        ] if value is not None
    }

    hass.services.call(DOMAIN, SERVICE_OSCILLATE, data)


@bind_hass
def set_speed(hass, entity_id: str=None, speed: str=None) -> None:
    """Set speed for all or specified fan."""
    data = {
        key: value for key, value in [
            (ATTR_ENTITY_ID, entity_id),
            (ATTR_SPEED, speed),
        ] if value is not None
    }

    hass.services.call(DOMAIN, SERVICE_SET_SPEED, data)


@bind_hass
def set_direction(hass, entity_id: str=None, direction: str=None) -> None:
    """Set direction for all or specified fan."""
    data = {
        key: value for key, value in [
            (ATTR_ENTITY_ID, entity_id),
            (ATTR_DIRECTION, direction),
        ] if value is not None
    }

    hass.services.call(DOMAIN, SERVICE_SET_DIRECTION, data)


@asyncio.coroutine
def async_setup(hass, config: dict):
    """Expose fan control via statemachine and services."""
    component = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL, GROUP_NAME_ALL_FANS)

    yield from component.async_setup(config)

    @asyncio.coroutine
    def async_handle_fan_service(service):
        """Handle service call for fans."""
        method = SERVICE_TO_METHOD.get(service.service)
        params = service.data.copy()

        # Convert the entity ids to valid fan ids
        target_fans = component.async_extract_from_service(service)
        params.pop(ATTR_ENTITY_ID, None)

        update_tasks = []
        for fan in target_fans:
            yield from getattr(fan, method['method'])(**params)
            if not fan.should_poll:
                continue
            update_tasks.append(fan.async_update_ha_state(True))

        if update_tasks:
            yield from asyncio.wait(update_tasks, loop=hass.loop)

    for service_name in SERVICE_TO_METHOD:
        schema = SERVICE_TO_METHOD[service_name].get('schema')
        hass.services.async_register(
            DOMAIN, service_name, async_handle_fan_service, schema=schema)

    return True


class FanEntity(ToggleEntity):
    """Representation of a fan."""

    def set_speed(self: ToggleEntity, speed: str) -> None:
        """Set the speed of the fan."""
        raise NotImplementedError()

    def async_set_speed(self: ToggleEntity, speed: str):
        """Set the speed of the fan.

        This method must be run in the event loop and returns a coroutine.
        """
        if speed is SPEED_OFF:
            return self.async_turn_off()
        return self.hass.async_add_job(self.set_speed, speed)

    def set_direction(self: ToggleEntity, direction: str) -> None:
        """Set the direction of the fan."""
        raise NotImplementedError()

    def async_set_direction(self: ToggleEntity, direction: str):
        """Set the direction of the fan.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.set_direction, direction)

    def turn_on(self: ToggleEntity, speed: str=None, **kwargs) -> None:
        """Turn on the fan."""
        raise NotImplementedError()

    def async_turn_on(self: ToggleEntity, speed: str=None, **kwargs):
        """Turn on the fan.

        This method must be run in the event loop and returns a coroutine.
        """
        if speed is SPEED_OFF:
            return self.async_turn_off()
        return self.hass.async_add_job(
            ft.partial(self.turn_on, speed, **kwargs))

    def oscillate(self: ToggleEntity, oscillating: bool) -> None:
        """Oscillate the fan."""
        pass

    def async_oscillate(self: ToggleEntity, oscillating: bool):
        """Oscillate the fan.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.oscillate, oscillating)

    @property
    def is_on(self):
        """Return true if the entity is on."""
        return self.speed not in [SPEED_OFF, STATE_UNKNOWN]

    @property
    def speed(self) -> str:
        """Return the current speed."""
        return None

    @property
    def speed_list(self: ToggleEntity) -> list:
        """Get the list of available speeds."""
        return []

    @property
    def current_direction(self) -> str:
        """Return the current direction of the fan."""
        return None

    @property
    def state_attributes(self: ToggleEntity) -> dict:
        """Return optional state attributes."""
        data = {}  # type: dict

        for prop, attr in PROP_TO_ATTR.items():
            if not hasattr(self, prop):
                continue

            value = getattr(self, prop)
            if value is not None:
                data[attr] = value

        return data

    @property
    def supported_features(self: ToggleEntity) -> int:
        """Flag supported features."""
        return 0
