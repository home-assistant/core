"""Component to allow numeric input for platforms."""
from __future__ import annotations

from abc import abstractmethod
from datetime import timedelta
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_STEP,
    ATTR_VALUE,
    DEFAULT_MAX_VALUE,
    DEFAULT_MIN_VALUE,
    DEFAULT_STEP,
    DOMAIN,
    SERVICE_SET_VALUE,
)

SCAN_INTERVAL = timedelta(seconds=30)

ENTITY_ID_FORMAT = DOMAIN + ".{}"

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Number entities."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_SET_VALUE,
        {vol.Required(ATTR_VALUE): vol.Coerce(float)},
        "async_set_value",
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)  # type: ignore


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)  # type: ignore


class NumberEntity(Entity):
    """Representation of a Number entity."""

    @property
    def capability_attributes(self) -> dict[str, Any]:
        """Return capability attributes."""
        return {
            ATTR_MIN: self.min_value,
            ATTR_MAX: self.max_value,
            ATTR_STEP: self.step,
        }

    @property
    def min_value(self) -> float:
        """Return the minimum value."""
        return DEFAULT_MIN_VALUE

    @property
    def max_value(self) -> float:
        """Return the maximum value."""
        return DEFAULT_MAX_VALUE

    @property
    def step(self) -> float:
        """Return the increment/decrement step."""
        step = DEFAULT_STEP
        value_range = abs(self.max_value - self.min_value)
        if value_range != 0:
            while value_range <= step:
                step /= 10.0
        return step

    @property
    def state(self) -> float:
        """Return the entity state."""
        return self.value

    @property
    @abstractmethod
    def value(self) -> float:
        """Return the entity value to represent the entity state."""

    def set_value(self, value: float) -> None:
        """Set new value."""
        raise NotImplementedError()

    async def async_set_value(self, value: float) -> None:
        """Set new value."""
        await self.hass.async_add_executor_job(self.set_value, value)
