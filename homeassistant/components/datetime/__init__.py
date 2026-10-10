"""Component to allow setting date/time as platforms."""

from datetime import UTC, datetime, timedelta
import logging
from typing import final, override

from propcache.api import cached_property

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import (  # noqa: F401
    ATTR_DATETIME,
    DATA_COMPONENT,
    DOMAIN,
    SERVICE_SET_VALUE,
)
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=30)


__all__ = ["ATTR_DATETIME", "DOMAIN", "DateTimeEntity", "DateTimeEntityDescription"]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Date/Time entities."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[DateTimeEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)


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
