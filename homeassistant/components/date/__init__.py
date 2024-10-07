"""Component to allow setting date as platforms."""

from __future__ import annotations

from datetime import date, timedelta
import logging
from typing import final

from propcache import cached_property
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DATE
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN, SERVICE_SET_VALUE

_LOGGER = logging.getLogger(__name__)

DATA_COMPONENT: HassKey[EntityComponent[DateEntity]] = HassKey(DOMAIN)
ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=30)


__all__ = ["DOMAIN", "DateEntity", "DateEntityDescription"]


async def _async_set_value(entity: DateEntity, service_call: ServiceCall) -> None:
    """Service call wrapper to set a new date."""
    return await entity.async_set_value(service_call.data[ATTR_DATE])


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Date entities."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[DateEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_SET_VALUE, {vol.Required(ATTR_DATE): cv.date}, _async_set_value
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)


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
    def device_class(self) -> None:
        """Return the device class for the entity."""
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
