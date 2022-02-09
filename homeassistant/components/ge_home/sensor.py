"""GE Home Sensor Entities"""
import async_timeout
import logging
from typing import Callable
import voluptuous as vol
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform

from .const import (
    DOMAIN, 
    SERVICE_SET_TIMER, 
    SERVICE_CLEAR_TIMER, 
    SERVICE_SET_INT_VALUE
)
from .entities import GeErdSensor
from .update_coordinator import GeHomeUpdateCoordinator

ATTR_DURATION = "duration"
ATTR_VALUE = "value"

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: Callable):
    """GE Home sensors."""
    _LOGGER.debug('Adding GE Home sensors')
    coordinator: GeHomeUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    # Get the platform
    platform = entity_platform.async_get_current_platform()

    # This should be a NOP, but let's be safe
    with async_timeout.timeout(20):
        await coordinator.initialization_future
    _LOGGER.debug('Coordinator init future finished')

    apis = list(coordinator.appliance_apis.values())
    _LOGGER.debug(f'Found {len(apis):d} appliance APIs')
    entities = [
        entity
        for api in apis
        for entity in api.entities
        if isinstance(entity, GeErdSensor) and entity.erd_code in api.appliance._property_cache
    ]
    _LOGGER.debug(f'Found {len(entities):d} sensors')
    async_add_entities(entities)

    # register set_timer entity service
    platform.async_register_entity_service(
    SERVICE_SET_TIMER,
    {
        vol.Required(ATTR_DURATION): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=360)
        )
    },
    set_timer)

    # register clear_timer entity service
    platform.async_register_entity_service(SERVICE_CLEAR_TIMER, {}, 'clear_timer')

    # register set_value entity service
    platform.async_register_entity_service(
    SERVICE_SET_INT_VALUE,
    {
        vol.Required(ATTR_VALUE): vol.All(
            vol.Coerce(int), vol.Range(min=0)
        )
    },
    set_int_value)    

async def set_timer(entity, service_call):
    ts = timedelta(minutes=int(service_call.data['duration']))
    await entity.set_timer(ts)

async def set_int_value(entity, service_call):
    await entity.set_value(int(service_call.data['value']))