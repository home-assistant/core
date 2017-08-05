"""
Support for Etherrain Sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.etherrain/
"""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import STATE_UNKNOWN
from homeassistant.helpers.entity import Entity
import homeassistant.components.etherrain as er
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['etherrain']

CONF_INCLUDE_ARCHIVED = "include_archived"

DEFAULT_INCLUDE_ARCHIVED = False

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_INCLUDE_ARCHIVED, default=DEFAULT_INCLUDE_ARCHIVED):
        cv.boolean,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    include_archived = config.get(CONF_INCLUDE_ARCHIVED)
    valve_id = config.get("valve_id")
    valve_name = config.get("name")

    add_devices([ERValveSensors(valve_id,valve_name)])


class ERValveSensors(Entity):

    def __init__(self, valve_id, valve_name):
        self._valve_id = valve_id
        self._valve_name = valve_name
        self._state = None

    @property
    def name(self):
        return self._valve_name

    @property
    def state(self):
        return self._state

    def update(self):
        state = er.get_state(self._valve_id)
        
        if state == 1:
            self._state = True
        else:
            self._state = False
        # _LOGGER.info("update etherrain switch {0} - {1}".format(self._valve_id, self._state))

    @property
    def is_on(self):
        # _LOGGER.info("is_on: etherrain switch {0} - {1}".format(self._valve_id, self._state))
        return self._state
