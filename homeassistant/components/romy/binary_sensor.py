"""Checking binary status values from your ROMY."""

from dataclasses import dataclass

from romy import RomyRobot

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RomyVacuumCoordinator


@dataclass(frozen=True)
class RomyBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Immutable class for describing Romy data."""


BINARY_SENSORS: list[RomyBinarySensorEntityDescription] = [
    RomyBinarySensorEntityDescription(
        key="dustbin",
        translation_key="dustbin",
    ),
    RomyBinarySensorEntityDescription(
        key="dock",
        translation_key="dock",
        device_class=BinarySensorDeviceClass.PRESENCE,
    ),
    RomyBinarySensorEntityDescription(
        key="water_tank",
        translation_key="water_tank",
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
    RomyBinarySensorEntityDescription(
        key="water_tank_empty",
        translation_key="water_tank_empty",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ROMY vacuum cleaner."""

    coordinator: RomyVacuumCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        RomyBinarySensor(coordinator, coordinator.romy, entity_description)
        for entity_description in BINARY_SENSORS
        if entity_description.key in coordinator.romy.binary_sensors
    )


class RomyBinarySensor(CoordinatorEntity[RomyVacuumCoordinator], BinarySensorEntity):
    """RomyBinarySensor Class."""

    entity_description: RomyBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: RomyVacuumCoordinator,
        romy: RomyRobot,
        entity_description: RomyBinarySensorEntityDescription,
    ) -> None:
        """Initialize ROMYs StatusSensor."""
        self._sensor_value: bool | None = None
        super().__init__(coordinator)
        self.romy = romy
        self._attr_unique_id = self.romy.unique_id
        self._device_info = DeviceInfo(
            identifiers={(DOMAIN, romy.unique_id)},
            manufacturer="ROMY",
            name=romy.name,
            model=romy.model,
        )
        self.entity_description = entity_description


    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._sensor_value = self.romy.binary_sensors[self.entity_description.key]
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool | None:
        """Return the value of the sensor."""
        return self.romy.binary_sensors[self.entity_description.key]
