"""Base entity for the Date platform."""

from datetime import date
from typing import final, override

from propcache.api import cached_property

from homeassistant.helpers.entity import Entity, EntityDescription


class DateEntityDescription(EntityDescription, frozen_or_thawed=True):
    """A class that describes date entities."""


CACHED_PROPERTIES_WITH_ATTR_ = {"native_value"}


class DateEntity(Entity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """Representation of a Date entity."""

    entity_description: DateEntityDescription
    _attr_device_class: None
    _attr_native_value: date | None
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
    def native_value(self) -> date | None:
        """Return the value reported by the date."""
        return self._attr_native_value

    def set_value(self, value: date) -> None:
        """Change the date."""
        raise NotImplementedError

    async def async_set_value(self, value: date) -> None:
        """Change the date."""
        await self.hass.async_add_executor_job(self.set_value, value)
