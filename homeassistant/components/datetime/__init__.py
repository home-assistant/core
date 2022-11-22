"""Component to allow setting date/time as platforms."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import functools
import logging
from typing import final

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
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

from .const import (
    ATTR_DATE,
    ATTR_DATETIME,
    ATTR_DAY,
    ATTR_HOUR,
    ATTR_MINUTE,
    ATTR_MONTH,
    ATTR_SECOND,
    ATTR_TIME,
    ATTR_TIME_ZONE,
    ATTR_TIMESTAMP,
    ATTR_YEAR,
    DOMAIN,
    SERVICE_SET_VALUE,
)

SCAN_INTERVAL = timedelta(seconds=30)

ENTITY_ID_FORMAT = DOMAIN + ".{}"

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

_LOGGER = logging.getLogger(__name__)

__all__ = ["DOMAIN", "DateTimeEntity", "DateTimeEntityDescription"]


def _split_date_time(config):
    """Split date/time components."""
    if datetime_ := (
        config.pop(ATTR_DATETIME, None) or config.get(ATTR_TIMESTAMP, None)
    ):
        config[ATTR_DATE] = datetime_.date()
        config[ATTR_TIME] = datetime_.time()
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
                vol.Schema(
                    {
                        vol.Required(ATTR_DATETIME): cv.datetime,
                        vol.Optional(ATTR_TIME_ZONE): cv.time_zone,
                        **ENTITY_SERVICE_FIELDS,
                    }
                ),
                vol.Schema(
                    {
                        vol.Required(ATTR_TIMESTAMP): vol.All(
                            vol.Coerce(float),
                            dt_util.utc_from_timestamp,
                            dt_util.as_local,
                        ),
                        vol.Optional(ATTR_TIME_ZONE): cv.time_zone,
                        **ENTITY_SERVICE_FIELDS,
                    }
                ),
            ),
            cv.has_at_least_one_key(*ENTITY_SERVICE_FIELDS),
            _split_date_time,
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
    time_zone = dt_util.get_time_zone(
        service_call.data.get(ATTR_TIME_ZONE, hass.config.time_zone)
    )
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
    _attr_native_value: datetime | None

    @property
    @final
    def state_attributes(self) -> dict[str, int | float]:
        """Return the state attributes."""
        state_attr: dict[str, int | float | None] = {
            ATTR_DAY: self.day,
            ATTR_MONTH: self.month,
            ATTR_YEAR: self.year,
            ATTR_HOUR: self.hour,
            ATTR_MINUTE: self.minute,
            ATTR_SECOND: self.second,
            ATTR_TIMESTAMP: self.timestamp,
        }
        return {k: v for k, v in state_attr.items() if v is not None}

    @property
    @final
    def state(self) -> str | None:
        """Return the entity state."""
        value = self.native_value
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError(
                f"Invalid datetime: {self.entity_id} provides state '{value}', "
                "which is missing timezone information"
            )
        if value.tzinfo != timezone.utc:
            value = value.astimezone(timezone.utc)

        return value.isoformat(timespec="seconds")

    @property
    @final
    def day(self) -> int | None:
        """Return day from value."""
        if self.native_value is None:
            return None
        return self.native_value.day

    @property
    @final
    def month(self) -> int | None:
        """Return month from value."""
        if self.native_value is None:
            return None
        return self.native_value.month

    @property
    @final
    def year(self) -> int | None:
        """Return year from value."""
        if self.native_value is None:
            return None
        return self.native_value.year

    @property
    @final
    def hour(self) -> int | None:
        """Return hour from value."""
        if self.native_value is None:
            return None
        return self.native_value.hour

    @property
    @final
    def minute(self) -> int | None:
        """Return minute from value."""
        if self.native_value is None:
            return None
        return self.native_value.minute

    @property
    @final
    def second(self) -> int | None:
        """Return second from value."""
        if self.native_value is None:
            return None
        return self.native_value.second

    @property
    @final
    def timestamp(self) -> float | None:
        """Return UNIX timestamp of value."""
        if self.native_value is None:
            return None
        return self.native_value.timestamp()

    @property
    def native_value(self) -> datetime | None:
        """Return the value reported by the datetime."""
        return self._attr_native_value

    def set_value(self, dt_value: datetime) -> None:
        """Change the date/time."""
        raise NotImplementedError()

    async def async_set_value(self, dt_value: datetime) -> None:
        """Change the date/time."""
        await self.hass.async_add_executor_job(self.set_value, dt_value)
