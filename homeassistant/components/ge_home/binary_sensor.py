"""GE Home Sensor Entities"""
import async_timeout
import logging
from typing import Callable

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .entities import GeErdBinarySensor
from .update_coordinator import GeHomeUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: Callable):
    """GE Home sensors."""

    coordinator: GeHomeUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    # This should be a NOP, but let's be safe
    with async_timeout.timeout(20):
        await coordinator.initialization_future

    apis = coordinator.appliance_apis.values()
    _LOGGER.debug(f'Found {len(apis):d} appliance APIs')
    entities = [
        entity
        for api in apis
        for entity in api.entities
        if isinstance(entity, GeErdBinarySensor) and not isinstance(entity, SwitchEntity)
    ]
    _LOGGER.debug(f'Found {len(entities):d} binary sensors  ')
    async_add_entities(entities)
