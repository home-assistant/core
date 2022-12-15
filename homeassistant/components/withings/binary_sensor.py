"""Sensors flow for Withings."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import (
    BaseWithingsSensor,
    WithingsBinarySensorEntityDescription,
    async_create_entities,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor config entry."""
    entities = await async_create_entities(
        hass, entry, WithingsHealthBinarySensor, BINARY_SENSOR_DOMAIN
    )

    async_add_entities(entities, True)


class WithingsHealthBinarySensor(BaseWithingsSensor, BinarySensorEntity):
    """Implementation of a Withings sensor."""

    entity_description: WithingsBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self._state_data
