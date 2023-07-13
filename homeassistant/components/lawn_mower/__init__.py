"""The lawn mower integration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import Enum, IntFlag
from functools import partial
import logging
from typing import Any, final

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

SCAN_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)

SERVICE_START_MOWING = "start_mowing"
SERVICE_PAUSE = "pause"
SERVICE_ENABLE_SCHEDULE = "enable_schedule"
SERVICE_DISABLE_SCHEDULE = "disable_schedule"
SERVICE_DOCK = "dock"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the lawn_mower component."""
    component = hass.data[DOMAIN] = EntityComponent[LawnMowerEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_START_MOWING,
        {},
        "async_service_start_mowing",
        [LawnMowerEntityFeature.START_MOWING],
    )
    component.async_register_entity_service(
        SERVICE_PAUSE, {}, "async_service_pause", [LawnMowerEntityFeature.PAUSE]
    )
    component.async_register_entity_service(
        SERVICE_ENABLE_SCHEDULE,
        {},
        "async_service_enable_schedule",
        [LawnMowerEntityFeature.ENABLE_SCHEDULE],
    )
    component.async_register_entity_service(
        SERVICE_DISABLE_SCHEDULE,
        {},
        "async_service_disable_schedule",
        [LawnMowerEntityFeature.DISABLE_SCHEDULE],
    )
    component.async_register_entity_service(
        SERVICE_DOCK, {}, "async_service_dock", [LawnMowerEntityFeature.DOCK]
    )

    return True


class LawnMowerActivity(Enum):
    """Activity state of the lawn mower entity."""

    ERROR = "error"
    PAUSED = "paused"
    MOWING = "mowing"
    DOCKING = "docking"
    DOCKED_SCHEDULE_DISABLED = "docked_schedule_disabled"
    DOCKED_SCHEDULE_ENABLED = "docked_schedule_enabled"


class LawnMowerEntityFeature(IntFlag):
    """Supported features of the lawn mower entity."""

    START_MOWING = 1
    PAUSE = 2
    DOCK = 4
    ENABLE_SCHEDULE = 8
    DISABLE_SCHEDULE = 16


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up lawn mower devices."""
    component: EntityComponent[LawnMowerEntity] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[LawnMowerEntity] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


@dataclass
class LawnMowerEntityEntityDescription(EntityDescription):
    """A class that describes lawn mower entities."""


class LawnMowerEntity(Entity):
    """Base class for lawn mower entities."""

    entity_description: LawnMowerEntityEntityDescription
    _activity: str | None = None
    _attr_supported_features: LawnMowerEntityFeature

    @final
    @property
    def state(self) -> str | None:
        """Return the current state."""
        return self._activity

    @property
    def supported_features(self) -> LawnMowerEntityFeature:
        """Flag lawn mower features that are supported."""
        return self._attr_supported_features

    def start_mowing(self) -> None:
        """Start mowing."""
        raise NotImplementedError()

    async def async_start_mowing(self) -> None:
        """Start mowing."""
        await self.hass.async_add_executor_job(partial(self.start_mowing))

    def dock(self) -> None:
        """Dock the mower."""
        raise NotImplementedError()

    async def async_dock(self) -> None:
        """Dock the mower."""
        await self.hass.async_add_executor_job(partial(self.dock))

    def pause(self) -> None:
        """Pause the lawn mower."""
        raise NotImplementedError()

    async def async_pause(self) -> None:
        """Pause the lawn mower."""
        await self.hass.async_add_executor_job(partial(self.pause))

    def enable_schedule(self) -> None:
        """Enable the schedule for the lawn mower."""
        raise NotImplementedError()

    async def async_enable_schedule(self, **kwargs: Any) -> None:
        """Enable the schedule for the lawn mower."""
        await self.hass.async_add_executor_job(partial(self.enable_schedule, **kwargs))

    def disable_schedule(self) -> None:
        """Disable the schedule for the lawn mower."""
        raise NotImplementedError()

    async def async_disable_schedule(self) -> None:
        """Disable the schedule for the lawn mower."""
        await self.hass.async_add_executor_job(partial(self.disable_schedule))
