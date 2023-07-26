"""PEGELONLINE sensor entities."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PegelOnlineDataUpdateCoordinator
from .entity import PegelOnlineEntity
from .model import PegelOnlineData


@dataclass
class PegelOnlineRequiredKeysMixin:
    """Mixin for required keys."""

    fn_native_unit: Callable[[PegelOnlineData], str]
    fn_native_value: Callable[[PegelOnlineData], float]


@dataclass
class PegelOnlineSensorEntityDescription(
    SensorEntityDescription, PegelOnlineRequiredKeysMixin
):
    """PEGELONLINE sensor entity description."""


SENSORS: tuple[PegelOnlineSensorEntityDescription, ...] = (
    PegelOnlineSensorEntityDescription(
        key="water_level",
        translation_key="water_level",
        state_class=SensorStateClass.MEASUREMENT,
        fn_native_unit=lambda data: data["water_level"].uom,
        fn_native_value=lambda data: data["water_level"].value,
        icon="mdi:waves-arrow-up",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the PEGELONLINE sensor."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [PegelOnlineSensor(coordinator, description) for description in SENSORS]
    )


class PegelOnlineSensor(PegelOnlineEntity, SensorEntity):
    """Representation of a PEGELONLINE sensor."""

    entity_description: PegelOnlineSensorEntityDescription

    def __init__(
        self,
        coordinator: PegelOnlineDataUpdateCoordinator,
        description: PegelOnlineSensorEntityDescription,
    ) -> None:
        """Initialize a PEGELONLINE sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self.station.uuid}_{description.key}"
        self._attr_native_unit_of_measurement = self.entity_description.fn_native_unit(
            coordinator.data
        )

        if self.station.latitude and self.station.longitude:
            self._attr_extra_state_attributes.update(
                {
                    ATTR_LATITUDE: self.station.latitude,
                    ATTR_LONGITUDE: self.station.longitude,
                }
            )

    @property
    def native_value(self) -> float:
        """Return the state of the device."""
        return self.entity_description.fn_native_value(self.coordinator.data)
