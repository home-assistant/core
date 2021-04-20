"""Sensors flow for Withings."""
from __future__ import annotations

from typing import Callable

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from .common import BaseWithingsSensor, async_create_entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[list[Entity], bool], None],
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
    def state(self) -> None | str | int | float:
        """Return the state of the entity."""
        return self._state_data

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity, if any."""
        return self._attribute.unit_of_measurement
