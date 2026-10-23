"""Base entity for the Time platform."""

from datetime import time
from typing import final, override

from propcache.api import cached_property

from homeassistant.helpers.entity import Entity, EntityDescription


class TimeEntityDescription(EntityDescription, frozen_or_thawed=True):
    """A class that describes time entities."""


CACHED_PROPERTIES_WITH_ATTR_ = {"native_value"}


class TimeEntity(Entity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """Representation of a Time entity."""

    entity_description: TimeEntityDescription
    _attr_native_value: time | None = None
    _attr_device_class: None = None
    _attr_state: None = None

    @cached_property
    @final
    @override
    def device_class(self) -> None:
        """Return the device class for the entity."""
        return None

    @cached_property
    @final
    @override
    def state_attributes(self) -> None:
        """Return the state attributes."""
        return None

    @property
    @final
    @override
    def state(self) -> str | None:
        """Return the entity state."""
        if self.native_value is None:
            return None
        return self.native_value.isoformat()

    @cached_property
    def native_value(self) -> time | None:
        """Return the value reported by the time."""
        return self._attr_native_value

    def set_value(self, value: time) -> None:
        """Change the time."""
        raise NotImplementedError

    async def async_set_value(self, value: time) -> None:
        """Change the time."""
        await self.hass.async_add_executor_job(self.set_value, value)
