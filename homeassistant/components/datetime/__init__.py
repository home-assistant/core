"""Component to allow setting date/time as platforms."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import logging
from typing import Any, final

import voluptuous as vol

from homeassistant.backports.enum import StrEnum
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

from .const import (
    ATTR_DATE,
    ATTR_DATETIME,
    ATTR_DAY,
    ATTR_HAS_DATE,
    ATTR_HAS_TIME,
    ATTR_MODE,
    ATTR_MONTH,
    ATTR_TIME,
    ATTR_TIMESTAMP,
    ATTR_YEAR,
    DOMAIN,
    SERVICE_SET_DATETIME,
)

SCAN_INTERVAL = timedelta(seconds=30)

ENTITY_ID_FORMAT = DOMAIN + ".{}"

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

_LOGGER = logging.getLogger(__name__)

FMT_DATE = "%Y-%m-%d"
FMT_TIME = "%H:%M:%S"
FMT_DATETIME = f"{FMT_DATE} {FMT_TIME}"

# mypy: disallow-any-generics


def validate_svc_attrs_and_split_date_time(config):
    """Validate set_datetime service attributes and split date/time components."""
    has_date_or_time_attr = any(key in config for key in (ATTR_DATE, ATTR_TIME))
    if (
        sum([has_date_or_time_attr, ATTR_DATETIME in config, ATTR_TIMESTAMP in config])
    ) > 1:
        raise vol.Invalid(f"Cannot use together: {', '.join(config.keys())}")
    if datetime_ := (
        config.pop(ATTR_DATETIME, None) or config.get(ATTR_TIMESTAMP, None)
    ):
        assert isinstance(datetime_, datetime)
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
        SERVICE_SET_DATETIME,
        vol.All(
            vol.Schema(
                {
                    vol.Optional(ATTR_DATE): cv.date,
                    vol.Optional(ATTR_TIME): cv.time,
                    vol.Optional(ATTR_DATETIME): cv.datetime,
                    vol.Optional(ATTR_TIMESTAMP): vol.All(
                        vol.Coerce(float), dt_util.utc_from_timestamp, dt_util.as_local
                    ),
                },
                extra=vol.ALLOW_EXTRA,
            ),
            cv.has_at_least_one_key(
                ATTR_DATE, ATTR_TIME, ATTR_DATETIME, ATTR_TIMESTAMP
            ),
            validate_svc_attrs_and_split_date_time,
        ),
        async_set_datetime,
    )

    return True


async def async_set_datetime(entity: DateTimeEntity, service_call: ServiceCall) -> None:
    """Service call wrapper to set a new datetime."""
    date_: date | None = service_call.data.get(ATTR_DATE)
    time_: time | None = service_call.data.get(ATTR_TIME)

    # Raise if input is datetime but entity doesn't accept datetime
    if date_ and time_ and entity.mode != DateTimeMode.DATETIME:
        component = "`date`" if entity.has_date else "`time`"
        raise vol.Invalid(f"Service data should only include {component} component")

    # For date/time mode we need both `date` and `time` attributes
    if entity.mode == DateTimeMode.DATETIME:
        # If only one date/time component is set and entity value is None, we can't
        # fill in data and the user must include both components
        if (bool(date_) ^ bool(time_)) and not isinstance(entity.value, datetime):
            raise vol.Invalid(
                "Service data must include both `date` and `time` component"
            )

        # Either both date and time components are set or entity value is a valid date
        # time so we can fill in the unset component only if needed
        if not date_:
            assert isinstance(entity.value, datetime)
            date_ = entity.value.date()

        if not time_:
            assert isinstance(entity.value, datetime)
            time_ = entity.value.time()

        return await entity.async_set_datetime(
            datetime.combine(date_, time_, dt_util.DEFAULT_TIME_ZONE)
        )

    if date_:
        return await entity.async_set_datetime(date_)

    if time_:
        return await entity.async_set_datetime(time_)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent[DateTimeEntity] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[DateTimeEntity] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


class DateTimeMode(StrEnum):
    """Modes for date/time entities."""

    DATETIME = "datetime"
    DATE = "date"
    TIME = "time"


@dataclass
class DateTimeEntityDescription(EntityDescription):
    """A class that describes date/time entities."""


class DateTimeEntity(Entity):
    """Representation of a Date/time entity."""

    entity_description: DateTimeEntityDescription
    _attr_mode: DateTimeMode
    _attr_native_value: datetime | date | time | None
    _attr_value: None = None
    _attr_has_date: None = None
    _attr_has_time: None = None
    _attr_year: None = None
    _attr_month: None = None
    _attr_day: None = None
    _attr_timestamp: None = None
    _attr_state: None = None

    @property
    def capability_attributes(self) -> dict[str, Any]:
        """Return capability attributes."""
        return {
            ATTR_MODE: self.mode,
        }

    @property
    @final
    def state_attributes(self) -> dict[str, str | bool | int | float]:
        """Return the state attributes."""
        state_attr: dict[str, str | bool | int | float] = {
            ATTR_MODE: self.mode,
            ATTR_HAS_DATE: self.has_date,
            ATTR_HAS_TIME: self.has_time,
        }
        for attr_name, attr in (
            (ATTR_DAY, self.day),
            (ATTR_MONTH, self.month),
            (ATTR_YEAR, self.year),
            (ATTR_TIMESTAMP, self.timestamp),
        ):
            if attr is not None:
                state_attr[attr_name] = attr
        return state_attr

    @property
    @final
    def state(self) -> str | None:
        """Return the entity state."""
        if self.value is None:
            return None
        if self.has_date and self.has_time:
            return self.value.strftime(FMT_DATETIME)

        if self.has_date:
            return self.value.strftime(FMT_DATE)

        return self.value.strftime(FMT_TIME)

    @property
    @final
    def has_date(self) -> bool:
        """Return whether entity has date component."""
        return self.mode in (DateTimeMode.DATE, DateTimeMode.DATETIME)

    @property
    @final
    def has_time(self) -> bool:
        """Return whether entity has time component."""
        return self.mode in (DateTimeMode.TIME, DateTimeMode.DATETIME)

    @property
    def mode(self) -> DateTimeMode:
        """Return mode."""
        return self._attr_mode

    @property
    @final
    def day(self) -> int | None:
        """Return day from value."""
        if isinstance(self.value, time) or self.value is None:
            return None
        return self.value.day

    @property
    @final
    def month(self) -> int | None:
        """Return month from value."""
        if isinstance(self.value, time) or self.value is None:
            return None
        return self.value.month

    @property
    @final
    def year(self) -> int | None:
        """Return year from value."""
        if isinstance(self.value, time) or self.value is None:
            return None
        return self.value.year

    @property
    @final
    def timestamp(self) -> float | None:
        """Return UNIX timestamp of value."""
        if not isinstance(self.value, datetime):
            return None
        return self.value.timestamp()

    @property
    @final
    def value(self) -> datetime | date | time | None:
        """Return the entity value to represent the entity state."""
        # If there is an entity mode and native value type mismatch, the native value
        # is invalid and we must return None
        if (not self.has_time and isinstance(self.native_value, time)) or (
            not self.has_date and isinstance(self.native_value, date)
        ):
            return None

        # If native value is a datetime and entity only has one component, return the
        # right component.
        if isinstance(self.native_value, datetime) and (self.has_time ^ self.has_date):
            if self.has_time:
                return self.native_value.time()
            return self.native_value.date()

        return self.native_value

    @property
    def native_value(self) -> datetime | date | time | None:
        """Return the value reported by the datetime."""
        return self._attr_native_value

    def set_datetime(self, dt_or_d_or_t: datetime | date | time) -> None:
        """Change the date/time."""
        raise NotImplementedError()

    async def async_set_datetime(self, dt_or_d_or_t: datetime | date | time) -> None:
        """Change the date/time."""
        await self.hass.async_add_executor_job(self.set_datetime, dt_or_d_or_t)
