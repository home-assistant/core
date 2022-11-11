"""Component to allow setting time as platforms."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
import logging
from typing import final

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import FORMAT_TIME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_HOUR,
    ATTR_MINUTE,
    ATTR_SECOND,
    ATTR_TIME,
    DOMAIN,
    SERVICE_SET_VALUE,
)

SCAN_INTERVAL = timedelta(seconds=30)

ENTITY_ID_FORMAT = DOMAIN + ".{}"

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Time entities."""
    component = hass.data[DOMAIN] = EntityComponent[TimeEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_SET_VALUE,
        {
            vol.Required(ATTR_TIME): cv.time,
        },
        "async_set_value",
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent[TimeEntity] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[TimeEntity] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


@dataclass
class TimeEntityDescription(EntityDescription):
    """A class that describes time entities."""


class TimeEntity(Entity):
    """Representation of a Time entity."""

    entity_description: TimeEntityDescription
    _attr_native_value: datetime | time | None
    _attr_value: None = None
    _attr_hour: None = None
    _attr_minute: None = None
    _attr_second: None = None
    _attr_state: None = None

    @property
    @final
    def state_attributes(self) -> dict[str, str | bool | int | float]:
        """Return the state attributes."""
        state_attr: dict[str, int | None] = {
            ATTR_HOUR: self.hour,
            ATTR_MINUTE: self.minute,
            ATTR_SECOND: self.second,
        }
        return {k: v for k, v in state_attr.items() if v is not None}

    @property
    @final
    def state(self) -> str | None:
        """Return the entity state."""
        if self.value is None:
            return None
        return self.value.strftime(FORMAT_TIME)

    @property
    @final
    def hour(self) -> int | None:
        """Return hour from value."""
        if self.value is None:
            return None
        return self.value.hour

    @property
    @final
    def minute(self) -> int | None:
        """Return minute from value."""
        if self.value is None:
            return None
        return self.value.minute

    @property
    @final
    def second(self) -> int | None:
        """Return second from value."""
        if self.value is None:
            return None
        return self.value.second

    @property
    @final
    def value(self) -> time | None:
        """Return the entity value to represent the entity state."""
        # If native value is a datetime, onlt return the time
        if isinstance(self.native_value, datetime):
            return self.native_value.time()
        return self.native_value

    @property
    def native_value(self) -> datetime | time | None:
        """Return the value reported by the time."""
        return self._attr_native_value

    def set_value(self, time_value: time) -> None:
        """Change the time."""
        raise NotImplementedError()

    async def async_set_value(self, time_value: time) -> None:
        """Change the time."""
        await self.hass.async_add_executor_job(self.set_value, time_value)
