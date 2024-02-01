"""PEGELONLINE sensor entities."""
from __future__ import annotations

from dataclasses import dataclass

from aiopegelonline.models import CurrentMeasurement

from homeassistant.components.sensor import (
    SensorDeviceClass,
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


@dataclass(frozen=True)
class PegelOnlineRequiredKeysMixin:
    """Mixin for required keys."""

    measurement_key: str


@dataclass(frozen=True)
class PegelOnlineSensorEntityDescription(
    SensorEntityDescription, PegelOnlineRequiredKeysMixin
):
    """PEGELONLINE sensor entity description."""


SENSORS: tuple[PegelOnlineSensorEntityDescription, ...] = (
    PegelOnlineSensorEntityDescription(
        key="air_temperature",
        translation_key="air_temperature",
        measurement_key="air_temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=False,
    ),
    PegelOnlineSensorEntityDescription(
        key="clearance_height",
        translation_key="clearance_height",
        measurement_key="clearance_height",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DISTANCE,
    ),
    PegelOnlineSensorEntityDescription(
        key="oxygen_level",
        translation_key="oxygen_level",
        measurement_key="oxygen_level",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    PegelOnlineSensorEntityDescription(
        key="ph_value",
        measurement_key="ph_value",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.PH,
        entity_registry_enabled_default=False,
    ),
    PegelOnlineSensorEntityDescription(
        key="water_speed",
        translation_key="water_speed",
        measurement_key="water_speed",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.SPEED,
        entity_registry_enabled_default=False,
    ),
    PegelOnlineSensorEntityDescription(
        key="water_flow",
        translation_key="water_flow",
        measurement_key="water_flow",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    PegelOnlineSensorEntityDescription(
        key="water_level",
        translation_key="water_level",
        measurement_key="water_level",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PegelOnlineSensorEntityDescription(
        key="water_temperature",
        translation_key="water_temperature",
        measurement_key="water_temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the PEGELONLINE sensor."""
    coordinator: PegelOnlineDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            PegelOnlineSensor(coordinator, description)
            for description in SENSORS
            if getattr(coordinator.data, description.measurement_key) is not None
        ]
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

        if description.device_class != SensorDeviceClass.PH:
            self._attr_native_unit_of_measurement = self.measurement.uom

        if self.station.latitude and self.station.longitude:
            self._attr_extra_state_attributes.update(
                {
                    ATTR_LATITUDE: self.station.latitude,
                    ATTR_LONGITUDE: self.station.longitude,
                }
            )

    @property
    def measurement(self) -> CurrentMeasurement:
        """Return the measurement data of the entity."""
        return getattr(self.coordinator.data, self.entity_description.measurement_key)

    @property
    def native_value(self) -> float:
        """Return the state of the device."""
        return self.measurement.value
