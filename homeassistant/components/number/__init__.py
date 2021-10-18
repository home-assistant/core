"""Component to allow numeric input for platforms."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any, final

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import Entity, EntityDescription
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
        async_set_value,
    )

    return True


async def async_set_value(entity: NumberEntity, service_call: ServiceCall) -> None:
    """Service call wrapper to set a new value."""
    value = service_call.data["value"]
    if value < entity.min_value or value > entity.max_value:
        raise ValueError(
            f"Value {value} for {entity.name} is outside valid range {entity.min_value} - {entity.max_value}"
        )
    await entity.async_set_value(value)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


@dataclass
class NumberEntityDescription(EntityDescription):
    """A class that describes number entities."""


class NumberEntity(Entity):
    """Representation of a Number entity."""

    entity_description: NumberEntityDescription
    _attr_max_value: float = DEFAULT_MAX_VALUE
    _attr_min_value: float = DEFAULT_MIN_VALUE
    _attr_state: None = None
    _attr_step: float
    _attr_value: float

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
        return self._attr_min_value

    @property
    def max_value(self) -> float:
        """Return the maximum value."""
        return self._attr_max_value

    @property
    def step(self) -> float:
        """Return the increment/decrement step."""
        if hasattr(self, "_attr_step"):
            return self._attr_step
        step = DEFAULT_STEP
        value_range = abs(self.max_value - self.min_value)
        if value_range != 0:
            while value_range <= step:
                step /= 10.0
        return step

    @property
    @final
    def state(self) -> float | None:
        """Return the entity state."""
        return self.value

    @property
    def value(self) -> float | None:
        """Return the entity value to represent the entity state."""
        return self._attr_value

    def set_value(self, value: float) -> None:
        """Set new value."""
        raise NotImplementedError()

    async def async_set_value(self, value: float) -> None:
        """Set new value."""
        await self.hass.async_add_executor_job(self.set_value, value)
