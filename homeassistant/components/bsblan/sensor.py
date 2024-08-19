"""Support for BSB-Lan sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .coordinator import BSBLanUpdateCoordinator
from .entity import BSBLanEntity
from .models import BSBLanData


@dataclass(frozen=True, kw_only=True)
class BSBLanSensorEntityDescription(SensorEntityDescription):
    """Describes BSB-Lan sensor entity."""

    value_fn: Callable[[BSBLanData], StateType]


SENSOR_TYPES: list[BSBLanSensorEntityDescription] = [
    BSBLanSensorEntityDescription(
        key="current_temperature",
        translation_key="current_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.coordinator.data.sensor.current_temperature.value,
    ),
    BSBLanSensorEntityDescription(
        key="outside_temperature",
        translation_key="outside_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.coordinator.data.sensor.outside_temperature.value,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BSB-Lan sensor based on a config entry."""
    data: BSBLanData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        BSBLanSensor(data.coordinator, data, description)
        for description in SENSOR_TYPES
    )


class BSBLanSensor(BSBLanEntity, SensorEntity):
    """Defines a BSB-Lan sensor."""

    entity_description: BSBLanSensorEntityDescription

    def __init__(
        self,
        coordinator: BSBLanUpdateCoordinator,
        data: BSBLanData,
        description: BSBLanSensorEntityDescription,
    ) -> None:
        """Initialize BSB-Lan sensor."""
        super().__init__(coordinator, data)
        self.entity_description = description
        self._attr_unique_id = f"{data.device.MAC}-{description.key}"
        self._attr_name = self._generate_name(description.translation_key)

    @staticmethod
    def _generate_name(translation_key: str | None) -> str:
        """Generate a name from the translation key."""
        if translation_key is None:
            return "Unknown"
        return translation_key.replace("_", " ").title()

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        value = self.entity_description.value_fn(self._data)
        try:
            return float(value) if value is not None else None
        except ValueError:
            return None
