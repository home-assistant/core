"""The lawn mower integration."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum, IntFlag
import logging
from typing import Any, final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

SCAN_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)

"""The LawnMowerEntity base should return the activity attribute as state.
Mower entity specific attributes:

    activity: a string enum, with the following attributes:
        error: the mower is in error and needs human intervention
        paused: the mower is paused away from the dock, no activity will be resumed
        mowing: the mower is currently mowing
        docked_schedule_enabled: the mower is docked and waiting for next schedule start
        docked_schedule_disabled: the mower is docked and the schedule is disabled

Mower entity services:

    start_mowing
    dock
    pause - this stops the mower where it is, for instance if you notice the lawn is not clear
    enable_schedule
    disable_schedule

"""

SERVICE_START_MOWING = "start_mowing"

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    component = hass.data[DOMAIN] = EntityComponent[LawnMowerEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)
    
    component.async_register_entity_service(
        SERVICE_START_MOWING, {}, "async_service_start_mowing"
    )


class LawnMowerActivity(Enum):
    ERROR = "error",
    PAUSED = "paused",
    MOWING = "mowing",
    DOCKED_SCHEDULE_ENABLED = "docked_schedule_enabled",
    DOCKED_SCHEDULE_DISABLED = "docked_schedule_disabled"

class LawnMowerEntityFeature(IntFlag):
    """Supported features of the lawn mower entity"""

@dataclass
class LawnMowerEntityEntityDescription(EntityDescription):
    """A class that describes lawn mower entities."""

    
class LawnMowerEntity(Entity):
    """Base class for lawn mower entities"""

    entity_description: LawnMowerEntityEntityDescription
    _attr_activity: LawnMowerActivity | None = None
    
    @final
    @property
    def state(self) -> str | None:
        """Return the current state."""
        return self._attr_activity
    
    @property
    def activity(self) -> LawnMowerActivity | None:
        """Return current activity"""
        
    def start_mowing(self) -> None:
        """Start mowing."""
        raise NotImplementedError()
        
    async def async_start_mowing(self, **kwargs: Any) -> None:
        """Start mowing."""
        await self.hass.async_add_executor_job(
            ft.partial(self.start_mowing, **kwargs)
        )
        
        
        
async def async_service_start_mowing(entity: LawnMowerEntity, service: ServiceCall) -> None:
    """Handle start mowing service."""
    kwargs = {
                key: value
                for key, value in service.data.items()
            }
    await entity.async_start_mowing(**kwargs)
    


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up lawn mower devices."""
    component: EntityComponent[LawnMowerEntity] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[LawnMowerEntity] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)
