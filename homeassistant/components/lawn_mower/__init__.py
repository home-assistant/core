"""The lawn mower integration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import final

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
    SERVICE_DOCK,
    SERVICE_PAUSE,
    SERVICE_START_MOWING,
    LawnMowerActivity,
    LawnMowerEntityFeature,
)

SCAN_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)


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

    return True


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
    _attr_activity: LawnMowerActivity | None = None
    _attr_supported_features: LawnMowerEntityFeature = LawnMowerEntityFeature(0)

    @final
    @property
    def state(self) -> str | None:
        """Return the current state."""
        if (activity := self.activity) is None:
            return None
        return str(activity)

    @property
    def activity(self) -> LawnMowerActivity | None:
        """Return the current lawn mower activity."""
        return self._attr_activity

    @property
    def supported_features(self) -> LawnMowerEntityFeature:
        """Flag lawn mower features that are supported."""
        return self._attr_supported_features

    def start_mowing(self) -> None:
        """Start or resume mowing."""
        raise NotImplementedError()

    async def async_start_mowing(self) -> None:
        """Start or resume mowing."""
        await self.hass.async_add_executor_job(self.start_mowing)

    def dock(self) -> None:
        """Dock the mower."""
        raise NotImplementedError()

    async def async_dock(self) -> None:
        """Dock the mower."""
        await self.hass.async_add_executor_job(self.dock)

    def pause(self) -> None:
        """Pause the lawn mower."""
        raise NotImplementedError()

    async def async_pause(self) -> None:
        """Pause the lawn mower."""
        await self.hass.async_add_executor_job(self.pause)
