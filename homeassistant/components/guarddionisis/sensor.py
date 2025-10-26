from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from threading import Thread
from homeassistant.components.guarddionisis.util.util import DBAccess

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType


from homeassistant.components.sensor import (
    SensorEntity,

)

from .const import ATTR_ALARM_STATUS, ATTR_COUNTER_VALUE, CONF_ID, CONF_TYPE, DOMAIN, LOGGER, SERVICE_CLEAR_VIDEOS, SERVICE_DEINCREMENT_COUNTER, SERVICE_INCREMENT_COUNTER, SERVICE_SET_ALARM_STATUS, SERVICE_SET_COUNTER
_LOGGER = logging.getLogger(__name__)


import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA

from homeassistant.const import (
    CONF_ID,
    CONF_NAME
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "guarddionisis"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ID): cv.positive_int,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_TYPE, default='area'): cv.string,

    }
)

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up a guard control panel."""
    name = config.get(CONF_NAME)
    id = config.get(CONF_ID)
    type = config.get(CONF_TYPE)
    GuardSensor = GuardSensorEntity(hass, name, id, type)
    async_add_entities([GuardSensor])

    # SERVICE_SET_ALARM_STATUS = "set_alarm_status"
    # SERVICE_CLEAR_VIDEOS = "clear_videos"
    # SERVICE_SET_COUNTER = "set_counter"
    # SERVICE_INCREMENT_COUNTER = "increment_counter"
    # SERVICE_DEINCREMENT_COUNTER = "deincrement_counter"

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_SET_ALARM_STATUS,
        {
            vol.Required(ATTR_ALARM_STATUS, default=0): vol.Coerce(int)
        },
        "set_alarm_status",
        # [SUPPORT_OPEN_DOOR],
    )

    platform.async_register_entity_service(
        SERVICE_CLEAR_VIDEOS,
        {},
        "clear_videos",
        # [SUPPORT_OPEN_DOOR],
    )
    platform.async_register_entity_service(
        SERVICE_SET_COUNTER,
        {
            vol.Required(ATTR_COUNTER_VALUE, default=0): vol.Coerce(int)
        },        
        "set_counter",
        # [SUPPORT_OPEN_DOOR],
    )
    platform.async_register_entity_service(
        SERVICE_INCREMENT_COUNTER,
        {},
        "increment_counter",
        # [SUPPORT_OPEN_DOOR],
    )
    platform.async_register_entity_service(
        SERVICE_DEINCREMENT_COUNTER,
        {},
        "deincrement_counter",
        # [SUPPORT_OPEN_DOOR],
    )


class GuardSensorEntity(SensorEntity):
    """Represent an Guard sensor."""

    def __init__(
        self,
        hass,
        name,
        id,
        type
    ):
        self.theDB = DBAccess('/home/dionisis/Database/TrackedObjectsDim.db')
        _LOGGER.debug("Setting up dionisissensor...")
        self._hass = hass
        self._name = name
        self._id = id
        self._type = type
        self._state = self.theDB.getAreaCounter(id) if self._type =='area' else self.theDB.getRegionCounter(id) if self._type =='region' else self.theDB.getAlarmSensorStatus(id)

    @property
    def name(self):
        """Return the name of the alarm."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "" if self._type == "alarm" else "people"
 
    @property
    def should_poll(self):
        return False

    # async def async_update(self):
    #     """Fetch new state data for the sensor."""
    #     #return
    #     #self._state = self.theDB.getAreaCounter(self._id) if self._type =='area' else self.theDB.getRegionCounter(self._id) if self._type =='region' else self.theDB.getAlarmSensorStatus(self._id)
    #     self.async_update_ha_state()

    async def async_update(self):
        # Manually update the state based on your custom asynchronous logic.
        new_state = await self.async_calculate_new_state()
        if new_state != self._state:
            self._state = new_state
            self.async_write_ha_state()

    async def async_calculate_new_state(self):
        # Replace this with your custom asynchronous logic to determine the new state.
        # For example, querying an external system, calculating, etc.
        return self.theDB.getAreaCounter(self._id) if self._type =='area' else self.theDB.getRegionCounter(self._id) if self._type =='region' else self.theDB.getAlarmSensorStatus(self._id)


    async def set_alarm_status(self,alarm_status):
        try:
           self.theDB.setAlarmSensorStatus(self._id,alarm_status)
           self._state = alarm_status
        #    self.async_update()
           await self.async_write_ha_state()
        except:
            lll=2

    async def clear_videos(self):
        try:
           lll=1    
        except:
            lll=2

    async def set_counter(self,value):
        print("set_counter")
        try:
           lll=1
           if (self._type =='area'):
            self.theDB.setAreaCounter(self._id,value)
           elif (self._type == 'region'):
            self.theDB.setRegionCounter(self._id,value) 
           elif (self._type == 'alarm'):
            self.theDB.setAlarmSensorStatus(self._id,value)       
           self._state = value
           await self.async_write_ha_state()
        except:
            lll=2

    async def increment_counter(self):
        try:
           if (self._type =='area'):
            tt =  self.theDB.getAreaCounter(self._id)
            tt = str(int(tt)+1)
            self.theDB.setAreaCounter(self._id,tt)
            self._state = tt

           else:
            tt =  self.theDB.getRegionCounter(self._id)
            tt = str(int(tt)+1)
            self.theDB.setRegionCounter(self._id,tt)
            self._state = tt
           await self.async_write_ha_state()
        #    self.async_update()

        except:
            lll=2

    async def deincrement_counter(self):
        try:
           if (self._type =='area'):
            tt =  self.theDB.getAreaCounter(self._id)
            tt = str(int(tt)-1)
            self.theDB.setAreaCounter(self._id,tt)
            self._state = tt
           else:
            tt =  self.theDB.getRegionCounter(self._id)
            tt = str(int(tt)-1)
            self.theDB.setRegionCounter(self._id,tt)
            self._state = tt
           await self.async_write_ha_state()

        except:
            lll=2
