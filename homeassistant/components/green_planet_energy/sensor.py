"""Green Planet Energy sensor platform."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_EURO, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SENSOR_HOURS
from .coordinator import GreenPlanetEnergyUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class GreenPlanetEnergySensorEntityDescription(SensorEntityDescription):
    """Describes Green Planet Energy sensor entity."""

    hour: int


SENSOR_DESCRIPTIONS: list[GreenPlanetEnergySensorEntityDescription] = [
    GreenPlanetEnergySensorEntityDescription(
        key=f"price_{hour:02d}",
        translation_key=f"price_{hour:02d}",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=4,
        hour=hour,
    )
    for hour in SENSOR_HOURS
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Green Planet Energy sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        GreenPlanetEnergySensor(coordinator, description, config_entry)
        for description in SENSOR_DESCRIPTIONS
    )


class GreenPlanetEnergySensor(
    CoordinatorEntity[GreenPlanetEnergyUpdateCoordinator], SensorEntity
):
    """Representation of a Green Planet Energy sensor."""

    entity_description: GreenPlanetEnergySensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GreenPlanetEnergyUpdateCoordinator,
        description: GreenPlanetEnergySensorEntityDescription,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{config_entry.entry_id}_{description.key}"
        self._attr_name = f"Preis {description.hour:02d}:00"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self.entity_description.key)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        return {
            "hour": self.entity_description.hour,
            "time_slot": f"{self.entity_description.hour:02d}:00-{self.entity_description.hour + 1:02d}:00",
        }
