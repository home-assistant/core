"""Support for the Nettigo Air Monitor air_quality service."""
from __future__ import annotations

from typing import Any

from homeassistant.components.air_quality import AirQualityEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import AIR_QUALITY_SENSORS, DEFAULT_NAME, DOMAIN

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Add a Nettigo Air Monitor entities from a config_entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for sensor in AIR_QUALITY_SENSORS:
        if f"{sensor}_p1" in coordinator.data:
            entities.append(NAMAirQuality(coordinator, sensor))

    async_add_entities(entities, False)


def round_state(func):
    """Round state."""

    def _decorator(self):
        res = func(self)
        if isinstance(res, float):
            return round(res)
        return res

    return _decorator


class NAMAirQuality(CoordinatorEntity, AirQualityEntity):
    """Define an Nettigo Air Monitor air quality."""

    def __init__(self, coordinator: DataUpdateCoordinator, sensor_type: str):
        """Initialize."""
        super().__init__(coordinator)
        self.sensor_type = sensor_type

    @property
    def name(self) -> str:
        """Return the name."""
        return f"{DEFAULT_NAME} {AIR_QUALITY_SENSORS[self.sensor_type]}"

    @property
    @round_state
    def particulate_matter_2_5(self) -> str | None:
        """Return the particulate matter 2.5 level."""
        return getattr(self.coordinator.data, f"{self.sensor_type}_p2", None)

    @property
    @round_state
    def particulate_matter_10(self) -> str | None:
        """Return the particulate matter 10 level."""
        return getattr(self.coordinator.data, f"{self.sensor_type}_p1", None)

    @property
    @round_state
    def carbon_dioxide(self) -> str | None:
        """Return the particulate matter 10 level."""
        return getattr(self.coordinator.data, "conc_co2_ppm", None)

    @property
    def unique_id(self) -> str:
        """Return a unique_id for this entity."""
        return f"{self.coordinator.unique_id}-{self.sensor_type}".lower()

    @property
    def device_info(self) -> dict[str, Any]:
        """Return the device info."""
        return self.coordinator.device_info
