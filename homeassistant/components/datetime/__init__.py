"""Component to allow setting date/time as platforms."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, tzinfo
import functools
import logging
from typing import final

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DATE, ATTR_TIME
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.config_validation import (  # noqa: F401
    ENTITY_SERVICE_FIELDS,
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import ATTR_DATETIME, ATTR_TIME_ZONE, DOMAIN, SERVICE_SET_VALUE

SCAN_INTERVAL = timedelta(seconds=30)

ENTITY_ID_FORMAT = DOMAIN + ".{}"

_LOGGER = logging.getLogger(__name__)

__all__ = ["DOMAIN", "DateTimeEntity", "DateTimeEntityDescription"]

ATTR_OFFSET = "offset"


def _split_date_time(config):
    """Split date/time components."""
    datetime_ = config.pop(ATTR_DATETIME, None)
    config[ATTR_DATE] = datetime_.date()
    config[ATTR_TIME] = datetime_.time()
    if (offset := datetime_.utcoffset()) is not None:
        config[ATTR_OFFSET] = offset
    return config


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Date/Time entities."""
    component = hass.data[DOMAIN] = EntityComponent[DateTimeEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_SET_VALUE,
        vol.All(
            vol.Any(
                vol.All(
                    vol.Schema(
                        {
                            vol.Optional(ATTR_DATE): cv.date,
                            vol.Optional(ATTR_TIME): cv.time,
                            vol.Optional(ATTR_TIME_ZONE): cv.time_zone,
                            **ENTITY_SERVICE_FIELDS,
                        }
                    ),
                    cv.has_at_least_one_key(ATTR_DATE, ATTR_TIME),
                ),
                vol.All(
                    vol.Schema(
                        {
                            vol.Required(ATTR_DATETIME): cv.datetime,
                            **ENTITY_SERVICE_FIELDS,
                        }
                    ),
                    _split_date_time,
                ),
            ),
            cv.has_at_least_one_key(*ENTITY_SERVICE_FIELDS),
        ),
        functools.partial(_async_set_value, hass),
    )

    return True


async def _async_set_value(
    hass: HomeAssistant, entity: DateTimeEntity, service_call: ServiceCall
) -> None:
    """Service call wrapper to set a new datetime."""
    date_ = service_call.data.get(ATTR_DATE)
    time_ = service_call.data.get(ATTR_TIME)
    if date_ is None or time_ is None:
        if entity.native_value is None:
            raise ValueError(
                f"Entity {entity.entity_id} has no native value to infer missing "
                "date/time parts"
            )
        if not date_:
            date_ = entity.native_value.date()
        if not time_:
            time_ = entity.native_value.time()

    time_zone: tzinfo | None
    if ATTR_OFFSET in service_call.data:
        time_zone = timezone(service_call.data[ATTR_OFFSET])
    else:
        time_zone_str = service_call.data.get(ATTR_TIME_ZONE, hass.config.time_zone)
        time_zone = dt_util.get_time_zone(time_zone_str)
    return await entity.async_set_value(datetime.combine(date_, time_, time_zone))


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent[DateTimeEntity] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[DateTimeEntity] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


@dataclass
class DateTimeEntityDescription(EntityDescription):
    """A class that describes date/time entities."""


class DateTimeEntity(Entity):
    """Representation of a Date/time entity."""

    entity_description: DateTimeEntityDescription
    _attr_device_class: None = None
    _attr_state: None = None
    _attr_native_value: datetime | None

    @property
    @final
    def device_class(self) -> None:
        """Return entity device class."""
        return None

    @property
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

        return value.astimezone(timezone.utc).isoformat(timespec="seconds")

    @property
    def native_value(self) -> datetime | None:
        """Return the value reported by the datetime."""
        return self._attr_native_value

    def set_value(self, value: datetime) -> None:
        """Change the date/time."""
        raise NotImplementedError()

    async def async_set_value(self, value: datetime) -> None:
        """Change the date/time."""
        await self.hass.async_add_executor_job(self.set_value, value)
