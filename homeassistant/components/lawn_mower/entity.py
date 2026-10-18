"""Base entity for the Lawn mower platform."""

from typing import final, override

from propcache.api import cached_property

from homeassistant.helpers.entity import Entity, EntityDescription

from .const import LawnMowerActivity, LawnMowerEntityFeature


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
    @override
    def state(self) -> str | None:
        """Return the current state."""
        return self.activity

    @cached_property
    def activity(self) -> LawnMowerActivity | None:
        """Return the current lawn mower activity."""
        return self._attr_activity

    @cached_property
    @override
    def supported_features(self) -> LawnMowerEntityFeature:
        """Flag lawn mower features that are supported."""
        return self._attr_supported_features

    def start_mowing(self) -> None:
        """Start or resume mowing."""
        raise NotImplementedError

    async def async_start_mowing(self) -> None:
        """Start or resume mowing."""
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

    def stop(self) -> None:
        """Stop the lawn mower."""
        raise NotImplementedError

    async def async_stop(self) -> None:
        """Stop the lawn mower."""
        await self.hass.async_add_executor_job(self.stop)
