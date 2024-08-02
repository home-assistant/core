"""The lawn mower integration."""

from __future__ import annotations

from datetime import timedelta
from functools import cached_property
import logging
from typing import final

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
    SERVICE_CANCEL,
    SERVICE_DOCK,
    SERVICE_FIXED_MOWING,
    SERVICE_PAUSE,
    SERVICE_RESUME,
    SERVICE_START_MOWING,
    LawnMowerActivity,
    LawnMowerEntityFeature,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=60)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the lawn_mower component."""
    component = hass.data[DOMAIN] = EntityComponent[LawnMowerEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_START_MOWING,
        {},
        "async_start_mowing",
        [LawnMowerEntityFeature.START_MOWING],
    )
    component.async_register_entity_service(
        SERVICE_PAUSE, {}, "async_pause", [LawnMowerEntityFeature.PAUSE]
    )
    component.async_register_entity_service(
        SERVICE_DOCK, {}, "async_dock", [LawnMowerEntityFeature.DOCK]
    )
    component.async_register_entity_service(
        SERVICE_RESUME, {}, "async_resume", [LawnMowerEntityFeature.RESUME]
    )
    component.async_register_entity_service(
        SERVICE_CANCEL, {}, "async_cancel", [LawnMowerEntityFeature.CANCEL]
    )
    component.async_register_entity_service(
        SERVICE_FIXED_MOWING,
        {},
        "async_fixed_mowing",
        [LawnMowerEntityFeature.FIXED_MOWING],
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up lawn mower devices."""
    component: EntityComponent[LawnMowerEntity] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[LawnMowerEntity] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


class LawnMowerEntityEntityDescription(EntityDescription, frozen_or_thawed=True):
    """A class that describes lawn mower entities."""


CACHED_PROPERTIES_WITH_ATTR_ = {
    "activity",
    "supported_features",
}


class LawnMowerEntity(Entity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """Base class for lawn mower entities."""

    entity_description: LawnMowerEntityEntityDescription
    _attr_activity: LawnMowerActivity | None = None
    _attr_supported_features: LawnMowerEntityFeature = LawnMowerEntityFeature(0)

    @final
    @property
    def state(self) -> str | None:
        """Return the current state."""
        if (activity := self.activity) is None:
            return None
        return str(activity)

    @cached_property
    def activity(self) -> LawnMowerActivity | None:
        """Return the current lawn mower activity."""
        return self._attr_activity

    @cached_property
    def supported_features(self) -> LawnMowerEntityFeature:
        """Flag lawn mower features that are supported."""
        return self._attr_supported_features

    def start_mowing(self) -> None:
        """Start mowing."""
        raise NotImplementedError

    async def async_start_mowing(self) -> None:
        """Start mowing."""
        await self.hass.async_add_executor_job(self.start_mowing)

    def dock(self) -> None:
        """Dock the mower."""
        raise NotImplementedError

    async def async_dock(self) -> None:
        """Dock the mower."""
        await self.hass.async_add_executor_job(self.dock)

    def pause(self) -> None:
        """Pause the lawn mower."""
        raise NotImplementedError

    async def async_pause(self) -> None:
        """Pause the lawn mower."""
        await self.hass.async_add_executor_job(self.pause)

    def resume(self) -> None:
        """Resume mowing."""
        raise NotImplementedError

    async def async_resume(self) -> None:
        """Resume mowing."""
        await self.hass.async_add_executor_job(self.resume)

    def cancel(self) -> None:
        """Cancel/Stop lawn mowing."""
        raise NotImplementedError

    async def async_cancel(self) -> None:
        """Cancel/Stop lawn mowing."""
        await self.hass.async_add_executor_job(self.cancel)

    def fixed_mowing(self) -> None:
        """Start mowing around a fixed spot."""
        raise NotImplementedError

    async def async_fixed_mowing(self) -> None:
        """Start mowing around a fixed spot."""
        await self.hass.async_add_executor_job(self.fixed_mowing)
