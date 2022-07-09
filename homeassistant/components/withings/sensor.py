"""Sensors flow for Withings."""
from __future__ import annotations

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import BaseWithingsSensor, async_create_entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor config entry."""
    entities = await async_create_entities(
        hass,
        entry,
        WithingsHealthSensor,
        SENSOR_DOMAIN,
    )

    async_add_entities(entities, True)


class WithingsHealthSensor(BaseWithingsSensor, SensorEntity):
    """Implementation of a Withings sensor."""

    @property
    def native_value(self) -> None | str | int | float:
        """Return the state of the entity."""
        return self._state_data

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity, if any."""
        return self._attribute.unit_of_measurement

    @property
    def state_class(self) -> str:
        """Return the state_class of this entity, if any."""
        return SensorStateClass.MEASUREMENT
