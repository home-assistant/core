"""Component to allow setting date as platforms."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging
from typing import final

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import FORMAT_DATE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import ATTR_DATE, ATTR_DAY, ATTR_MONTH, ATTR_YEAR, DOMAIN, SERVICE_SET_VALUE

SCAN_INTERVAL = timedelta(seconds=30)

ENTITY_ID_FORMAT = DOMAIN + ".{}"

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Date entities."""
    component = hass.data[DOMAIN] = EntityComponent[DateEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_SET_VALUE,
        vol.Schema(
            {
                vol.Required(ATTR_DATE): cv.date,
            },
            extra=vol.ALLOW_EXTRA,
        ),
        "async_set_value",
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent[DateEntity] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[DateEntity] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


@dataclass
class DateEntityDescription(EntityDescription):
    """A class that describes date entities."""


class DateEntity(Entity):
    """Representation of a Date entity."""

    entity_description: DateEntityDescription
    _attr_native_value: date | datetime | None
    _attr_year: None = None
    _attr_month: None = None
    _attr_day: None = None
    _attr_state: None = None

    @property
    @final
    def state_attributes(self) -> dict[str, int]:
        """Return the state attributes."""
        state_attr: dict[str, int | None] = {
            ATTR_DAY: self.day,
            ATTR_MONTH: self.month,
            ATTR_YEAR: self.year,
        }
        return {k: v for k, v in state_attr.items() if v is not None}

    @property
    @final
    def state(self) -> str | None:
        """Return the entity state."""
        if self.value is None:
            return None
        return self.value.strftime(FORMAT_DATE)

    @property
    @final
    def day(self) -> int | None:
        """Return day from value."""
        if self.value is None:
            return None
        return self.value.day

    @property
    @final
    def month(self) -> int | None:
        """Return month from value."""
        if self.value is None:
            return None
        return self.value.month

    @property
    @final
    def year(self) -> int | None:
        """Return year from value."""
        if self.value is None:
            return None
        return self.value.year

    @property
    @final
    def value(self) -> date | None:
        """Return the entity value to represent the entity state."""
        # If native value is a datetime, only return the date.
        if isinstance(self.native_value, datetime):
            return self.native_value.date()
        return self.native_value

    @property
    def native_value(self) -> datetime | date | None:
        """Return the value reported by the date."""
        return self._attr_native_value

    def set_value(self, date_value: date) -> None:
        """Change the date."""
        raise NotImplementedError()

    async def async_set_value(self, date_value: date) -> None:
        """Change the date."""
        await self.hass.async_add_executor_job(self.set_value, date_value)
