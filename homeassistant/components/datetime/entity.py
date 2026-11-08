"""Base entity for the Date/Time platform."""

from datetime import UTC, datetime
from typing import final, override

from propcache.api import cached_property

from homeassistant.helpers.entity import Entity, EntityDescription


class DateTimeEntityDescription(EntityDescription, frozen_or_thawed=True):
    """A class that describes date/time entities."""


CACHED_PROPERTIES_WITH_ATTR_ = {
    "native_value",
}


class DateTimeEntity(Entity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """Representation of a Date/time entity."""

    entity_description: DateTimeEntityDescription
    _attr_device_class: None = None
    _attr_state: None = None
    _attr_native_value: datetime | None

    @cached_property
    @final
    @override
    def device_class(self) -> None:
        """Return entity device class."""
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
        if (value := self.native_value) is None:
            return None
        if value.tzinfo is None:
            raise ValueError(
                f"Invalid datetime: {self.entity_id} provides state '{value}', "
                "which is missing timezone information"
            )

        return value.astimezone(UTC).isoformat(timespec="seconds")

    @cached_property
    def native_value(self) -> datetime | None:
        """Return the value reported by the datetime."""
        return self._attr_native_value

    def set_value(self, value: datetime) -> None:
        """Change the date/time."""
        raise NotImplementedError

    async def async_set_value(self, value: datetime) -> None:
        """Change the date/time."""
        await self.hass.async_add_executor_job(self.set_value, value)
