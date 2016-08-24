"""
Provides functionality to interact with fans.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/fan/
"""
import logging
import os
import csv

import voluptuous as vol

from homeassistant.components import group
from homeassistant.config import load_yaml_config_file
from homeassistant.const import (
    STATE_OFF, SERVICE_TURN_ON,
    SERVICE_TURN_OFF, ATTR_ENTITY_ID)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
import homeassistant.helpers.config_validation as cv


DOMAIN = "fan"
SCAN_INTERVAL = 30

GROUP_NAME_ALL_FANS = 'all fans'
ENTITY_ID_ALL_FANS = group.ENTITY_ID_FORMAT.format(GROUP_NAME_ALL_FANS)

ENTITY_ID_FORMAT = DOMAIN + '.{}'

# Bitfield of features supported by the fan entity
ATTR_SUPPORTED_FEATURES = 'supported_features'
SUPPORT_SET_SPEED = 1
SUPPORT_OSCILLATE = 2

SERVICE_SET_SPEED = 'set_speed'
SERVICE_OSCILLATE = 'oscillate'

ATTR_SPEED = 'speed'
ATTR_SPEED_LIST = 'speed_list'
ATTR_OSCILLATE = 'oscillate'

PROP_TO_ATTR = {
    'speed': ATTR_SPEED,
    'speed_list': ATTR_SPEED_LIST,
    'oscillate': ATTR_OSCILLATE,
    'supported_features': ATTR_SUPPORTED_FEATURES,
}

FAN_SET_SPEED_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_SPEED): cv.string
})

FAN_TURN_ON_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional(ATTR_SPEED): cv.string
})

FAN_TURN_OFF_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids
})

FAN_OSCILLATE_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_OSCILLATE): cv.boolean
})

_LOGGER = logging.getLogger(__name__)


def is_on(hass, entity_id=None):
    """Return if the fans are on based on the statemachine."""
    entity_id = entity_id or ENTITY_ID_ALL_FANS
    return not hass.states.is_state(entity_id, STATE_OFF)


# pylint: disable=too-many-arguments
def turn_on(hass, entity_id=None, speed=None):
    """Turn all or specified fan on."""
    data = {
        key: value for key, value in [
            (ATTR_ENTITY_ID, entity_id),
            (ATTR_SPEED, speed),
        ] if value is not None
    }

    hass.services.call(DOMAIN, SERVICE_TURN_ON, data)


def turn_off(hass, entity_id=None):
    """Turn all or specified fan off."""
    data = {
        ATTR_ENTITY_ID: entity_id,
    }

    hass.services.call(DOMAIN, SERVICE_TURN_OFF, data)


def oscillate(hass, entity_id=None, oscillate=None):
    """Set oscillation on all or specified fan."""
    data = {
        key: value for key, value in [
            (ATTR_ENTITY_ID, entity_id),
            (ATTR_OSCILLATE, oscillate()),
        ] if value is not None
    }

    hass.services.call(DOMAIN, SERVICE_OSCILLATE, data)


def set_speed(hass, entity_id=None, speed=None):
    """Set speed for all or specified fan."""
    data = {
        key: value for key, value in [
            (ATTR_ENTITY_ID, entity_id),
            (ATTR_SPEED, speed),
        ] if value is not None
    }

    hass.services.call(DOMAIN, SERVICE_SET_SPEED, data)


# pylint: disable=too-many-branches, too-many-locals, too-many-statements
def setup(hass, config):
    """Expose fan control via statemachine and services."""
    component = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL, GROUP_NAME_ALL_FANS)
    component.setup(config)

    def handle_fan_service(service):
        """Hande service call for fans."""
        # Get the validated data
        params = service.data.copy()

        # Convert the entity ids to valid fan ids
        target_fans = component.extract_from_service(service)
        params.pop(ATTR_ENTITY_ID, None)

        service_fun = None
        for service_def in [SERVICE_TURN_ON, SERVICE_TURN_OFF,
                            SERVICE_SET_SPEED, SERVICE_OSCILLATE]:
            if service_def == service.service:
                service_fun = service_def
                break

        if service_fun:
            for fan in target_fans:
                getattr(fan, service_fun)(**params)

            for fan in target_fans:
                if fan.should_poll:
                    fan.update_ha_state(True)
            return

    # Listen for fan service calls.
    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))
    hass.services.register(DOMAIN, SERVICE_TURN_ON, handle_fan_service,
                           descriptions.get(SERVICE_TURN_ON),
                           schema=FAN_TURN_ON_SCHEMA)

    hass.services.register(DOMAIN, SERVICE_TURN_OFF, handle_fan_service,
                           descriptions.get(SERVICE_TURN_OFF),
                           schema=FAN_TURN_OFF_SCHEMA)

    hass.services.register(DOMAIN, SERVICE_SET_SPEED, handle_fan_service,
                           descriptions.get(SERVICE_SET_SPEED),
                           schema=FAN_SET_SPEED_SCHEMA)

    hass.services.register(DOMAIN, SERVICE_OSCILLATE, handle_fan_service,
                           descriptions.get(SERVICE_OSCILLATE),
                           schema=FAN_OSCILLATE_SCHEMA)

    return True


class FanEntity(Entity):
    """Representation of a fan."""

    # pylint: disable=no-self-use, abstract-method

    def set_speed(self:Entity, speed:str) -> None:
        """Set the speed of the fan."""
        pass

    def turn_on(self:Entity, speed:str=None) -> None:
        """Turn on the fan."""
        pass

    def turn_off(self:Entity) -> None:
        """Turn off the fan."""
        pass

    def oscillate(self:Entity) -> None:
        """Oscillate the fan."""
        pass

    @property
    def speed_list(self):
        """Get the list of available speeds"""
        return []

    @property
    def state_attributes(self:Entity) -> None:
        """Return optional state attributes."""
        data = {}  # type: dict

        for prop, attr in PROP_TO_ATTR.items():
            value = getattr(self, prop)
            if value is not None:
                data[attr] = value

        return data

    @property
    def supported_features(self:Entity) -> int:
        """Flag supported features."""
        return 0
