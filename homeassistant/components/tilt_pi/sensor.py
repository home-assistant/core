"""Support for Tilt Hydrometer sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TiltPiDataUpdateCoordinator
from .model import TiltHydrometerData

ATTR_TEMPERATURE = "temperature"
ATTR_GRAVITY = "gravity"


@dataclass(frozen=True, kw_only=True)
class TiltEntityDescription(SensorEntityDescription):
    """Describes TiltHydrometerData sensor entity."""

    value_fn: Callable[[TiltHydrometerData], StateType]


SENSOR_TYPES: Final[list[TiltEntityDescription]] = [
    TiltEntityDescription(
        key=ATTR_TEMPERATURE,
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.temperature,
    ),
    TiltEntityDescription(
        key=ATTR_GRAVITY,
        name="Gravity",
        native_unit_of_measurement="SG",
        # device_class=SensorDeviceClass.,
        icon="mdi:water",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.gravity,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tilt Hydrometer sensors."""
    coordinator: TiltPiDataUpdateCoordinator = config_entry.runtime_data

    async_add_entities(
        TiltSensor(
            coordinator=coordinator,
            description=description,
            hydrometer=hydrometer,
        )
        for description in SENSOR_TYPES
        for hydrometer in coordinator.data
    )


class TiltSensor(CoordinatorEntity[TiltPiDataUpdateCoordinator], SensorEntity):
    """Defines a Tilt sensor."""

    entity_description: TiltEntityDescription

    def __init__(
        self,
        coordinator: TiltPiDataUpdateCoordinator,
        description: TiltEntityDescription,
        hydrometer: TiltHydrometerData,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entity_description = description
        self._hydrometer = hydrometer
        self._mac_id = hydrometer.mac_id
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{hydrometer.mac_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, hydrometer.mac_id)},
            name=f"Tilt {hydrometer.color}",
            manufacturer="Tilt Hydrometer",
            model=f"{hydrometer.color} Tilt Hydrometer",
        )

    def _get_current_hydrometer(self) -> TiltHydrometerData | None:
        """Get current hydrometer data."""
        if not self.coordinator.data:
            return None

        for hydrometer in self.coordinator.data:
            if hydrometer.mac_id == self._mac_id:
                return hydrometer
        return None

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        if hydrometer := self._get_current_hydrometer():
            return self.entity_description.value_fn(hydrometer)
        return None
