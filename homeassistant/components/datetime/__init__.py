"""Component to allow setting date/time as platforms."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import final

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import FORMAT_DATETIME
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

from .const import (
    ATTR_DATE,
    ATTR_DATETIME,
    ATTR_DAY,
    ATTR_MONTH,
    ATTR_TIME,
    ATTR_TIMESTAMP,
    ATTR_YEAR,
    DOMAIN,
    SERVICE_SET_VALUE,
)

SCAN_INTERVAL = timedelta(seconds=30)

ENTITY_ID_FORMAT = DOMAIN + ".{}"

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

_LOGGER = logging.getLogger(__name__)


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
                        }
                    ),
                    cv.has_at_least_one_key(ATTR_DATE, ATTR_TIME),
                ),
                vol.Schema(
                    {
                        vol.Required(ATTR_DATETIME): cv.datetime,
                    }
                ),
                vol.Schema(
                    {
                        vol.Required(ATTR_TIMESTAMP): vol.All(
                            vol.Coerce(float),
                            dt_util.utc_from_timestamp,
                            dt_util.as_local,
                        ),
                    }
                ),
            ),
            _split_date_time,
        ),
        _async_set_value,
    )

    return True


async def _async_set_value(entity: DateTimeEntity, service_call: ServiceCall) -> None:
    """Service call wrapper to set a new datetime."""
    date_ = service_call.data.get(ATTR_DATE)
    time_ = service_call.data.get(ATTR_TIME)
    if date_ is None or time_ is None:
        if entity.native_value is None:
            raise ValueError(
                "Entity has no native value to infer missing date/time parts"
            )
        if not date_:
            date_ = entity.native_value.date()
        if not time_:
            time_ = entity.native_value.time()

    return await entity.async_set_value(datetime.combine(date_, time_))


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
    _attr_value: None = None
    _attr_year: None = None
    _attr_month: None = None
    _attr_day: None = None
    _attr_timestamp: None = None
    _attr_state: None = None

    @property
    @final
    def state_attributes(self) -> dict[str, int | float]:
        """Return the state attributes."""
        state_attr: dict[str, int | float | None] = {
            ATTR_DAY: self.day,
            ATTR_MONTH: self.month,
            ATTR_YEAR: self.year,
            ATTR_TIMESTAMP: self.timestamp,
        }
        return {k: v for k, v in state_attr.items() if v is not None}

    @property
    @final
    def state(self) -> str | None:
        """Return the entity state."""
        if self.native_value is None:
            return None
        return self.native_value.strftime(FORMAT_DATETIME)

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
