"""Component to allow setting date/time as platforms."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from functools import cached_property
import logging
from typing import final

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import ATTR_DATETIME, DOMAIN, SERVICE_SET_VALUE

SCAN_INTERVAL = timedelta(seconds=30)

ENTITY_ID_FORMAT = DOMAIN + ".{}"

_LOGGER = logging.getLogger(__name__)

__all__ = ["ATTR_DATETIME", "DOMAIN", "DateTimeEntity", "DateTimeEntityDescription"]


async def _async_set_value(entity: DateTimeEntity, service_call: ServiceCall) -> None:
    """Service call wrapper to set a new date/time."""
    value: datetime = service_call.data[ATTR_DATETIME]
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt_util.get_default_time_zone())
    return await entity.async_set_value(value)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Date/Time entities."""
    component = hass.data[DOMAIN] = EntityComponent[DateTimeEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_SET_VALUE,
        {
            vol.Required(ATTR_DATETIME): cv.datetime,
        },
        _async_set_value,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent[DateTimeEntity] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[DateTimeEntity] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


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
    def device_class(self) -> None:
        """Return entity device class."""
        return None

    @cached_property
    @final
    def state_attributes(self) -> None:
        """Return the state attributes."""
        return None

    @property
    @final
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
